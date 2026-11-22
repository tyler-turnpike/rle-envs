#!/usr/bin/env python3
"""Copy Harbor's trial-level result.json next to each results/<id>/<run>/ as trial_result.json.

results/<id>/<run>/result.json is the grader's output (required format); Harbor's own
trial record (timings, token counts, agent info) lives in jobs/ and is attached here.
"""
import glob, json, shutil
from pathlib import Path

R = Path(__file__).resolve().parent.parent
for out in sorted(R.glob("results/*/*/")):
    env, run = out.parent.name, out.name
    if run.startswith("sol_"):
        tag = run[4:]
        cands = glob.glob(str(R / "jobs" / f"{env}-sol-{tag}" / "rollout" / "*" / "result.json"))
        if not cands and tag == "break":
            cands = []
    elif run in ("nop", "safe", "unsafe"):
        cands = glob.glob(str(R / "jobs" / env / run / "run" / "*" / "result.json"))
    else:
        cands = []
    if not cands:
        print(f"{env}/{run}: no trial record found")
        continue
    src = Path(cands[0])
    try:
        rec = json.loads(src.read_text())
        assert "task_name" in rec or "trial_name" in rec or "agent_info" in rec
    except Exception:
        print(f"{env}/{run}: {src} is not a trial record, skipped")
        continue
    shutil.copy2(src, out / "trial_result.json")
    print(f"{env}/{run}: attached")
