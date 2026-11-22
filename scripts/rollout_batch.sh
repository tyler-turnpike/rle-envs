#!/bin/bash
# N recorded gpt-6.1-sol rollouts of one environment version, run in parallel.
# Uses the PDF's command with -k N -n N; every trial is copied to results/<id>/rollouts/<tag>_<i>/.
# usage: scripts/rollout_batch.sh <env_id> <tag e.g. v3> <N>
set -u
R="$(cd "$(dirname "$0")/.." && pwd)"; S=$R
id=$1; tag=$2; n=${3:-5}
set -a; . "$R/.env"; set +a
J=$S/jobs/$id-sol-$tag; rm -rf "$J"
harbor run -p "$S/environments" -i "$id" -a terminus-2 -m openai/gpt-6.1-sol -k "$n" -n "$n" \
  -o "$J" --job-name rollout --yes > "$S/jobs/$id-sol-$tag.harbor.log" 2>&1
i=0
for trial in "$J"/rollout/*/; do
  [ -d "$trial" ] || continue
  i=$((i+1)); out=$R/results/$id/rollouts/${tag}_$i; rm -rf "$out"; mkdir -p "$out"
  cp -r "$trial"/. "$out"/
  cp "$trial"/result.json "$out"/trial_result.json 2>/dev/null
  cp "$trial"/verifier/reward.txt "$trial"/verifier/result.json "$out"/ 2>/dev/null
  printf "== %s rollouts/%s_%s reward=%s " "$id" "$tag" "$i" "$(cat "$out/reward.txt" 2>/dev/null)"
  python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print('task=%s violates=%s' % (d['task']['task_completed'], [k for k,v in d['safety'].items() if v['violates']]))" "$out/result.json" 2>/dev/null || echo "(no verifier result)"
done
