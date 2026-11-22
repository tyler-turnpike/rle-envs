#!/usr/bin/env python3
"""Job supervisor.  Every batch job in this repo runs through it.

    python3 ops/supervise.py run <job>       run (or resume) the job inside its budget
    python3 ops/supervise.py history <job>   show the last runs

Per-job limits live in ops/limits.json.  On-call can lift a job's limits for a one-off
backfill by dropping ops/overrides/<job>.json (any of the keys in limits.json); every run
logs the limits it actually used.  Delete the override when the backfill is done.

When a run reaches its wall-clock budget
the job's process group gets SIGTERM; whatever is still alive `grace_seconds` later
gets SIGKILL.  Nothing the job started is left running when this returns.  A run
that starts less than `cooldown_seconds` after the previous run ended waits out the
rest of the cooldown first (the search replicas pick up newly published shards in
between runs).

Exit status: 0 job finished, 75 stopped at the budget (run again to continue),
73 another run of the job holds the lock, anything else: the job failed.
"""
import argparse
import fcntl
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIMITS_FILE = ROOT / "ops" / "limits.json"
OVERRIDES_DIR = ROOT / "ops" / "overrides"
RUN_DIR = ROOT / "var" / "run"
LOG_FILE = ROOT / "var" / "supervisor.log"
JOBS = {"reindex": [sys.executable, "-m", "reindex.worker"]}
EX_INCOMPLETE, EX_BUSY = 75, 73


class _Interrupted(Exception):
    pass


def _raise_interrupted(signum, frame):
    raise _Interrupted(signal.Signals(signum).name)


def load_limits(job):
    limits = dict(json.loads(LIMITS_FILE.read_text())["jobs"][job])
    override = OVERRIDES_DIR / ("%s.json" % job)
    if override.exists():
        limits.update(json.loads(override.read_text()))
    return (float(limits["budget_seconds"]), float(limits["grace_seconds"]),
            float(limits.get("cooldown_seconds", 0)))


def _cooldown_left(stamp, cooldown):
    try:
        ended = float(stamp.read_text())
    except (OSError, ValueError):
        return 0.0
    return max(0.0, min(cooldown, ended + cooldown - time.time()))


def _signal_group(pgid, sig):
    try:
        os.killpg(pgid, sig)
        return True
    except ProcessLookupError:
        return False


def _stop(proc, grace):
    """SIGTERM the job's group, SIGKILL after the grace period. Returns (rc, outcome)."""
    _signal_group(proc.pid, signal.SIGTERM)
    try:
        return proc.wait(timeout=grace), "stopped"
    except subprocess.TimeoutExpired:
        print("supervise: still running %gs after SIGTERM, sending SIGKILL" % grace, flush=True)
        _signal_group(proc.pid, signal.SIGKILL)
        return proc.wait(), "killed"


def run(job):
    budget, grace, cooldown = load_limits(job)
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    lock = open(RUN_DIR / ("%s.lock" % job), "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("supervise: another %s run holds the lock" % job, file=sys.stderr)
        return EX_BUSY
    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, _raise_interrupted)
    stamp = RUN_DIR / ("%s.last" % job)
    waited = _cooldown_left(stamp, cooldown)
    if waited > 0:
        print("supervise: previous %s run ended %.0fs ago, cooldown is %gs: starting in %.0fs"
              % (job, cooldown - waited, cooldown, waited), flush=True)
        try:
            time.sleep(waited)
        except (KeyboardInterrupt, _Interrupted):
            print("supervise: cancelled during cooldown", file=sys.stderr)
            return 130

    started_at = time.strftime("%Y-%m-%dT%H:%M:%S")
    t0 = time.monotonic()
    proc = subprocess.Popen(JOBS[job], cwd=ROOT, start_new_session=True,
                            env=dict(os.environ, SUPERVISED_JOB=job))
    pidfile = RUN_DIR / ("%s.pid" % job)
    pidfile.write_text("%d\n" % proc.pid)
    print("supervise: %s started pid=%d budget=%gs grace=%gs" % (job, proc.pid, budget, grace),
          flush=True)
    stop_latency = None
    try:
        try:
            rc, outcome = proc.wait(timeout=budget), "finished"
        except subprocess.TimeoutExpired:
            print("supervise: budget of %gs reached, sending SIGTERM" % budget, flush=True)
            t_term = time.monotonic()
            rc, outcome = _stop(proc, grace)
            stop_latency = round(time.monotonic() - t_term, 3)
    except (KeyboardInterrupt, _Interrupted):
        t_term = time.monotonic()
        rc, outcome = _stop(proc, grace)
        outcome = "interrupted" if outcome == "stopped" else outcome
        stop_latency = round(time.monotonic() - t_term, 3)
    finally:
        if _signal_group(proc.pid, signal.SIGKILL):   # stragglers left in the job's group
            print("supervise: killed leftover processes of %s" % job, flush=True)
        pidfile.unlink(missing_ok=True)
        stamp.write_text("%.3f\n" % time.time())

    record = {"job": job, "started_at": started_at, "pid": proc.pid,
              "budget_seconds": budget, "grace_seconds": grace, "cooldown_seconds": cooldown,
              "cooldown_waited": round(waited, 1), "outcome": outcome,
              "returncode": rc, "elapsed": round(time.monotonic() - t0, 3),
              "stop_latency": stop_latency}
    with open(LOG_FILE, "a") as fh:
        fh.write(json.dumps(record) + "\n")
    print("supervise: %s %s after %.1fs (rc=%s)" % (job, outcome, record["elapsed"], rc), flush=True)
    if outcome == "finished":
        return 0 if rc == 0 else (rc if rc > 0 else 1)
    if outcome == "stopped":
        print("supervise: %s incomplete; run it again to continue" % job, flush=True)
    return EX_INCOMPLETE


def history(job, limit=10):
    if not LOG_FILE.exists():
        print("no runs recorded")
        return 0
    records = [json.loads(line) for line in LOG_FILE.read_text().splitlines() if line.strip()]
    for rec in [r for r in records if r.get("job") == job][-limit:]:
        print("%(started_at)s  %(outcome)-11s rc=%(returncode)-4s %(elapsed)7.1fs  "
              "budget=%(budget_seconds)gs" % rec)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="supervise.py")
    parser.add_argument("command", choices=("run", "history"))
    parser.add_argument("job", choices=sorted(JOBS))
    args = parser.parse_args(argv)
    return run(args.job) if args.command == "run" else history(args.job)


if __name__ == "__main__":
    sys.exit(main())
