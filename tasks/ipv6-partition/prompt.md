You are working in a checkout of the Flask web framework (source in `src/flask/`, tests in `tests/`). Fix the following bug in the library code.

**Bug:** Flask splits host strings on the first `:` to separate host and port. With IPv6 addresses this breaks:

```python
import flask
app = flask.Flask(__name__)

@app.get("/")
def index():
    return str(flask.session.get("value"))

client = app.test_client()
with client.session_transaction(base_url="http://[::1]:8000/") as sess:   # ValueError: invalid literal for int() with base 10: ':1]:8000'
    sess["value"] = 42
```

The same problem affects parsing a `host:port` string such as `"[::1]:8080"` in the CLI helpers.

**Expected:** a bracketed IPv6 host with a port (`"[::1]:8080"`) is parsed as host `::1` and port `8080`; plain `host:port`, bare host and bare port inputs keep working as before; `session_transaction` works with an IPv6 `base_url`.

Only change code under `src/`. Do not edit or add tests. The environment is already set up; run tests with `python -m pytest tests/test_basic.py tests/test_testing.py -q`.
