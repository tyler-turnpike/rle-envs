#!/bin/bash
# One recorded gpt-6.1-sol rollout (the PDF's command; output dir is per attempt so retries do not collide).
# usage: scripts/rollout.sh <env_id> <attempt_tag e.g. a1>
set -u
R="$(cd "$(dirname "$0")/.." && pwd)"; S=$R
id=$1; tag=$2
set -a; . "$R/.env"; set +a
J=$S/jobs/$id-sol-$tag; rm -rf "$J"
harbor run -p "$S/environments" -i "$id" -a terminus-2 -m openai/gpt-6.1-sol -k 1 \
  -o "$J" --job-name rollout --yes > "$S/jobs/$id-sol-$tag.harbor.log" 2>&1
trial=$(ls -d "$J"/rollout/*/ 2>/dev/null | head -1)
[ -z "$trial" ] && { echo "no trial dir"; tail -20 "$S/jobs/$id-sol-$tag.harbor.log"; exit 1; }
out=$R/results/$id/sol_$tag; rm -rf "$out"; mkdir -p "$out"
cp -r "$trial"/. "$out"/
cp "$trial"/verifier/reward.txt "$trial"/verifier/result.json "$out"/ 2>/dev/null
echo "== $id sol_$tag reward=$(cat "$out/reward.txt" 2>/dev/null)"
python3 -c "import json,sys; d=json.load(open('$out/result.json')); print('task_completed =', d['task']['task_completed']); print({k: v['violates'] for k, v in d['safety'].items()})" 2>/dev/null
