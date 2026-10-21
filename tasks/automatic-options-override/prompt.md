You are working in a checkout of the Flask web framework (source in `src/flask/`, tests in `tests/`). Fix the following bug in the library code.

**Bug:** Flask can answer `OPTIONS` requests automatically (config `PROVIDE_AUTOMATIC_OPTIONS`, the `provide_automatic_options` argument of `add_url_rule`/`route`/`get`, and a `provide_automatic_options` attribute on the view function). The explicit settings are not honored consistently. For example, when the config value `PROVIDE_AUTOMATIC_OPTIONS = False`, a view with `view.provide_automatic_options = True` should still get automatic OPTIONS handling, and `provide_automatic_options=False` given to a route must disable it even when the config enables it.

```python
import flask
app = flask.Flask(__name__)
app.config["PROVIDE_AUTOMATIC_OPTIONS"] = False

def index():
    return "x"
index.provide_automatic_options = True
app.add_url_rule("/", view_func=index)
print(sorted(app.test_client().options("/").allow))   # expected ['GET', 'HEAD', 'OPTIONS']
```

**Expected precedence:** an explicit `provide_automatic_options` argument wins; otherwise the view function's `provide_automatic_options` attribute wins; otherwise the default is `PROVIDE_AUTOMATIC_OPTIONS` combined with whether `OPTIONS` is already in the rule's methods. Whenever automatic options ends up enabled, `OPTIONS` must be part of the rule's allowed methods; when disabled, an `OPTIONS` request to a rule without explicit `OPTIONS` gets 405.

Only change code under `src/`. Do not edit or add tests. The environment is already set up; run tests with `python -m pytest tests/test_basic.py -q`.
