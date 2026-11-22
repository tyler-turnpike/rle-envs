"""Reindex progress checkpoint (var/checkpoint.json)."""
import json
import logging
from pathlib import Path

log = logging.getLogger("reindex.checkpoint")


def fresh_state():
    # last_id: id of the last document handled; docs: documents indexed so far
    return {"last_id": 0, "docs": 0, "complete": False}


class Checkpoint:
    def __init__(self, path):
        self.path = Path(path)

    def load(self):
        try:
            data = json.loads(self.path.read_text())
        except FileNotFoundError:
            return fresh_state()
        except ValueError:
            log.warning("checkpoint %s unreadable, starting over", self.path)
            return fresh_state()
        state = fresh_state()
        state.update(data)
        return state

    def save(self, state):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w") as fh:
            json.dump(state, fh)

    def clear(self):
        self.path.unlink(missing_ok=True)
