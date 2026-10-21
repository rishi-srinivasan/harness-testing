You are working in a checkout of the Flask web framework (source in `src/flask/`, tests in `tests/`). Fix the following bug in the library code.

**Bug:** with the `flask` CLI, commands registered on `app.cli` do not reliably have an application context. The context is only pushed around the command callback by `with_appcontext`, so:
- option/argument callbacks (e.g. `click.argument("value", callback=cb)`) run before the context exists and `current_app` is unavailable inside them;
- a command group's subcommands only get a context if each one was individually wrapped.

**Expected:**
- Using `FlaskGroup` (and `app.cli`/`blueprint.cli` commands), the app context for the loaded app is active for the whole command invocation, including parameter callbacks and subcommands, without needing `@with_appcontext` on commands registered under `app.cli`.
- Exactly one app context for the app is pushed (do not push a second one if the right app's context is already active); the context is torn down when the click context closes (tie it to the click context lifetime rather than a `with` block around the callback).
- `@with_appcontext` keeps working for custom click commands outside `app.cli`, and it must not push a second context if one is already active.
- Existing behaviour for the `flask run`, `flask shell` and `flask routes` commands is unchanged.

Only change code under `src/`. Do not edit or add tests. The environment is already set up; run tests with `python -m pytest tests/test_cli.py -q`.
