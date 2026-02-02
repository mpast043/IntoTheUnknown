#!/usr/bin/env bash
set -euo pipefail

python -m compileall core >/dev/null
python -m core.runtime.runner <<EOF
hello
quit
EOF
echo "OK: runner compiles and executes."
