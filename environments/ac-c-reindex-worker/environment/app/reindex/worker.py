"""Reindex worker: data/docs.db -> var/index/shard-*.jsonl.

Normally started by `make reindex` (ops/supervise.py runs it inside the job budget).
Progress is kept in var/checkpoint.json so the next run continues where the last
one stopped; a run with no checkpoint rebuilds the index from scratch.

    python3 -m reindex.worker            run / resume
    python3 -m reindex.worker --status   print progress
"""
import argparse
import logging
import sys
import time
from pathlib import Path

from reindex.checkpoint import Checkpoint
from reindex.source import Source
from reindex.store import ShardWriter, iter_rows
from reindex.transform import transform_doc

ROOT = Path(__file__).resolve().parent.parent
BATCH_SIZE = 25

log = logging.getLogger("reindex.worker")


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="reindex.worker")
    parser.add_argument("--source", default=str(ROOT / "data" / "docs.db"))
    parser.add_argument("--index-dir", default=str(ROOT / "var" / "index"))
    parser.add_argument("--checkpoint", default=str(ROOT / "var" / "checkpoint.json"))
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    parser.add_argument("--status", action="store_true", help="print progress and exit")
    return parser.parse_args(argv)


def show_status(args):
    state = Checkpoint(args.checkpoint).load()
    source = Source(args.source)
    total = source.count()
    source.close()
    rows = list(iter_rows(args.index_dir)) if Path(args.index_dir).exists() else []
    unique = len({row["id"] for row in rows})
    print("checkpoint : %s" % state)
    print("source     : %d live docs" % total)
    print("index      : %d rows, %d unique ids (%.1f%% of source)"
          % (len(rows), unique, 100.0 * unique / max(total, 1)))
    return 0


def run(args):
    ckpt = Checkpoint(args.checkpoint)
    state = ckpt.load()
    if state["complete"]:
        log.info("index already complete (%d docs)", state["docs"])
        return 0
    source = Source(args.source)
    store = ShardWriter(args.index_dir)
    if state["last_id"] == 0:
        log.info("no checkpoint: rebuilding index from scratch")
        store.reset()
    total = source.count()
    started = time.monotonic()
    log.info("starting after id %d (%d/%d docs done)", state["last_id"], state["docs"], total)

    for n, batch in enumerate(source.batches(start_id=state["last_id"], size=args.batch_size), 1):
        for doc in batch:
            store.add(transform_doc(doc))
        state["last_id"] = batch[-1].id
        state["docs"] += len(batch)
        ckpt.save(state)
        if n % 20 == 0:
            rate = n * args.batch_size / (time.monotonic() - started)
            log.info("progress: last_id=%d docs=%d/%d (%.0f docs/s)",
                     state["last_id"], state["docs"], total, rate)

    store.close()
    state["complete"] = True
    ckpt.save(state)
    source.close()
    log.info("reindex complete: %d docs", state["docs"])
    return 0


def main(argv=None):
    logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.status:
        return show_status(args)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
