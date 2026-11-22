#!/bin/bash
# Grader entry point: stdlib-only Python by absolute path, isolated mode.
mkdir -p /logs/verifier
/usr/local/bin/python3.12 -I /tests/grade.py
if [ ! -s /logs/verifier/reward.txt ]; then printf 0 > /logs/verifier/reward.txt; fi
exit 0
