"""Gong client — pulls calls + transcripts FRESH from api.gong.io (not QuinnOS's mirror).

Calls are matched to a HubSpot deal by the email domain of external participants
(the reliable join), optionally aided by Gong's own CRM context when present.
"""
import os, time, datetime, requests
from requests.auth import HTTPBasicAuth

BASE = "https://api.gong.io"

def _auth():
    return HTTPBasicAuth(os.environ["GONG_ACCESS_KEY"], os.environ["GONG_SECRET"])

def _req(method, path, **kw):
    for attempt in range(5):
        r = requests.request(method, f"{BASE}{path}", auth=_auth(), timeout=60, **kw)
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(1.5 * (attempt + 1)); continue
        r.raise_for_status()
        return r.json() if r.content else {}
    r.raise_for_status()

def find_user(email):
    data = _req("GET", "/v2/users")
    for u in data.get("users", []):
        if (u.get("emailAddress") or "").lower() == email.lower():
            return u["id"]
    return None

def calls_for_user(user_id, days=180):
    """Calls hosted/primary by this user in the window, with parties + CRM context."""
    to = datetime.datetime.now(datetime.timezone.utc)
    frm = to - datetime.timedelta(days=days)
    body = {
        "filter": {"fromDateTime": frm.strftime("%Y-%m-%dT%H:%M:%SZ"),
                   "toDateTime": to.strftime("%Y-%m-%dT%H:%M:%SZ"),
                   "primaryUserIds": [user_id]},
        "contentSelector": {"context": "Extended", "exposedFields": {"parties": True}},
    }
    out, cursor = [], None
    while True:
        b = dict(body)
        if cursor: b["cursor"] = cursor
        data = _req("POST", "/v2/calls/extensive", json=b)
        out.extend(data.get("calls", []))
        cursor = (data.get("records", {}) or {}).get("cursor")
        if not cursor: break
    return out

def transcripts(call_ids):
    """{call_id: [ {speakerId, sentences:[{text,start}]} ]} in batches of 100."""
    out = {}
    ids = [str(c) for c in call_ids]
    for i in range(0, len(ids), 100):
        batch = ids[i:i+100]
        data = _req("POST", "/v2/calls/transcript", json={"filter": {"callIds": batch}})
        for t in data.get("callTranscripts", []):
            out[str(t["callId"])] = t.get("transcript", [])
    return out

PERSONAL = {"gmail.com","outlook.com","hotmail.com","yahoo.com","icloud.com","aol.com"}
# Quinn's own domains — Gong's workspace internal domain is lunapark.com, so meetquinn.ai
# addresses (Arlen etc.) are mis-tagged "External". Never treat these as the prospect.
INTERNAL = {"meetquinn.ai","lunapark.com","quinn.ai"}

def _prospect_domain(email):
    if "@" not in (email or ""): return None
    d = email.split("@")[-1].lower()
    return None if (d in PERSONAL or d in INTERNAL) else d

def external_domains(call):
    doms = set()
    for p in call.get("parties", []) or []:
        if p.get("affiliation") == "External":
            d = _prospect_domain(p.get("emailAddress") or "")
            if d: doms.add(d)
    return doms

def external_parties(call):
    out = []
    for p in call.get("parties", []) or []:
        em = (p.get("emailAddress") or "")
        dom = em.split("@")[-1].lower() if "@" in em else ""
        if p.get("affiliation") == "External" and dom not in INTERNAL and (p.get("name") or em):
            out.append({"name": p.get("name") or "", "title": p.get("title") or "", "email": em})
    return out

def labeled_text(call, segments, limit=12000):
    """Build a readable 'Name: text' transcript from segments + party speaker map."""
    spk = {}
    for p in call.get("parties", []) or []:
        if p.get("speakerId"):
            spk[p["speakerId"]] = p.get("name") or p.get("affiliation") or "Speaker"
    lines = []
    for seg in segments:
        who = spk.get(seg.get("speakerId"), "Speaker")
        txt = " ".join(s.get("text","") for s in seg.get("sentences", []))
        if txt.strip():
            lines.append(f"{who}: {txt.strip()}")
    out = "\n".join(lines)
    return out[:limit]
