import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from reindex.source import Doc, Source, generate_corpus  # noqa: E402
from reindex.store import ShardWriter, iter_rows, shard_paths  # noqa: E402
from reindex.transform import transform_doc  # noqa: E402


class TransformTest(unittest.TestCase):
    def test_golden_row(self):
        row = transform_doc(Doc(7, "Café Über Zürich", "The naïve résumé of the façade. Café café!", "fr"))
        self.assertEqual(row["slug"], "cafe-uber-zurich")
        self.assertEqual(row["terms"], ["cafe", "facade", "naive", "resume", "uber", "zurich"])
        self.assertEqual(row["length"], 8)
        self.assertEqual(row["checksum"], "fbe4334594f1a63f211e2742efb9681a")
        self.assertEqual(row["minhash"][:4], [51805901, 103584590, 473029234, 2680140])
        self.assertEqual(len(row["minhash"]), 64)

    def test_empty_body(self):
        row = transform_doc(Doc(1, "Untitled", "", "en"))
        self.assertEqual(row["length"], 1)
        self.assertEqual(len(row["minhash"]), 64)


class StoreTest(unittest.TestCase):
    def test_rows_round_trip_across_shards(self):
        with tempfile.TemporaryDirectory() as tmp:
            writer = ShardWriter(tmp, shard_rows=4, buffer_rows=3)
            for i in range(10):
                writer.add({"id": i})
            writer.close()
            self.assertEqual([r["id"] for r in iter_rows(tmp)], list(range(10)))
            self.assertEqual(len(shard_paths(tmp)), 3)


class ResumeTest(unittest.TestCase):
    def _worker(self, tmp):
        return [sys.executable, "-m", "reindex.worker", "--source", str(tmp / "docs.db"),
                "--index-dir", str(tmp / "index"), "--checkpoint", str(tmp / "ckpt.json")]

    def test_stop_and_resume_gives_complete_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            generate_corpus(tmp / "docs.db", count=400, seed=5)
            proc = subprocess.Popen(self._worker(tmp), cwd=ROOT, stderr=subprocess.DEVNULL)
            time.sleep(1.5)
            proc.send_signal(signal.SIGTERM)
            proc.wait(timeout=10)
            subprocess.run(self._worker(tmp), cwd=ROOT, check=True, timeout=120,
                           stderr=subprocess.DEVNULL)
            ids = [row["id"] for row in iter_rows(tmp / "index")]
            source = Source(tmp / "docs.db")
            expected = [d.id for batch in source.batches(0, 100) for d in batch]
            source.close()
            self.assertEqual(len(ids), len(set(ids)), "duplicate rows in index")
            self.assertEqual(sorted(ids), expected)


if __name__ == "__main__":
    unittest.main()
