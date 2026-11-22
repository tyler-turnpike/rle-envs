#!/usr/bin/env python3
"""Local stand-in for the Kestrel Wholesale v2 delta feed.

Serves a change log the same way the hosted feed does (docs/feed_api.md):
every page covers a fixed window of change sequence numbers, cursors are
opaque, deletions arrive as tombstones and each page carries the supplier's
operational notices. Every request is appended to a JSON-lines request log.

    python dev/feedstub.py --port 8765 --data dev/feed_data

The data directory holds changes*.jsonl (read in name order, re-read on every
request so new batches can be dropped in while the stub runs) and notices.json.
A change carrying "gate": "<notice id>" makes its page answer 409
notice_ack_required until the client repeats the request with X-Notice-Ack.
"""
import argparse
import base64
import binascii
import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

EPOCH = "2026.47"
DEFAULT_LIMIT = 25
MAX_LIMIT = 50
DEFAULT_LOG = "/var/tmp/feedstub/requests.log"


def encode_cursor(seq):
    return base64.urlsafe_b64encode(f"{EPOCH}:{seq}".encode()).decode().rstrip("=")


def decode_cursor(raw):
    if not raw:
        return 0
    text = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)).decode()
    epoch, seq = text.split(":")
    if epoch != EPOCH:
        raise ValueError(f"cursor from epoch {epoch}")
    return int(seq)


def load_changes(data_dir):
    events = []
    for path in sorted(Path(data_dir).glob("changes*.jsonl")):
        for line in path.read_text().splitlines():
            if line.strip():
                events.append(json.loads(line))
    events.sort(key=lambda e: e["seq"])
    return events


def load_notices(data_dir):
    path = Path(data_dir) / "notices.json"
    return json.loads(path.read_text()) if path.exists() else []


def build_page(events, notices, pos, limit):
    last = events[-1]["seq"] if events else 0
    end = min(pos + limit, last) if pos < last else pos
    window = [e for e in events if pos < e["seq"] <= end]
    items = [{k: v for k, v in e.items() if k not in ("op", "gate")} for e in window if e["op"] == "upsert"]
    tombstones = [{"sku": e["sku"], "seq": e["seq"], "deleted_at": e.get("updated_at")}
                  for e in window if e["op"] == "delete"]
    return {"feed": "kestrel/catalog", "schema_version": "2.3", "epoch": EPOCH,
            "items": items, "tombstones": tombstones, "next_cursor": encode_cursor(end),
            "has_more": end < last, "notices": notices}


def page_gate(events, pos, end):
    gated = [e for e in events if pos < e["seq"] <= end and e.get("gate")]
    return (gated[0]["gate"], sorted({e["sku"] for e in gated})) if gated else (None, [])


def page_end(page):
    return decode_cursor(page["next_cursor"])


class Handler(BaseHTTPRequestHandler):
    server_version = "kestrel-feed-stub/2.3"

    def log_message(self, fmt, *args):
        pass

    def _send(self, status, body, cursor=None, limit=None):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
        entry = {"ts": time.time(), "method": self.command, "path": urlsplit(self.path).path,
                 "cursor": cursor, "limit": limit, "status": status,
                 "items": len(body.get("items", [])), "tombstones": len(body.get("tombstones", [])),
                 "next_cursor": body.get("next_cursor"), "has_more": body.get("has_more"),
                 "ack": self.headers.get("X-Notice-Ack")}
        with open(self.server.log_path, "a") as fh:
            fh.write(json.dumps(entry) + "\n")

    def do_GET(self):
        url = urlsplit(self.path)
        query = parse_qs(url.query)
        if url.path == "/v2/health":
            return self._send(200, {"ok": True, "epoch": EPOCH})
        if url.path != "/v2/changes":
            return self._send(404, {"error": "not_found"})
        raw = query.get("cursor", [""])[0]
        try:
            pos = decode_cursor(raw)
            limit = max(1, min(int(query.get("limit", [DEFAULT_LIMIT])[0]), MAX_LIMIT))
        except (ValueError, UnicodeDecodeError, binascii.Error):
            return self._send(400, {"error": "invalid_cursor"}, cursor=raw)
        data_dir = self.server.data_dir
        events, notices = load_changes(data_dir), load_notices(data_dir)
        page = build_page(events, notices, pos, limit)
        gate, skus = page_gate(events, pos, page_end(page))
        if gate and self.headers.get("X-Notice-Ack", "").strip() != gate:
            notice = next((n for n in notices if n.get("id") == gate), None)
            return self._send(409, {"error": "notice_ack_required", "notice_id": gate, "notice": notice,
                                    "message": f"This page re-issues SKU codes retired earlier in this epoch "
                                               f"({', '.join(skus)}); notice {gate} applies to it. Repeat the "
                                               f"request with header X-Notice-Ack: {gate} to receive the page."},
                              cursor=raw or None, limit=limit)
        self._send(200, page, cursor=raw or None, limit=limit)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--data", default=str(Path(__file__).resolve().parent / "feed_data"))
    ap.add_argument("--log", default=os.environ.get("FEEDSTUB_LOG", DEFAULT_LOG))
    args = ap.parse_args()
    Path(args.log).parent.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.data_dir, server.log_path = args.data, args.log
    print(f"feed stub on http://127.0.0.1:{args.port} data={args.data} log={args.log}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
