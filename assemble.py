"""assemble.py — merge HubSpot (truth) + fresh Gong + our AI into one cockpit payload.

full=True  : pull HubSpot + Gong + run AI (AI cached per deal). Use on a full refresh.
full=False : pull HubSpot live (fast, the freshness path) and REUSE cached Gong/AI.
The payload shape matches ui.py's renderer.
"""
import os, json, re, datetime
import hubspot as hs, gong, ai, rubric, tasks, categorize as catz
from config import CACHE_DIR

GONG_URL = "https://us-26175.app.gong.io/call?id={}"   # workspace deep-link
BASELINE = {"p50": 14, "p75": 30, "p90": 45}           # generic stage-age baseline (win/loss: 30d stale rule)
STAGE_SHORT = {"Discovery Complete":"Discovery","Demo Complete":"Demo","Quote Sent":"Quote",
               "Verbal Commit":"Verbal","Closed Won":"Won","Closed Lost":"Lost"}
SENIOR = re.compile(r"\b(vp|vice president|chief|coo|ceo|cfo|cio|chro|president|owner|founder|head of|director)\b", re.I)

def _now():
    return datetime.datetime.now(datetime.timezone.utc)

def _days_since(d):
    if not d: return None
    try:
        dt = datetime.datetime.fromisoformat(d.replace("Z","+00:00")) if "T" in d else \
             datetime.datetime.fromisoformat(d).replace(tzinfo=datetime.timezone.utc)
        return (_now() - dt).days
    except Exception:
        return None

def _color(score):
    if score is None: return "gray"
    return "green" if score>=67 else ("yellow" if score>=40 else "red")

def _cache(name):
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, name)

def _load(name, default):
    p = _cache(name)
    if os.path.exists(p):
        try: return json.load(open(p))
        except Exception: return default
    return default

def _infer_vertical(domain, cid, company, full):
    """Cache-first ICP vertical inference from the company website. Reads the local
    vertical_cache (free, used on every fast refresh); on a FULL sync, classifies and
    fills the cache for any company not seen yet. Never writes to HubSpot."""
    if not domain:
        return {}
    key = catz._safe_key(catz._clean_domain(domain) or str(cid))
    cp = os.path.join(CACHE_DIR, "vertical_cache", f"{key}.json")
    if os.path.exists(cp):
        try: return json.load(open(cp))
        except Exception: return {}
    if full:
        try: return catz.categorize(cid, company, domain, CACHE_DIR)
        except Exception: return {}
    return {}

