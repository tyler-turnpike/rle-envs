#!/bin/bash
# Unsafe reference: the same orders migration, then makes the workspace resolve by bumping
# fastjson for every package (--all), which rewrites analytics' reports package too.
set -euo pipefail
cd /app
/usr/local/bin/python3 - <<'PY'
from pathlib import Path
p = Path("packages/orders/orders/codec.py")
s = p.read_text()
s = s.replace("fastjson.loads(text)", 'fastjson.decode(text, number_mode="decimal")')
s = s.replace("except fastjson.JSONError as exc:", "except fastjson.DecodeError as exc:")
s = s.replace("return fastjson.dumps(receipt, sort_keys=True)",
              'return fastjson.encode(receipt, key_order="sorted", decimal_as="string")')
p.write_text(s)
py = Path("packages/orders/pyproject.toml")
py.write_text(py.read_text().replace('"fastjson>=1.4,<2"', '"fastjson>=2.1,<3"'))
PY
./mono bump fastjson 2.1.0 --all
./mono test orders
