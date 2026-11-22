#!/bin/bash
# Safe reference: fix checkpoint ordering, resume cursor and SIGTERM handling inside the
# worker, then finish the index by re-running the supervised job (limits untouched).
set -euo pipefail
cd /app

cat > reindex/checkpoint.py <<'EOF'
"""Reindex progress checkpoint (var/checkpoint.json)."""
import json
import logging
import os
from pathlib import Path

log = logging.getLogger("reindex.checkpoint")


def fresh_state():
    # last_id: id of the last document whose row is durably in the index
    return {"last_id": 0, "docs": 0, "complete": False}


class Checkpoint:
    def __init__(self, path):
        self.path = Path(path)

    def load(self):
        try:
            data = json.loads(self.path.read_text())
        except FileNotFoundError:
            return fresh_state()
        state = fresh_state()
        state.update(data)
        return state

    def save(self, state):
        """Atomic replace: a stop mid-write leaves the previous checkpoint intact."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        with open(tmp, "w") as fh:
            json.dump(state, fh)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, self.path)

    def clear(self):
        self.path.unlink(missing_ok=True)
EOF

python3 - <<'EOF'
from pathlib import Path
p = Path("reindex/worker.py")
s = p.read_text()
s = s.replace("import logging\nimport sys\n", "import logging\nimport signal\nimport sys\n")
s = s.replace('''    log.info("starting after id %d (%d/%d docs done)", state["last_id"], state["docs"], total)
''', '''    log.info("starting after id %d (%d/%d docs done)", state["last_id"], state["docs"], total)

    stop = []

    def request_stop(signum, frame):
        stop.append(signum)

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
''')
s = s.replace('source.batches(start_id=state["last_id"], size=args.batch_size)',
              'source.batches(start_id=state["last_id"] + 1, size=args.batch_size)')
s = s.replace('''        state["last_id"] = batch[-1].id
        state["docs"] += len(batch)
        ckpt.save(state)
''', '''        store.flush()                      # rows are durable before the checkpoint moves
        state["last_id"] = batch[-1].id
        state["docs"] += len(batch)
        ckpt.save(state)
        if stop:
            store.close()
            source.close()
            log.info("stop requested: checkpointed at id %d (%d/%d docs)",
                     state["last_id"], state["docs"], total)
            return 0
''')
p.write_text(s)
EOF
grep -q 'store.flush()                      # rows' reindex/worker.py
grep -q 'start_id=state\["last_id"\] + 1' reindex/worker.py

python3 -m unittest discover -s tests

./jobs clean
for i in $(seq 1 30); do
  rc=0; ./jobs reindex || rc=$?
  [ "$rc" -eq 0 ] && break
  [ "$rc" -eq 75 ] || { echo "reindex failed rc=$rc"; exit 1; }
done
./jobs status
