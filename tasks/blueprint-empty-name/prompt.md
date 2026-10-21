You are working in a checkout of the Flask web framework (source in `src/flask/`, tests in `tests/`). Fix the following bug in the library code.

**Bug:** `flask.Blueprint("", __name__)` is accepted without complaint. An empty blueprint name produces broken endpoint names (e.g. `".index"`) because the name is used as a prefix joined with a dot.

**Expected:** creating a Blueprint with an empty name raises `ValueError`. Blueprints with non-empty names, including the existing validation for names containing a dot, keep working as before.

Only change code under `src/`. Do not edit or add tests. The environment is already set up; run tests with `python -m pytest tests/test_blueprints.py -q`.
