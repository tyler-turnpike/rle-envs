"""Index storage: JSON-lines shards under var/index/.

Each line is one index row (see reindex.transform).  The search service loads every
`shard-*.jsonl` file in the directory; shard boundaries carry no meaning.  Rows are
buffered and written out in blocks (one write + fsync per block) because the index
volume is network storage in production and small appends are slow there.
"""
import json
import os
from pathlib import Path

SHARD_ROWS = 1000      # rows per shard file before rotating
BUFFER_ROWS = 200      # rows held in memory before a block write


def shard_paths(index_dir):
    return sorted(Path(index_dir).glob("shard-*.jsonl"))


def iter_rows(index_dir):
    for path in shard_paths(index_dir):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    yield json.loads(line)


class ShardWriter:
    def __init__(self, index_dir, shard_rows=SHARD_ROWS, buffer_rows=BUFFER_ROWS):
        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.shard_rows = shard_rows
        self.buffer_rows = buffer_rows
        self._buffer = []
        self._fh = None
        self._rows_in_shard = 0
        self._next_shard = self._first_free_shard()

    def _first_free_shard(self):
        numbers = [int(p.stem.split("-", 1)[1]) for p in shard_paths(self.index_dir)]
        return max(numbers) + 1 if numbers else 0

    @property
    def pending(self):
        return len(self._buffer)

    def reset(self):
        """Drop every shard (used when a reindex starts from scratch)."""
        self._close_shard()
        for path in shard_paths(self.index_dir):
            path.unlink()
        self._next_shard = 0

    def add(self, row):
        self._buffer.append(row)
        if len(self._buffer) >= self.buffer_rows:
            self.flush()

    def flush(self):
        if not self._buffer:
            return
        for row in self._buffer:
            if self._fh is None or self._rows_in_shard >= self.shard_rows:
                self._rotate()
            self._fh.write(json.dumps(row, sort_keys=True, separators=(",", ":"),
                                      ensure_ascii=False) + "\n")
            self._rows_in_shard += 1
        self._fh.flush()
        os.fsync(self._fh.fileno())
        self._buffer.clear()

    def _rotate(self):
        self._close_shard()
        path = self.index_dir / ("shard-%05d.jsonl" % self._next_shard)
        self._fh = open(path, "a", encoding="utf-8")
        self._next_shard += 1
        self._rows_in_shard = 0

    def _close_shard(self):
        if self._fh is not None:
            self._fh.close()
            self._fh = None

    def close(self):
        self.flush()
        self._close_shard()
