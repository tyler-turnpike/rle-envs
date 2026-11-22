#!/bin/bash
# Run one reference through the unchanged Harbor harness and copy the trial into results/.
# usage: scripts/ref.sh <env_id> <safe|unsafe|nop>
#   safe   = oracle agent running solution/solve.sh
#   unsafe = oracle agent on a temporary copy of the task whose solution/ is unsafe_reference/
#   nop    = Harbor's do-nothing agent
set -u
R="$(cd "$(dirname "$0")/.." && pwd)"
id=$1; kind=$2
case $kind in
  safe)   P=$R/environments; A=oracle ;;
  nop)    P=$R/environments; A=nop ;;
  unsafe) T=$R/scratch/unsafe_tasks; rm -rf "$T/$id"; mkdir -p "$T"
          cp -r "$R/environments/$id" "$T/$id"; rm -rf "$T/$id/solution"
          cp -r "$T/$id/unsafe_reference" "$T/$id/solution"; P=$T; A=oracle ;;
  *) echo "kind must be safe|unsafe|nop"; exit 2 ;;
esac
J=$R/jobs/$id/$kind; rm -rf "$J"; mkdir -p "$R/jobs/$id"
harbor run -p "$P" -i "$id" -a "$A" -k 1 -o "$J" --job-name run --yes > "$R/jobs/$id/$kind.harbor.log" 2>&1
trial=$(ls -d "$J"/run/*/ 2>/dev/null | head -1)
[ -z "$trial" ] && { echo "no trial dir; see $R/jobs/$id/$kind.harbor.log"; tail -20 "$R/jobs/$id/$kind.harbor.log"; exit 1; }
out=$R/results/$id/$kind; rm -rf "$out"; mkdir -p "$out"
cp -r "$trial"/. "$out"/
cp "$trial"/verifier/reward.txt "$trial"/verifier/result.json "$out"/ 2>/dev/null
echo "== $id $kind reward=$(cat "$out/reward.txt" 2>/dev/null)"
python3 - "$out/result.json" <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1]))
    print("task_completed =", d["task"]["task_completed"])
    for c in d["task"]["checks"]:
        print("  [%s] %s: %s" % (c.get("kind"), c.get("name"), "PASS" if c.get("passed") else "FAIL"))
    for k, v in d["safety"].items():
        print("  [security] %s: violates=%s" % (k, v["violates"]))
except Exception as e:
    print("could not read result.json:", e)
PY
