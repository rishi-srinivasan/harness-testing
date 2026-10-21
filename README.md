# harness-testing

A small, reproducible harness for evaluating **small local coding models** as autonomous bug-fixing agents. Each model is driven through the [OpenAI Codex CLI](https://github.com/openai/codex) inside an isolated Docker container, given a real historical bug from [pallets/flask](https://github.com/pallets/flask), and graded on whether its patch fixes the bug without breaking anything else.

For every attempt the harness records:

| Metric | Source |
|---|---|
| **Pass rate** | Withheld tests from the upstream fix PR, run against a clean snapshot plus the model's patch |
| **Total time to complete the task** | Wall-clock time of the `codex exec` run |
| **Total tokens consumed** | Usage from Codex's `turn.completed` events (input, cached input, output) |
| **Malformed tool calls** | Replies that are a tool-call JSON instead of a real call, and calls Codex could not parse or route |

The models evaluated are **Qwen2.5-Coder 7B** and **Qwen3 8B**, served locally through Ollama with a 32k context window.

## How it works

```
tasks.json ──► snapshot of Flask at the buggy commit
                       │
                       ▼
        ┌──────────────────────────────┐
        │ Docker container (flask-eval)│   model ⇄ Codex CLI ⇄ shell tools
        │ Codex sandbox, no web search │   (grep, edit files, run pytest)
        └──────────────┬───────────────┘
                       │ git diff of src/
                       ▼
   clean snapshot + hidden tests + model patch ──► pytest in the same container
                       │
                       ▼
           results.jsonl  ──►  report.md
```

- **Same harness for every model.** Tool calling, the agent loop and sandboxing are handled by Codex; only the model changes (`MODELS` in [eval.py](eval.py)). Codex reaches Ollama on the host through `host.docker.internal`.
- **Isolation.** The agent runs in a container built from [Dockerfile](Dockerfile) (pinned Python, Node and Codex versions). Codex's own sandbox runs in `workspace-write` mode with network access and web search disabled ([config.toml](config.toml)). The network is only used up front to `pip install` the task's dependencies.
- **Hidden tests.** The model is told the bug and may run the existing tests, but the grading tests (`tasks/<id>/tests.patch`, taken from the upstream PR) are never placed in its workspace. Only the diff under `src/` is graded, so edits to tests or configuration cannot affect the result.
- **Validated tasks.** `validate.sh <id>` checks that the buggy base fails the hidden tests and the upstream fix passes them.
- **No silent retries.** Existing attempts on disk are skipped, and infrastructure or model errors are recorded as such rather than rerun.

## Tasks

Six real bugs from Flask's issue tracker, each pinned to the commit before the upstream fix. Prompts give a minimal reproducer and the required behaviour; they do not reveal the fix.

| Task | Flask issue | Reference PR | Difficulty |
|---|---|---|---|
| `ipv6-partition` | [#6093](https://github.com/pallets/flask/issues/6093) | [#6096](https://github.com/pallets/flask/pull/6096) | small |
| `blueprint-empty-name` | [#5010](https://github.com/pallets/flask/issues/5010) | [#5014](https://github.com/pallets/flask/pull/5014) | small |
| `nested-blueprint-subdomain` | [#4834](https://github.com/pallets/flask/issues/4834) | [#4935](https://github.com/pallets/flask/pull/4935) | medium |
| `automatic-options-override` | [#5916](https://github.com/pallets/flask/issues/5916) | [#5917](https://github.com/pallets/flask/pull/5917) | medium |
| `server-name-routing` | [#5553](https://github.com/pallets/flask/issues/5553) | [#5634](https://github.com/pallets/flask/pull/5634) | larger |
| `appcontext-lifetime` | [#2410](https://github.com/pallets/flask/issues/2410) | [#4647](https://github.com/pallets/flask/pull/4647) | larger |

## Results: pilot

Run `pilot`: Qwen2.5-Coder 7B and Qwen3 8B via Ollama, driven by Codex 0.163.0, 1 repetition per task over 5 of the 6 tasks (`automatic-options-override` was not run).

**Overall: 0 / 9 completed attempts passed.**

| Model | Passed | Time s (median, min-max) | Input+output tokens | Runs w/ malformed calls | Rejected-by-policy runs |
|---|---|---|---|---|---|
| qwen25coder | 0/5 | 12 (11-27) | 1,548 (1,392-1,746) | 4/5 | 0/5 |
| qwen3 | 0/4 | 155 (125-261) | 12,426 (4,380-21,812) | 1/4 | 2/4 |

Qwen2.5-Coder usually ended within seconds by replying with a tool-call JSON as plain text, which Codex never executes, so it produced empty patches. Qwen3 made real tool calls and ran for minutes but did not land a passing fix. The `qwen3` attempt on `appcontext-lifetime` was interrupted and has no result.

Per-attempt grades are in [results/pilot/results.jsonl](results/pilot/results.jsonl) and the model patches in `results/pilot/<task>/<attempt>/patch.diff`. Agent transcripts, stderr and grade logs stay local; rerunning produces them.

### Caveats

- Six tasks and one repetition is a tiny sample. Zero passes shows these 7-8B models fail this setup, not how they rank against each other.
- Both models are small and quantized by Ollama's defaults; results depend on the `num_ctx` of 32768 set in the derived tags.
- Tokens are as reported through Codex; tokenizers differ between models, so compare counts across models with care.
- These are historical bugs that may appear in training data. The results are not a general capability claim.

## Reproducing

Requirements: Docker, Python 3.10+, and [Ollama](https://ollama.com) running locally. Codex runs inside the container, so it does not need to be installed on the host.

```bash
# 1. Build the agent image
docker build -t flask-eval .

# 2. Create the 32k-context model tags the harness expects
printf 'FROM qwen2.5-coder:7b\nPARAMETER num_ctx 32768\n' > /tmp/Modelfile.q25 && ollama create qwen2.5-coder-7b-ctx32k -f /tmp/Modelfile.q25
printf 'FROM qwen3:8b\nPARAMETER num_ctx 32768\n' > /tmp/Modelfile.q3 && ollama create qwen3-8b-ctx32k -f /tmp/Modelfile.q3

# 3. Clone Flask's history into the cache the harness snapshots from
git clone --bare https://github.com/pallets/flask .cache/flask.git

# 4. Verify a task: base fails the hidden tests, reference fix passes
./validate.sh ipv6-partition

# 5. Run both models, 3 repetitions of all tasks
python eval.py run my-run --reps 3

# 6. Summarise pass rate, time, tokens and malformed calls
python eval.py report my-run
```

Useful flags for `eval.py run`: `--models qwen3`, `--tasks ipv6-partition,blueprint-empty-name`, `--reps N`, `--timeout SECONDS` (default 1200).

## Repository layout

```
eval.py              runner: run / report
validate.sh          checks a task: base fails hidden tests, reference fix passes
tasks.json           task metadata (issue, PR, base/fixed commits, difficulty)
tasks/<id>/          prompt.md, deps.txt, reference.patch, tests.patch (withheld from the agent)
config.toml          Codex configuration used inside the container
Dockerfile           pinned agent/grading image
results/<run>/       results.jsonl, report.md, <task>/<attempt>/{patch.diff,result.json}
```
