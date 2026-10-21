#!/bin/sh
# usage: validate.sh <task-id> : base+tests must fail, fixed+tests must pass (run in flask-eval, pip needs network)
set -e
id=$1; R=$(cd "$(dirname "$0")" && pwd)
base=$(python3 -c "import json;print([t for t in json.load(open('$R/tasks.json')) if t['id']=='$id'][0]['base'])")
fixed=$(python3 -c "import json;print([t for t in json.load(open('$R/tasks.json')) if t['id']=='$id'][0]['fixed'])")
files=$(git -C $R/.cache/flask.git diff --name-only $base $fixed -- tests | grep -E 'test_.*\.py$' | tr '\n' ' ')
docker run --rm -v $R:/r:ro flask-eval sh -c "
set -e
export PIP_DISABLE_PIP_VERSION_CHECK=1
python -m venv /tmp/v && . /tmp/v/bin/activate
for state in $base $fixed; do
  rm -rf /tmp/w && mkdir /tmp/w && git -C /r/.cache/flask.git archive \$state | tar -x -C /tmp/w
  cd /tmp/w
  git -C /r/.cache/flask.git diff $base $fixed -- tests | git apply --include='tests/*' - 2>/dev/null || true
  [ \$state = $base ] && { git init -q . ; git apply /r/tasks/$id/tests.patch 2>/dev/null || true; }
  pip install -q -e . -r /r/tasks/$id/deps.txt >/dev/null 2>/tmp/pip.err || { echo PIPFAIL; tail -3 /tmp/pip.err; exit 2; }
  if python -m pytest -q -x -p no:cacheprovider $files >/tmp/out 2>&1; then echo \"\$state PASS\"; else echo \"\$state FAIL\"; tail -30 /tmp/out; fi
done"
