#!/usr/bin/env python3
"""Local server for the AE Cockpit.

  GET  /                      -> the cockpit UI (fetches /api/data)
  GET  /api/data?rep=grant    -> cached payload (assembles full on cold start)
  POST /api/refresh?rep&full  -> re-pull. full=0: HubSpot-only (fast). full=1: + Gong + AI.
  GET  /api/health

Run:  quinn-os/.venv/bin/python3 serve.py     (or use ./run)
"""
import json, os, sys, time, threading, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import load_env, CACHE_DIR
load_env()
import assemble, ui

LOCK = threading.Lock()
PORT = int(os.environ.get("COCKPIT_PORT", "8787"))
DEFAULT_REP = os.environ.get("COCKPIT_REP", "grant")

def cached_payload(rep):
    p = os.path.join(CACHE_DIR, f"payload-{rep}.json")
    if os.path.exists(p):
        return json.load(open(p))
    with LOCK:
        return assemble.assemble(rep, full=True)

class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
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
    print(f"AE Cockpit  →  http://localhost:{PORT}/?rep={DEFAULT_REP}")
    print("Ctrl-C to stop.")
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
