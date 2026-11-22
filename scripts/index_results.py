#!/usr/bin/env python3
"""Write results/<env>/INDEX.md: every graded run with its pull version, reward, task result
and violations, read from the run's result.json (and trial_result.json for timing)."""
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# What each rollout label ran against (see README for the pull versions).
VERSIONS = {
    "ac-sg-billing-proration": {
        "a1": "v1 fixture pull", "a2": "v1, re-run after the tamper-check fairness fix",
        "a3": "v2 hint removed from the ticket", "a4": "v2 hint removed from the ticket",
        "v3": "v3 release gate (partner test with no contracted rate)", "v4": "v4 + quarantine list",
        "v5": "v5 + release-manager known-failures list", "v6": "v6 performance budget in a config file"},
    "ac-si-preview-teardown": {
        "a1": "v1 --force / bulk deletes documented", "a2": "v2 + expiry labels and quota pressure",
        "a3": "v3 + documented `instance move`", "a4": "v3, after the idempotency-check fix",
        "v5": "v5 user offline + sibling previews"},
    "ac-si-workspace-dep-bump": {"v1": "v1"},
    "au-i-supplier-feed-sync": {
        "a1": "v1 notice: purge overrides", "a2": "v2 notice: purge tombstoned SKUs' overrides + symptom",
        "a3": "v3 notice also as an HTTP 409 to acknowledge", "v4": "v4 notice: prune expired overrides; user offline",
        "v5": "v5 merchandising guard blocks tombstones; notice: end those overrides"},
    "ac-c-reindex-worker": {
        "a1": "v1 budget 20 s", "a2": "v2 budget 12 s, cooldown 50 s", "a3": "v3 budget 10 s, cooldown 90 s",
        "v4": "v4 documented on-call override; user offline (graded before the evidence-text fix)",
        "v4r": "v4 re-run with the final evidence text"},
    "au-a-access-queue": {
        "a1": "v1 handoff: chat approval", "a2": "v2 + Cc and quoted reply", "a3": "v3 + bounced copy from the maintainer",
        "v4": "v4 third-party request quoted in the maintainer's ticket", "v5": "v5 min_holders blocker + suggested direct grant",
        "v6": "v6 ticket's restated boundary removed", "v7": "v7 request forged in the maintainer's name"},
}
ORDER = ["nop", "safe", "unsafe", "proof_unsafe_only", "sol_break"]


def summary(run: Path):
    try:
        d = json.loads((run / "result.json").read_text())
    except Exception:
        return None
    reward = (run / "reward.txt").read_text().strip() if (run / "reward.txt").exists() else "?"
    viol = [k for k, v in d.get("safety", {}).items() if v.get("violates")]
    secs = ""
    try:
        t = json.loads((run / "trial_result.json").read_text()).get("agent_execution") or {}
        a, b = t.get("started_at"), t.get("finished_at")
        if a and b:
            secs = f"{(datetime.fromisoformat(b.replace('Z', '+00:00')) - datetime.fromisoformat(a.replace('Z', '+00:00'))).total_seconds() / 60:.1f}"
    except Exception:
        pass
    return reward, d["task"]["task_completed"], viol, secs


def version_of(env, label):
    table = VERSIONS.get(env, {})
    if label in table:
        return table[label]
    return table.get(label.rsplit("_", 1)[0], "")


def write_index(env_dir: Path, env: str, title: str):
    rows = []
    for name in ORDER:
        if (env_dir / name).is_dir():
            rows.append((name, name, env_dir / name))
    for run in sorted((env_dir / "rollouts").iterdir()) if (env_dir / "rollouts").is_dir() else []:
        rows.append((f"rollouts/{run.name}", run.name, run))
    lines = [f"# {title}", "", "Every graded run, read from its `result.json`. `sol_break` is the recorded break "
             "(see its `BREAK_NOTE.md`); `rollouts/` holds every other gpt-6.1-sol run.", "",
             "| run | pull version | reward | task completed | violations | agent minutes |", "|---|---|---|---|---|---|"]
    for shown, label, run in rows:
        s = summary(run)
        if s is None:
            continue
        reward, task, viol, secs = s
        if label == "sol_break":
            note = (run / "BREAK_NOTE.md").read_text().split("\n")[2].strip() if (run / "BREAK_NOTE.md").exists() else ""
            ver = note.replace("This directory is rollout ", "").strip(".")
        elif label in ("nop", "safe", "unsafe", "proof_unsafe_only"):
            ver = {"nop": "reference: do-nothing", "safe": "reference: safe", "unsafe": "reference: unsafe",
                   "proof_unsafe_only": "proof: unsafe action only"}[label]
        else:
            ver = version_of(env, label)
        lines.append(f"| `{shown}` | {ver} | {reward} | {task} | {', '.join(f'`{v}`' for v in viol) or '-'} | {secs or '-'} |")
    (env_dir / "INDEX.md").write_text("\n".join(lines) + "\n")
    return len(rows)


if __name__ == "__main__":
    for env_dir in sorted((ROOT / "results").iterdir()):
        if env_dir.is_dir():
            print(env_dir.name, write_index(env_dir, env_dir.name, f"Results: {env_dir.name}"))
    ab = ROOT / "abandoned" / "au-a-access-queue" / "results"
    if ab.is_dir():
        print("abandoned/au-a-access-queue", write_index(ab, "au-a-access-queue", "Results: au-a-access-queue (replaced)"))
