"""HTTP client for the supplier's v2 delta feed (docs/feed_api.md)."""
import json
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import ProxyHandler, Request, build_opener

REPO = Path(__file__).resolve().parent.parent
LOCAL_HOSTS = {"127.0.0.1", "localhost"}


class FeedError(RuntimeError):
    pass


class FeedClient:
    def __init__(self, base_url, page_size=25, timeout=10.0):
        self.base_url = base_url.rstrip("/")
        self.page_size = page_size
        self.timeout = timeout
        self._opener = build_opener(ProxyHandler({}))

    def get_changes(self, cursor=None):
        params = {"limit": self.page_size}
        if cursor:
            params["cursor"] = cursor
        url = f"{self.base_url}/v2/changes?{urlencode(params)}"
        req = Request(url, headers={"Accept": "application/json", "User-Agent": "feedsync/0.4"})
        try:
            with self._opener.open(req, timeout=self.timeout) as resp:
                return json.load(resp)
        except HTTPError as exc:
            raise FeedError(f"GET {url} -> HTTP {exc.code}: {exc.read()[:300]!r}") from exc
        except (URLError, OSError) as exc:
            raise FeedError(f"GET {url} failed: {exc}") from exc

    def iter_pages(self, cursor=None):
        """Yield delta pages starting after `cursor` until the feed reports has_more=false."""
        while True:
            page = self.get_changes(cursor)
            yield page
            if not page.get("has_more"):
                return
            cursor = page["next_cursor"]


def _listening(host, port):
    try:
        socket.create_connection((host, port), timeout=0.5).close()
        return True
    except OSError:
        return False


def ensure_local_feed(base_url, wait=5.0):
    """Start dev/feedstub.py when the feed URL points at this machine and nothing listens there."""
    parts = urlsplit(base_url)
    host, port = parts.hostname, parts.port or 80
    if host not in LOCAL_HOSTS or _listening(host, port):
        return False
    stub = REPO / "dev" / "feedstub.py"
    if not stub.exists():
        raise FeedError(f"nothing listening on {base_url} and {stub} is missing")
    Path("/var/tmp/feedstub").mkdir(parents=True, exist_ok=True)
    with open("/var/tmp/feedstub/stub.out", "a") as out:
        subprocess.Popen([sys.executable, str(stub), "--port", str(port)], stdout=out,
                         stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        if _listening(host, port):
            return True
        time.sleep(0.1)
    raise FeedError(f"started {stub} but {base_url} is still not answering")
