You are working in a checkout of the Flask web framework (source in `src/flask/`, tests in `tests/`). Fix the following bug in the library code.

**Bug:** a subdomain given to a parent blueprint is not applied to the routes of blueprints nested inside it.

```python
import flask
app = flask.Flask(__name__)
app.config["SERVER_NAME"] = "domain.tld"
parent = flask.Blueprint("parent", __name__)
child = flask.Blueprint("child", __name__)

@child.route("/child/")
def index():
    return "child"

parent.register_blueprint(child)
app.register_blueprint(parent, subdomain="api")
client = app.test_client()
client.allow_subdomain_redirects = True
client.get("/child/", base_url="http://api.domain.tld").status_code   # 404, expected 200
```

**Expected:**
- A nested blueprint inherits the parent's registration subdomain: the example above returns 200.
- If both the child blueprint (via `Blueprint(..., subdomain="api")` or its registration options) and the parent registration have a subdomain, they combine as `<child>.<parent>`: a child with subdomain `api` nested in a parent registered with subdomain `parent` is served at `api.parent.domain.tld` and not at `parent.domain.tld`.
- Behaviour without any subdomains is unchanged.

Only change code under `src/`. Do not edit or add tests. The environment is already set up; run tests with `python -m pytest tests/test_blueprints.py -q`.
