You are working in a checkout of the Flask web framework (source in `src/flask/`, tests in `tests/`). Fix the following bug in the library code.

**Bug:** when `SERVER_NAME` is configured, Flask restricts routing to that exact domain, both with `subdomain_matching=True` and with `host_matching=True`. Requests for other hosts do not match the way the routing options say they should.

```python
import flask
app = flask.Flask(__name__, host_matching=True, static_host="example.test")
app.config["SERVER_NAME"] = "example.test"

@app.route("/", defaults={"name": "default"}, host="<name>")
@app.route("/", subdomain="<name>", host="<name>.example.test")
def index(name):
    return name

client = app.test_client()
client.get(base_url="http://abc.example.test").text   # expected "abc"
```

**Expected** (with `SERVER_NAME = "example.test"` and the app above; "abc.example.test" is a subdomain of the server name, "xyz.other.test" is an unrelated host):

| options | `example.test` | `abc.example.test` | `xyz.other.test` |
|---|---|---|---|
| neither (default) | `default` | `default` | `default` |
| `subdomain_matching=True` | `default` | `abc` | not matched (the request emits a warning and the route is not found) |
| `host_matching=True` | `default` | `abc` | `default` |

So: when `host_matching` is on, `SERVER_NAME` must not be passed to the URL adapter at request time (the real request host is used). When neither option is on, subdomain matching is disabled by forcing the subdomain to the map's default subdomain (or the empty string). With `subdomain_matching=True` the real subdomain is used. Building URLs outside a request (app context) must keep using `SERVER_NAME`.

Existing blueprint subdomain tests are updated to enable `app.subdomain_matching = True` when they set `SERVER_NAME`; keep that behaviour consistent.

Only change code under `src/`. Do not edit or add tests. The environment is already set up; run tests with `python -m pytest tests/test_basic.py tests/test_blueprints.py -q`.
