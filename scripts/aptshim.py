# Local build-cache helper: forwards plain-HTTP apt requests as HTTPS through the host proxy.
# Only used by scripts/prime.sh on a build host whose proxy accepts HTTPS CONNECT only.
import http.server, socketserver, urllib.request, urllib.parse, sys
class H(http.server.BaseHTTPRequestHandler):
    def _go(self, head=False):
        u = urllib.parse.urlsplit(self.path)
        url = urllib.parse.urlunsplit(("https", u.netloc, u.path, u.query, ""))
        try:
            req = urllib.request.Request(url, method="HEAD" if head else "GET")
            for k in ("If-Modified-Since", "Range"):
                if self.headers.get(k): req.add_header(k, self.headers[k])
            with urllib.request.urlopen(req, timeout=120) as r:
                body = b"" if head else r.read()
                self.send_response(r.status)
                for k, v in r.getheaders():
                    if k.lower() in ("content-type", "last-modified", "content-range"): self.send_header(k, v)
                self.send_header("Content-Length", str(len(body)) if not head else r.headers.get("Content-Length", "0"))
                self.end_headers(); self.wfile.write(body)
        except urllib.error.HTTPError as e:
            self.send_response(e.code); self.send_header("Content-Length", "0"); self.end_headers()
        except Exception as e:
            self.send_response(502); self.send_header("Content-Length", "0"); self.end_headers()
    def do_GET(self): self._go()
    def do_HEAD(self): self._go(True)
    def log_message(self, *a): pass
class S(socketserver.ThreadingMixIn, http.server.HTTPServer): daemon_threads = True
S(("127.0.0.1", 3128), H).serve_forever()
