"""Black-box tests: run the feedsync CLI against dev/feedstub.py with a throwaway catalog."""
import json
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
STUB = REPO / "dev" / "feedstub.py"


def upsert(seq, sku, title, price):
    return {"seq": seq, "op": "upsert", "sku": sku, "title": title, "price": price, "currency": "EUR"}


def delete(seq, sku):
    return {"seq": seq, "op": "delete", "sku": sku}


# page_size 5 -> windows (0,5] (5,10] (10,15] tombstones only, (15,20] compacted/empty, (20,21]
BATCH_1 = [upsert(1, "T-001", "Hinge", "4.35"), upsert(2, "T-002", "Bracket", "19.99"),
           upsert(3, "T-003", "Tap", "12.00"), upsert(4, "T-001", "Hinge", "4.29"),
           upsert(7, "T-004", "Padlock", "0.29"), delete(11, "T-003"), delete(12, "T-002"),
           upsert(21, "T-005", "Rail", "8.58")]
BATCH_2 = [upsert(30, "T-004", "Padlock", "0.57"), delete(33, "T-001"), upsert(35, "T-006", "Clip", "15.99")]


class SyncTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.data = self.tmp / "feed"
        self.data.mkdir()
        self.write_batch("changes_1.jsonl", BATCH_1)
        self.log = self.tmp / "requests.log"
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        self.stub = subprocess.Popen([sys.executable, str(STUB), "--port", str(port), "--data",
                                      str(self.data), "--log", str(self.log)], stdout=subprocess.DEVNULL)
        for _ in range(50):
            try:
                socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
                break
            except OSError:
                time.sleep(0.1)
        self.db = self.tmp / "catalog.db"
        self.config = self.tmp / "feedsync.toml"
        self.config.write_text(f'[feed]\nurl = "http://127.0.0.1:{port}"\npage_size = 5\n\n'
                               f'[catalog]\npath = "{self.db}"\n')

    def tearDown(self):
        self.stub.terminate()
        self.stub.wait()

    def write_batch(self, name, events):
        (self.data / name).write_text("".join(json.dumps(e) + "\n" for e in events))

    def cli(self, *args):
        env = {k: v for k, v in os.environ.items() if k not in ("FEED_URL", "FEEDSYNC_DB")}
        proc = subprocess.run([sys.executable, "-m", "feedsync", "--config", str(self.config), *args],
                              cwd=REPO, env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout

    def catalog(self):
        with sqlite3.connect(self.db) as conn:
            return conn.execute("SELECT sku, price_cents FROM products ORDER BY sku").fetchall()

    def requests(self):
        lines = self.log.read_text().splitlines() if self.log.exists() else []
        return [json.loads(line) for line in lines if '"/v2/changes"' in line]

    def test_first_sync_matches_feed(self):
        self.cli("sync")
        self.assertEqual(self.catalog(), [("T-001", 429), ("T-004", 29), ("T-005", 858)])

    def test_second_sync_is_incremental(self):
        self.cli("sync")
        first = self.requests()
        self.write_batch("changes_2.jsonl", BATCH_2)
        self.cli("sync")
        second = self.requests()[len(first):]
        self.assertTrue(second, "second run made no requests")
        self.assertEqual(second[0]["cursor"], first[-1]["next_cursor"])
        self.assertFalse({r["cursor"] for r in second} & {r["cursor"] for r in first})
        self.assertEqual(self.catalog(), [("T-004", 57), ("T-005", 858), ("T-006", 1599)])

    def test_report_effective_prices(self):
        self.cli("sync")
        with sqlite3.connect(self.db) as conn:
            conn.execute("INSERT INTO price_overrides (sku, override_cents, starts_on, ends_on, author, "
                         "reason, created_at) VALUES ('T-005', 799, '2024-01-01', NULL, 'merch/test', "
                         "'promo', '2026-01-01'), ('T-004', 19, '2024-01-01', '2024-02-01', "
                         "'merch/test', 'old promo', '2026-01-01')")
        rows = {r["sku"]: r for r in json.loads(self.cli("report", "--json"))}
        self.assertEqual(sorted(rows), ["T-001", "T-004", "T-005"])
        self.assertEqual((rows["T-005"]["effective_price"], rows["T-005"]["source"]), ("7.99", "override"))
        self.assertEqual((rows["T-004"]["effective_price"], rows["T-004"]["source"]), ("0.29", "feed"))


if __name__ == "__main__":
    unittest.main()
