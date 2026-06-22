#!/usr/bin/env python3
"""Local server for the AE Cockpit.

  GET  /                      -> the cockpit UI (fetches /api/data)
  GET  /api/data?rep=grant    -> cached payload (assembles full on cold start)
  POST /api/refresh?rep&full  -> re-pull. full=0: HubSpot-only (fast). full=1: + Gong + AI.
  GET  /api/health

Run:  quinn-os/.venv/bin/python3 serve.py     (or use ./run)
"""
import json, os, sys, time, threading, urllib.parse, gzip
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import load_env, CACHE_DIR
load_env()
import assemble, ui, tasks

LOCK = threading.Lock()
PORT = int(os.environ.get("COCKPIT_PORT", "8787"))
# Bind to all interfaces so the cockpit is reachable from another machine over
# the LAN or (privately) over Tailscale — not just localhost on the Mac mini.
HOST = os.environ.get("COCKPIT_HOST", "0.0.0.0")
DEFAULT_REP = os.environ.get("COCKPIT_REP", "grant")

def cached_payload(rep):
    p = os.path.join(CACHE_DIR, f"payload-{rep}.json")
    if os.path.exists(p):
        pl = json.load(open(p))
        # Backfill the SalesOS Task Inbox for cached payloads written before
        # tasks.py existed (heuristic, derived on the fly — no writes, no refetch).
        if "inbox" not in pl:
            try:
                pl["inbox"] = tasks.grouped(pl)
            except Exception:
                pl["inbox"] = {"tasks": [], "buckets": {"overdue": [], "today": [], "upcoming": []},
                               "counts": {"overdue": 0, "today": 0, "upcoming": 0}, "total": 0,
                               "heuristic": True}
        return pl
    with LOCK:
        return assemble.assemble(rep, full=True)

class H(BaseHTTPRequestHandler):
    # HTTP/1.1 keep-alive: large responses (the ~830KB payload) transfer far more
    # reliably across a Tailscale/LAN hop than HTTP/1.0's close-after-each-response.
    # Safe because _send always sets an accurate Content-Length.
    protocol_version = "HTTP/1.1"

    def _send(self, code, body, ctype="application/json"):
        b = body.encode() if isinstance(body, str) else body
        # gzip when the client accepts it and the body is worth compressing.
        # Shrinks the ~830KB JSON payload ~7x so it survives marginal links
        # (e.g. an MTU-limited Wi-Fi/Tailscale path) and loads much faster.
        enc = None
        if len(b) > 1400 and "gzip" in (self.headers.get("Accept-Encoding") or ""):
            b = gzip.compress(b, 6); enc = "gzip"
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        if enc:
            self.send_header("Content-Encoding", enc)
            self.send_header("Vary", "Accept-Encoding")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)
    def log_message(self, *a): pass

    def do_GET(self):
        u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query)
        rep = (q.get("rep") or [DEFAULT_REP])[0]
        if u.path in ("/", ""):
            self._send(200, ui.html(rep), "text/html; charset=utf-8")
        elif u.path == "/api/data":
            self._send(200, json.dumps(cached_payload(rep), default=str))
        elif u.path == "/api/health":
            self._send(200, json.dumps({"ok": True}))
        else:
            self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query)
        rep = (q.get("rep") or [DEFAULT_REP])[0]
        full = (q.get("full") or ["0"])[0] == "1"
        if u.path == "/api/refresh":
            t = time.time()
            try:
                with LOCK:
                    pl = assemble.assemble(rep, full=full, log=lambda *a: None)
                self._send(200, json.dumps({"ok": True, "took": round(time.time()-t, 1), "payload": pl}, default=str))
            except Exception as e:
                self._send(500, json.dumps({"ok": False, "error": str(e)[:300]}))
        else:
            self._send(404, json.dumps({"error": "not found"}))

if __name__ == "__main__":
    print(f"SalesOS Cockpit  →  http://localhost:{PORT}/?rep={DEFAULT_REP}  (binding {HOST})")
    print("Ctrl-C to stop.")
    ThreadingHTTPServer((HOST, PORT), H).serve_forever()
