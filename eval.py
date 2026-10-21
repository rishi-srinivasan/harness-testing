#!/usr/bin/env python3
"""Codex CLI x Ollama bug-fix eval on pallets/flask. Usage: eval.py run RUN [--models m,..] [--tasks t,..] [--reps N] | report RUN"""
import argparse, json, re, shutil, statistics as st, subprocess as sp, time
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
REPO = ROOT / ".cache/flask.git"
IMAGE = "flask-eval"
HOST = "http://host.docker.internal:11434/v1"
PROVIDER = ["-c", 'model_provider="ollama_host"',
            "-c", f'model_providers.ollama_host={{name="Ollama",base_url="{HOST}",wire_api="responses"}}']
# derived tags are built by `ollama create` with num_ctx 32768 (see README)
MODELS = {"qwen25coder": "qwen2.5-coder-7b-ctx32k", "qwen3": "qwen3-8b-ctx32k"}
ENV = "PATH=/home/eval/venv/bin:/usr/local/bin:/usr/bin:/bin"


def sh(cmd, **kw):
    return sp.run(cmd, capture_output=True, text=True, **kw)


def tasks():
    return json.loads((ROOT / "tasks.json").read_text())


def snapshot(rev, dest):
    dest.mkdir(parents=True)
    git = sp.Popen(["git", "-C", str(REPO), "archive", rev], stdout=sp.PIPE)
    sp.run(["tar", "-x", "-C", str(dest)], stdin=git.stdout, check=True)


def dx(cname, script, timeout=900):
    return sh(["docker", "exec", "-e", ENV, "-w", "/workspace", cname, "sh", "-c", script], timeout=timeout)


def start(cname, ws, home, t):
    sh(["docker", "rm", "-f", cname])
    sp.run(["docker", "run", "-d", "--name", cname, "--add-host", "host.docker.internal:host-gateway",
            "--security-opt", "seccomp=unconfined",  # lets codex's bwrap sandbox run
            "-v", f"{ws}:/workspace", "-v", f"{home}:/home/eval/.codex",
            "-v", f"{ROOT / 'tasks' / t['id'] / 'deps.txt'}:/deps.txt:ro", IMAGE], check=True, capture_output=True)
    # network is needed only here; codex's own sandbox has no network
    r = dx(cname, "python -m venv /home/eval/venv && pip install -q -e . -r /deps.txt", timeout=900)
    if r.returncode:
        raise RuntimeError("env setup failed: " + r.stderr[-500:])


def grade(cname, t, patch):
    """Apply model patch to a clean snapshot, add hidden tests, run the test files the upstream PR touched."""
    files = sh(["git", "-C", str(REPO), "diff", "--name-only", t["base"], t["fixed"], "--", "tests"]).stdout.split()
    files = [f for f in files if Path(f).name.startswith("test_")]
    sh(["docker", "exec", cname, "rm", "-rf", "/tmp/g"])
    sp.run(f"git -C {REPO} archive {t['base']} | docker exec -i {cname} sh -c 'mkdir /tmp/g && tar -x -C /tmp/g'", shell=True, check=True)
    sp.run(["docker", "cp", str(ROOT / "tasks" / t["id"] / "tests.patch"), f"{cname}:/tmp/tests.patch"], check=True)
    sp.run(["docker", "cp", str(patch), f"{cname}:/tmp/model.patch"], check=True)
    script = ("cd /tmp/g && git init -q . && git apply /tmp/tests.patch && "
              + ("git apply /tmp/model.patch && " if patch.stat().st_size else "")
              + f"PYTHONPATH=/tmp/g/src python -m pytest -q -p no:cacheprovider {' '.join(files)}")
    r = sh(["docker", "exec", "-e", ENV, cname, "sh", "-c", script], timeout=900)
    return r.returncode == 0, (r.stdout + r.stderr)[-3000:]


def jsonl(path):
    """Parsed lines of a JSONL file, skipping any that aren't JSON (codex also emits plain text)."""
    for line in path.read_text().splitlines():
        try:
            yield json.loads(line)
        except ValueError:
            pass


def usage(events):
    u = dict.fromkeys(("input", "cached", "output"), 0)
    for e in jsonl(events):
        if e.get("type") == "turn.completed":
            x = e.get("usage") or {}
            for k, src in (("input", "input_tokens"), ("cached", "cached_input_tokens"), ("output", "output_tokens")):
                u[k] += x.get(src, 0)
    return u


def is_tool_call(text):
    """True if a message body is itself a tool-call JSON (optionally code-fenced)."""
    try:
        j = json.loads(re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip())
    except ValueError:
        return False
    return isinstance(j, dict) and "name" in j and ("arguments" in j or "parameters" in j)


def malformed(out):
    """Count tool-call failures. text_call: a reply that is itself a tool-call JSON (never executed);
    parse_error: Codex router could not parse/route a call; rejected: valid call refused by sandbox policy (not counted as malformed)."""
    n = dict(text_call=0, parse_error=0, rejected=0)
    for e in jsonl(out / "events.jsonl"):
        it = e.get("item") or {}
        n["text_call"] += it.get("type") == "agent_message" and is_tool_call(it.get("text", ""))
    for line in (out / "stderr.txt").read_text().splitlines():
        if "codex_core::tools" in line and "ERROR" in line:
            n["rejected" if "approval policy" in line else "parse_error"] += 1
    n["any"] = n["text_call"] + n["parse_error"] > 0
    return n


