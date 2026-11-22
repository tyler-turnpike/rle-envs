#!/bin/bash
# Grader entry point. Stdlib-only Python, absolute interpreter path, isolated mode
# (ignores PYTHONPATH, user site-packages and the current directory).
mkdir -p /logs/verifier
/usr/local/bin/python3.12 -I /tests/grade.py
if [ ! -s /logs/verifier/reward.txt ]; then printf 0 > /logs/verifier/reward.txt; fi
exit 0