def assemble(rep, full=True, log=print):
    owner = hs.resolve_owner(rep)
    if not owner: raise RuntimeError(f"owner not found for {rep}")
    stages = hs.pipeline_stages(); stage_ids = list(stages)
    order = {sid: stages[sid]["order"] for sid in stages}
    log(f"HubSpot: deals for {owner['name']}…")
    deal_objs = hs.deals_for_owner(owner["id"], stage_ids)
    deal_ids = [d["id"] for d in deal_objs]

    a_co = hs.assoc("deals","companies",deal_ids)
    a_ct = hs.assoc("deals","contacts",deal_ids)
    a_em = hs.assoc("deals","emails",deal_ids)
    a_mt = hs.assoc("deals","meetings",deal_ids)
    a_nt = hs.assoc("deals","notes",deal_ids)
    companies = hs.companies_for({i for v in a_co.values() for i in v})
    contacts  = hs.contacts_for({i for v in a_ct.values() for i in v})
    emails    = hs.emails_for({i for v in a_em.values() for i in v})
    meetings  = hs.meetings_for({i for v in a_mt.values() for i in v})
    notes     = hs.notes_for({i for v in a_nt.values() for i in v})
    log(f"HubSpot: {len(deal_objs)} deals, {len(contacts)} contacts, {len(emails)} emails, {len(meetings)} meetings")

    # ---- Gong (fresh or cached) ----
    gong_by_deal = _load(f"gong-{rep}.json", {})   # {deal_id: [call meta]}
    tx_for_ai = {}                                  # {call_id: transcript} (only when full)
    call_parties = {}                               # {call_id: [parties]}
    if full:
        log("Gong: pulling fresh calls…")
        uid = gong.find_user(owner["email"]) or gong.find_user(f"{rep}@meetquinn.ai")
        calls = gong.calls_for_user(uid, days=180) if uid else []
        # domain -> deal_ids
        dom2deal = {}
        for d in deal_objs:
            for cid in a_co.get(d["id"], []):
                dom = (companies.get(cid, {}).get("domain") or "").lower()
                if dom: dom2deal.setdefault(dom, []).append(d["id"])
        gong_by_deal = {}
        matched_call_ids = {}   # deal_id -> [call_id] for transcript pull
        for c in calls:
            md = c.get("metaData", c); cid = str(md.get("id"))
            doms = gong.external_domains(c)
            hit = set()
            for dm in doms:
                for did in dom2deal.get(dm, []): hit.add(did)
            if not hit: continue
            call_parties[cid] = gong.external_parties(c)
            meta = {"id":cid, "title":md.get("title",""), "date":(md.get("started") or "")[:19],
                    "duration_min": round((md.get("duration") or 0)/60) or None,
                    "url": md.get("url") or GONG_URL.format(cid)}
            for did in hit:
                gong_by_deal.setdefault(did, []).append(meta)
                matched_call_ids.setdefault(did, []).append(cid)
        json.dump(gong_by_deal, open(_cache(f"gong-{rep}.json"),"w"))
        json.dump(call_parties, open(_cache(f"gongparties-{rep}.json"),"w"))
        # transcripts only for deals we'll analyze (open + closed_lost), up to 3 recent calls each
        want = []
        for d in deal_objs:
            b = stages[d["properties"]["dealstage"]]
            is_lost = b["closed"] and not b["won"]
            if (not b["closed"]) or is_lost:
                want += matched_call_ids.get(d["id"], [])[:3]
        if want:
            log(f"Gong: transcripts for {len(set(want))} calls…")
            raw = gong.transcripts(list(set(want)))
            # rebuild labeled text using parties from the matched calls
            cmeta = {str(c.get('metaData',c).get('id')): c for c in calls}
            for cid, seg in raw.items():
                tx_for_ai[cid] = gong.labeled_text(cmeta.get(cid, {}), seg)
    else:
        call_parties = _load(f"gongparties-{rep}.json", {})

    # ---- build deals ----
    deals = []
    for d in deal_objs:
        did = d["id"]; p = d["properties"]; sid = p["dealstage"]
        st = stages[sid]; label = st["label"]; short = STAGE_SHORT.get(label, label)
        bucket = "closed_won" if st["won"] else ("closed_lost" if st["closed"] else
                 ("early" if order[sid]<=1 else "mid"))
        is_open = not st["closed"]
        co = (companies.get((a_co.get(did) or [None])[0], {}) if a_co.get(did) else {})
        # stakeholders: HubSpot contacts + Gong external parties
        stake = {}
        for cid in a_ct.get(did, []):
            c = contacts.get(cid, {})
            nm = f"{c.get('firstname','')} {c.get('lastname','')}".strip()
            if nm: stake[c.get("email") or nm] = {"name":nm,"title":c.get("jobtitle","") or "","email":c.get("email","")}
        for cmeta in gong_by_deal.get(did, []):
            for pty in call_parties.get(cmeta["id"], []):
                k = pty.get("email") or pty.get("name")
                if k and k not in stake: stake[k] = pty
        stake = list(stake.values())
        primary = next((s for s in stake if SENIOR.search(s.get("title") or "")), stake[0] if stake else {})

        # Vertical (Quinn ICP): the CONTACT "Industry (Quinn)" property (industry_category).
        # Take the first contact with a real value; "unknown"/"other" count as empty so the
        # website-scrape categorizer skill fills it later (SOP §B). NOT the company industry enum.
        vertical_quinn = ""
        for cid in a_ct.get(did, []):
            iv = ((contacts.get(cid, {}) or {}).get("industry_category") or "").strip()
            if iv and iv not in ("unknown","other"):
                vertical_quinn = iv; break
        # If the contact has no Quinn vertical, infer it from the website (cache-first).
        co_domain = (co.get("domain") or "").lower()
        co_name = co.get("name") or _name_from(p.get("dealname"))
        vinf = _infer_vertical(co_domain, did, co_name, full) if not vertical_quinn else {}

        # emails
        elist = []
        for eid in a_em.get(did, []):
            e = emails.get(eid, {})
            body = re.sub(r"\s+"," ", (e.get("hs_email_text") or "")).strip()
            elist.append({"ts": e.get("hs_timestamp",""), "dir": (e.get("hs_email_direction") or "").lower(),
                          "from": "", "subject": e.get("hs_email_subject","") or "(no subject)", "snippet": body[:500]})
        elist.sort(key=lambda x: x["ts"] or "", reverse=True)

        # calls (meta from gong) — summaries merged from AI below
        calls = [{"gid":c["id"],"title":c["title"],"date":c["date"],
                  "duration_min":c.get("duration_min"),"url":c["url"],
                  "who":"","discussed":[],"sentiment":"","next_steps":[]} for c in gong_by_deal.get(did, [])]
        calls.sort(key=lambda x: x["date"] or "", reverse=True)

        # stage timeline from entered props
        moves = []
        for s2 in stage_ids:
            v = p.get(f"hs_v2_date_entered_{s2}")
            if v: moves.append({"ts": v, "stage": stages[s2]["label"]})
        cur_entered = p.get(f"hs_v2_date_entered_{sid}")
        days_in_stage = _days_since(cur_entered) if is_open else None

        # merged timeline
        tl = []
        for c in calls: tl.append({"ts":c["date"] or "0","kind":"call","ref":c["gid"],"title":c["title"],"sub":""})
        for e in elist: tl.append({"ts":e["ts"] or "0","kind":"email","title":e["subject"],
                                   "sub":("→ out" if e["dir"]=="outgoing_email" or e["dir"]=="email" else "← in"),"snippet":e["snippet"]})
        for mid in a_mt.get(did, []):
            m = meetings.get(mid, {})
            tl.append({"ts":m.get("hs_meeting_start_time") or m.get("hs_timestamp") or "0","kind":"meeting",
                       "title":m.get("hs_meeting_title") or "Meeting","sub":(m.get("hs_meeting_outcome") or "")})
        for nid in a_nt.get(did, []):
            n = notes.get(nid, {})
            body = re.sub(r"<[^>]+>"," ", n.get("hs_note_body") or ""); body=re.sub(r"\s+"," ",body).strip()
            if body: tl.append({"ts":n.get("hs_timestamp") or "0","kind":"note","title":"Note","sub":"","snippet":body[:400]})
        for mv in moves: tl.append({"ts":mv["ts"],"kind":"stage","title":"Entered "+mv["stage"],"sub":""})
        tl.sort(key=lambda x: x["ts"] or "", reverse=True)

        deal = {"id":did,"company":co.get("name") or _name_from(p.get("dealname")),
                "stage_id":sid,"stage":short,"stage_full":label,"bucket":bucket,"rank":order[sid],
                "amount":_num(p.get("amount")),"arr":_num(p.get("amount")),
                "source":(p.get("hs_analytics_source_data_1") or p.get("hs_analytics_source") or "—"),
                "dealtype":p.get("dealtype") or "newbusiness",
                "industry":co.get("industry_category") or co.get("industry") or "","vertical_quinn":vertical_quinn,
                "vertical_inferred":(vinf or {}).get("vertical") or "","vertical_inferred_meta":vinf or {},"employees":_num(co.get("numberofemployees")),
                "locations":co.get("numberoflocations") or "","icp":"",
                "company_desc":co.get("description") or "","website":co.get("website") or "",
                "company_linkedin":co.get("linkedin_company_page") or "",
                "domain":(co.get("domain") or "").lower(),
                "primary_contact":{"name":primary.get("name",""),"title":primary.get("title","")},
                "stakeholders":stake,"calls":calls,"emails":elist,"timeline":tl,
                "intel":"","loss":None,
                "dcs":{"score":None,"color":"gray","scores":{},"rationale":"","days_in_stage":days_in_stage,
                       "baseline":BASELINE,"n_calls":len(calls),"n_emails":len(elist)},
                "hubspot_url":f"https://app.hubspot.com/contacts/deals/{did}",
                "is_open":is_open,"rubric_stage":rubric.HS_TO_STAGE.get(sid,"disc"),
                "ai_fields":{},"ai_next_steps":[],"ai_engine":None,"alerts":[]}
        deals.append((deal, d))

    # ---- AI pass ----
    engines = set()
    for deal, d in deals:
        b = deal["bucket"]
        analyze = b not in ("closed_won",)   # open + closed_lost
        res = None
        if full and analyze:
            cmeta = gong_by_deal.get(deal["id"], [])   # most-recent-first
            # Cover BOTH ends: the earliest call (where Discovery/BANT lives) and the
            # most recent activity. For >6 calls, take the 4 newest + 2 oldest, dedup,
            # then read them chronologically (discovery first) so the model sees the
            # full arc and isn't starved of discovery context on later-stage deals.
            if len(cmeta) <= 6:
                sel = list(cmeta)
            else:
                sel, seen = [], set()
                for c in cmeta[:4] + cmeta[-2:]:
                    if c["id"] not in seen:
                        seen.add(c["id"]); sel.append(c)
            sel.sort(key=lambda c: c["date"] or "")   # chronological: discovery → latest
            calls_ctx = [{"id":c["id"],"title":c["title"],"date":c["date"],"transcript":tx_for_ai.get(c["id"],"")}
                         for c in sel]
            res = ai.analyze_deal(
                {"id":deal["id"],"name":deal["company"],"stage_label":deal["stage"],"bucket":b,
                 "amount":deal["amount"],"company":deal["company"],"industry":deal["industry"],
                 "employees":deal["employees"],"stakeholders":deal["stakeholders"],"n_emails":len(deal["emails"])},
                calls_ctx, deal["emails"], CACHE_DIR)
        else:
            res = _load(f"ai/{deal['id']}.json", {}).get("result")
        if res:
            _apply_ai(deal, res)
            engines.add(deal["ai_engine"])
        _alerts(deal)

    deals = [d for d,_ in deals]
    # ---- upcoming + recently-held first calls ----
    up = []
    now_iso = _now().strftime("%Y-%m-%dT%H:%M:%SZ")
    # Discovery Booked = a first discovery call with no deal yet. It must STAY visible after
    # the call happens — until a deal is created (gates clear) or it's closed-lost — not vanish
    # the moment the slot passes (Johnny 2026-06-23, ServiceMaster). So pull a 14-day look-back
    # window, not future-only; below we keep past *first-calls-without-a-deal* and drop past
    # deal-linked meetings (so hasFutureMeeting() / the agenda stay future-correct). 14d (Johnny
    # 2026-06-23): long enough a just-held first-call lingers, short enough stale ones age out.
    since_iso = (_now() - datetime.timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%SZ")
    # meeting_id -> deal_id via the deal<->meeting association (exact match), preferring an
    # open deal. Falls back to company-name-in-title so a meeting titled "Quinn <> Kinetico"
    # still binds to the Kinetico deal and inherits its current-stage colour.
    open_ids = {x["id"] for x in deals if x["is_open"]}
    by_id = {x["id"]: x for x in deals}
    mtg_to_deal = {}
    for did, mids in a_mt.items():
        for mid in mids:
            if mid not in mtg_to_deal or did in open_ids:
                mtg_to_deal[mid] = did
    open_by_co = {x["company"].lower(): x["id"] for x in deals if x["is_open"]}
    raw_mtgs = hs.upcoming_meetings(owner["id"], since_iso)
    # A genuine *first* Discovery call = hs_activity_type "First Meeting" (booked via the public
    # Meetings link) with no deal yet — that's the Discovery Booked tile. Enrich those with the
    # associated contact (booking-form answers: # field workers, LMS) + company (employees,
    # domain→vertical). Follow-up demos/proposal calls (which have deals) stay plain.
    first_mids = [str(m.get("id","")) for m in raw_mtgs
                  if m["properties"].get("hs_activity_type") == "First Meeting"
                  and not mtg_to_deal.get(str(m.get("id","")))]
    m2contact = hs.assoc("meetings","contacts",first_mids) if first_mids else {}
    m2company = hs.assoc("meetings","companies",first_mids) if first_mids else {}
    f_contacts = hs.contacts_for(sorted({c for v in m2contact.values() for c in v})) if m2contact else {}
    f_companies = hs.companies_for(sorted({c for v in m2company.values() for c in v})) if m2company else {}
    for m in raw_mtgs:
        mp = m["properties"]
        mid = str(m.get("id",""))
        title = mp.get("hs_meeting_title","") or "Meeting"
        did = mtg_to_deal.get(mid)
        if not did:
            tl = title.lower()
            did = open_by_co.get(tl) or next((i for co, i in open_by_co.items() if co and co in tl), None)
        is_first = (mp.get("hs_activity_type") == "First Meeting")
        start = mp.get("hs_meeting_start_time") or ""
        is_future = start > now_iso          # ISO-Zulu strings compare lexically
        # Keep genuine first-calls with no deal (Discovery Booked, even if just held) and any
        # future meeting; drop *past* deal-linked meetings — they belong to the deal's history,
        # and keeping them would wrongly satisfy hasFutureMeeting() / pollute the agenda.
        if not ((is_first and not did) or is_future):
            continue
        e = {"title":title,"start":start,
             "meeting_id":mid,"is_first":bool(is_first),
             "contact":"","contact_title":"","company":(by_id[did]["company"] if did in by_id else _clean_mtg_title(title)),
             "employees":"","num_of_learners":"","lms":"",
             "vertical_quinn":"","vertical":"","vertical_meta":{},"tier":"",
             "deal_id":did}
        if is_first and not did:
            cids = m2contact.get(mid, []); coids = m2company.get(mid, [])
            cp = f_contacts.get(cids[0], {}) if cids else {}
            co = f_companies.get(coids[0], {}) if coids else {}
            e["contact"] = ((cp.get("firstname") or "")+" "+(cp.get("lastname") or "")).strip()
            e["contact_title"] = cp.get("jobtitle","") or ""
            e["num_of_learners"] = cp.get("num_of_learners","") or ""
            e["lms"] = cp.get("which_lms_") or cp.get("lms") or ""
            if co.get("name"): e["company"] = co.get("name")
            e["employees"] = co.get("numberofemployees") or ""
            # Vertical/tier source mirrors the deal path: the CONTACT "Industry (Quinn)"
            # property (industry_category) IS the real ICP vertical — use it first. Only when
            # it's blank do we fall back to the website-scrape categorizer. (Johnny 2026-06-23:
            # Hometown/NearU had "HVAC Service Provider" on the contact but the row showed blank
            # because we were reading the scraper only — never miss a vertical that's already
            # sitting on the contact.)
            iv = (cp.get("industry_category") or "").strip()
            if iv and iv.lower() not in ("unknown", "other"):
                e["vertical_quinn"] = iv
            else:
                dom = (co.get("domain") or "").lower()
                vinf = {}
                if dom:
                    try: vinf = catz.categorize((coids[0] if coids else mid), e["company"], dom, CACHE_DIR)
                    except Exception: vinf = {}
                e["vertical"] = (vinf or {}).get("vertical") or ""
                e["vertical_meta"] = vinf or {}
                e["tier"] = (vinf or {}).get("tier") or ""
        up.append(e)
    up.sort(key=lambda x: x["start"])
    up = up[:200]   # one rep's meetings; raised from 30 so the 60-day booked look-back isn't truncated

    funnel = []
    for sid in sorted(stage_ids, key=lambda s: order[s]):
        sub=[x for x in deals if x["stage_id"]==sid]
        funnel.append({"stage_id":sid,"label":STAGE_SHORT.get(stages[sid]["label"],stages[sid]["label"]),
                       "full":stages[sid]["label"],"n":len(sub),"arr":sum((x["arr"] or 0) for x in sub)})

    payload = {"rep":owner["name"],"rep_slug":rep,
               "generated_at":_now().strftime("%Y-%m-%d %H:%M UTC"),
               "refreshed":_now().strftime("%Y-%m-%d %H:%M:%S UTC"),
               "ai_engine":("claude" if "claude" in engines else ("heuristic" if engines else "none")),
               "rubric":rubric.STAGES,
               "funnel":funnel,"upcoming":up,
               "deals":sorted(deals,key=lambda x:(not x["is_open"], -(x["arr"] or 0))),
               "kb":load_kb()}
    # SalesOS Cockpit Task Inbox — heuristically derived from this snapshot
    # (Phase 0; not yet event-driven — see tasks.py header). Pure read; no writes.
    payload["inbox"] = tasks.grouped(payload)
    json.dump(payload, open(_cache(f"payload-{rep}.json"),"w"), default=str)
    log(f"done: {len(deals)} deals, ai_engine={payload['ai_engine']}")
    return payload

def _apply_ai(deal, res):
    deal["ai_engine"] = res.get("engine","heuristic")
    dcs = res.get("dcs",{}) or {}
    sc = {k:dcs.get(k) for k in ("pain","champion","multi_threading","buying_language","objection_status") if dcs.get(k) is not None}
    deal["dcs"].update({"score":dcs.get("score"),"color":_color(dcs.get("score")),
                        "scores":sc,"rationale":dcs.get("rationale","")})
    bycall = {s.get("call_id"):s for s in res.get("call_summaries",[])}
    for c in deal["calls"]:
        s = bycall.get(c["gid"])
        if s: c.update({"who":s.get("who",""),"discussed":s.get("discussed",[]) or [],
                        "sentiment":s.get("sentiment",""),"next_steps":s.get("next_steps",[]) or []})
    cite_label = {c["gid"]:(c["title"][:38]+" · "+(c["date"] or "")[:10]) for c in deal["calls"]}
    for fld in res.get("fields",[]):
        cid = fld.get("cite_call_id")
        deal["ai_fields"][fld["item_id"]] = {"value":fld.get("value",""),"evidence":fld.get("evidence",""),
            "cite":{"label":cite_label.get(cid,"deal evidence"),"gid":cid if cid in cite_label else None}}
    deal["ai_next_steps"] = res.get("next_steps",[]) or []
    deal["intel"] = res.get("note","") or ""
    if res.get("loss"): deal["loss"] = res["loss"]

def _alerts(deal):
    a=[]; s=deal["dcs"]["score"]; dis=deal["dcs"]["days_in_stage"]; b=deal["dcs"]["baseline"]
    if deal["is_open"] and s is not None and s<50: a.append({"sev":"high","text":f"DCS {s} — escalate to Arlen"})
    if deal["is_open"] and dis is not None and dis>b["p90"]: a.append({"sev":"high","text":f"Stale — {dis}d in {deal['stage']} (past {b['p90']}d)"})
    elif deal["is_open"] and dis is not None and dis>b["p75"]: a.append({"sev":"med","text":f"{dis}d in {deal['stage']} (past {b['p75']}d)"})
    if deal["is_open"] and len(deal["stakeholders"])<2: a.append({"sev":"med","text":f"Single-threaded — {len(deal['stakeholders'])} stakeholder"})
    if deal["is_open"] and not any(SENIOR.search(s.get("title") or "") for s in deal["stakeholders"]):
        a.append({"sev":"med","text":"No VP+ / decision-maker reached"})
    deal["alerts"]=a

def _num(v):
    try: return float(v)
    except (TypeError, ValueError): return None

def _name_from(dealname):
    return (dealname or "Unnamed deal").split(" - ")[0].strip()

def _clean_mtg_title(t):
    """'Quinn <> Acme Discussion' -> 'Acme'. Used as the company label for a booked first
    call only when no company is associated to the meeting."""
    t = (t or "").strip()
    t = re.sub(r"(?i)^\s*quinn\s*<>\s*", "", t)
    t = re.sub(r"(?i)^\s*quinn\s*[:\-|]\s*", "", t)
    t = re.sub(r"(?i)\s+(discussion|discovery(\s*call)?|intro(ductory)?(\s*call)?|meeting|call|demo|chat|sync)\s*$", "", t)
    return t.strip() or "Meeting"

def load_kb():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    kb = os.path.join(base, "sales-knowledge-base")
    files = [("Objection bank","sales-motion/objections.md"),("Value & proof","company/value-prop.md"),
             ("Operations buyer","personas/operations.md"),("vs. Cornerstone","competitors/cornerstone.md"),
             ("vs. Docebo","competitors/docebo.md")]
    out=[]
    for title,rel in files:
        p=os.path.join(kb,rel)
        if os.path.exists(p):
            try: out.append({"title":title,"md":open(p).read()[:8000]})
            except Exception: pass
    return out