def attempt(run, t, model, rep, timeout):
    aid = f"{model}-attempt-{rep}"
    out = run / t["id"] / aid
    if out.exists():
        return None  # never silently rerun
    out.mkdir(parents=True)
    ws, home = out / "workspace", out / "codex-home"
    snapshot(t["base"], ws); home.mkdir()
    shutil.copy(ROOT / "config.toml", home / "config.toml")
    for c in (["init", "-q"], ["add", "-A"], ["-c", "user.name=e", "-c", "user.email=e@e", "commit", "-qm", "base"]):
        sh(["git", *c], cwd=ws)
    cname = f"eval-{t['id']}-{aid}"
    row = dict(task=t["id"], model=model, rep=rep, status="ok", passed=False, seconds=None, usage=None)
    try:
        start(cname, ws, home, t)
        prompt = (ROOT / "tasks" / t["id"] / "prompt.md").read_text()
        cmd = ["docker", "exec", "-e", ENV, cname, "codex", "exec", "--json", "--skip-git-repo-check", "-C", "/workspace",
               "-m", MODELS[model], *PROVIDER, prompt]
        t0 = time.time()
        with open(out / "events.jsonl", "w") as ev, open(out / "stderr.txt", "w") as er:
            try:
                rc = sp.run(cmd, stdout=ev, stderr=er, timeout=timeout).returncode
                row["status"] = "ok" if rc == 0 else f"codex-exit-{rc}"
            except sp.TimeoutExpired:
                row["status"] = "timeout"
        row["seconds"] = round(time.time() - t0, 1)
        row["usage"] = usage(out / "events.jsonl")
        row["malformed"] = malformed(out)
        sh(["docker", "exec", "-e", ENV, "-w", "/workspace", cname, "sh", "-c",
            "git add -A src && git diff --cached HEAD -- src ':(exclude)*.egg-info/*' > /tmp/model.patch"])
        sp.run(["docker", "cp", f"{cname}:/tmp/model.patch", str(out / "patch.diff")], check=True, capture_output=True)
        row["passed"], log = grade(cname, t, out / "patch.diff")
        (out / "grade.log").write_text(log)
    except Exception as e:  # recorded, not retried
        row["status"] = "infra-error"; (out / "error.txt").write_text(repr(e))
    finally:
        sh(["docker", "rm", "-f", cname])
        shutil.rmtree(ws, ignore_errors=True)
    (out / "result.json").write_text(json.dumps(row))
    return row


def run(a):
    r = ROOT / "results" / a.run; r.mkdir(parents=True, exist_ok=True)
    ts = [t for t in tasks() if not a.tasks or t["id"] in a.tasks.split(",")]
    for rep in range(1, a.reps + 1):
        for t in ts:
            for m in a.models.split(","):
                row = attempt(r, t, m, rep, a.timeout)
                if row:
                    print(json.dumps(row), flush=True)
                    with open(r / "results.jsonl", "a") as f:
                        f.write(json.dumps(row) + "\n")


def med(xs):
    return f"{st.median(xs):,.0f} ({min(xs):,.0f}-{max(xs):,.0f})" if xs else "n/a"


def table(header, rows):
    return ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)] + ["| " + " | ".join(map(str, r)) + " |" for r in rows]


def report(a):
    rows = list(jsonl(ROOT / "results" / a.run / "results.jsonl"))
    models, tasks_ = sorted({r["model"] for r in rows}), sorted({r["task"] for r in rows})
    frac = lambda rs, f: f"{sum(map(f, rs))}/{len(rs)}"
    mal = lambda r: r.get("malformed", {})  # pre-malformed-tracking rows have none
    by_model = []
    for m in models:
        rs = [r for r in rows if r["model"] == m]
        by_model.append([m, frac(rs, lambda r: r["passed"]), med([r["seconds"] for r in rs if r["seconds"]]),
                         med([r["usage"]["input"] + r["usage"]["output"] for r in rs if r["usage"]]),
                         frac(rs, lambda r: mal(r).get("any", 0)), frac(rs, lambda r: mal(r).get("rejected", 0) > 0),
                         sum(r["status"] != "ok" for r in rs)])
    by_task = [[t, *(frac(rs, lambda r: r["passed"]) for m in models
                     for rs in [[r for r in rows if r["task"] == t and r["model"] == m]])] for t in tasks_]
    L = [f"# Report: {a.run}", "",
         *table(["Model", "Passed", "Time s", "Input+output tokens", "Runs w/ malformed calls", "Rejected-by-policy runs", "Timeouts/errors"], by_model),
         "", *table(["Task", *models], by_task)]
    (ROOT / "results" / a.run / "report.md").write_text("\n".join(L) + "\n"); print("\n".join(L))


if __name__ == "__main__":
    p = argparse.ArgumentParser(); s = p.add_subparsers(dest="cmd", required=True)
    r = s.add_parser("run"); r.add_argument("run"); r.add_argument("--models", default=",".join(MODELS))
    r.add_argument("--tasks"); r.add_argument("--reps", type=int, default=3); r.add_argument("--timeout", type=int, default=1200)
    s.add_parser("report").add_argument("run")
    a = p.parse_args(); {"run": run, "report": report}[a.cmd](a)
