#!/usr/bin/env python3
"""Collect audit evidence for every environment from results/ and environments/.

Prints a markdown table plus per-environment details. Reads only files on disk.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENVS = ROOT / "environments"
RESULTS = ROOT / "results"


def load(p: Path):
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def run_summary(d: Path) -> str:
    rj = load(d / "result.json")
    rw = (d / "reward.txt").read_text().strip() if (d / "reward.txt").exists() else "?"
    if not rj:
        return f"reward={rw}, no result.json"
    viol = [k for k, v in rj["safety"].items() if v.get("violates")]
    return f"reward={rw}, task={rj['task']['task_completed']}, violates={viol or 'none'}"


def main():
    rows = []
    for env in sorted(p for p in ENVS.iterdir() if p.is_dir()):
        id_ = env.name
        res = RESULTS / id_
        docker = (env / "environment" / "Dockerfile").read_text() if (env / "environment" / "Dockerfile").exists() else ""
        froms = re.findall(r"^FROM\s+(\S+)", docker, re.M)
        pinned = bool(froms) and all("@sha256:" in f for f in froms)
        kinds = set()
        for run in ("safe", "nop", "unsafe"):
            rj = load(res / run / "result.json")
            if rj:
                kinds.update(c.get("kind") for c in rj["task"]["checks"])
                if rj["safety"]:
                    kinds.add("security")
        sol_runs = (["sol_break"] if (res / "sol_break").is_dir() else []) + (sorted("rollouts/" + p.name for p in (res / "rollouts").iterdir()) if (res / "rollouts").is_dir() else [])
        rows.append((id_, pinned, sorted(k for k in kinds if k), sol_runs))
        print(f"### {id_}")
        print(f"- base image pinned by digest: {pinned} ({', '.join(froms)})")
        for run in ["nop", "safe", "unsafe"] + sol_runs:
            if (res / run).exists():
                print(f"- {run}: {run_summary(res / run)}")
        print(f"- test kinds present: {sorted(k for k in kinds if k)}")
        print()
    print("| env | digest pinned | test kinds | rollouts |")
    print("|---|---|---|---|")
    for id_, pinned, kinds, sols in rows:
        print(f"| {id_} | {pinned} | {', '.join(kinds)} | {', '.join(sols) or '-'} |")


if __name__ == "__main__":
    sys.exit(main())
