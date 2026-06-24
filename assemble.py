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

# ================== BANT — computed by SalesOS from the transcript (SOP §2 rubric) ==========
# The OLD path read the #gong-notifier contact props (bant_score/bant_raw_scores). That engine
# is OUTDATED and being sunset (Johnny 2026-06-23). SalesOS now COMPUTES BANT itself from the
# Gong discovery transcript via ai.score_bant() using the SOP rubric, and combines it with the
# fit routing (tier / field-worker count / inbound) to recommend QUALIFY / DISQUALIFY.
_NEED_SUBS = [("operational_pain","Operational Pain",20),("tech_stack","Tech Stack",10),
              ("multi_location","Multi-Location",5),("compliance","Compliance",5)]

def _fw_lower(band):
    """Field-worker band ('101-500','2000+','25-50') -> lower-bound int."""
    if not band: return None
    m = re.search(r"\d+", str(band).replace(",",""))
    return int(m.group()) if m else None

def contact_enrich(cp):
    """Booking-form fallback for # field workers + LMS (used when the transcript is silent)."""
    cp = cp or {}
    band = (cp.get("num_of_learners") or "").strip()
    est  = (cp.get("frontline_workers_est") or "").strip()
    which = (cp.get("which_lms_") or "").strip()
    lv = (cp.get("lms") or "").strip().lower()
    lms_yn = "yes" if lv in ("yes","true","y") else ("no" if lv in ("no","false","n","none") else ("yes" if which else ""))
    return {"fw_band":band, "fw_est":est, "fw_lower":(_fw_lower(est) or _fw_lower(band)),
            "lms":lms_yn, "which_lms":which}

# Primary Source ("lead_source_custom") -> inbound/outbound, Johnny's EXACT mapping (2026-06-23).
# Stored VALUES differ from labels: "Cold Call" -> "ZoomInfo". Anything unlisted -> unknown(None).
_INBOUND_SRC = {"warm call","zoominfo","cold call","conference","field visit","cold outreach email",
                "paid social","paid search","cold outreach linkedin","email marketing"}
_OUTBOUND_SRC = {"referral","organic"}
def _inbound(cp):
    """inbound(True)/outbound(False)/unknown(None) from the Primary Source property."""
    v = ((cp or {}).get("lead_source_custom") or "").strip().lower()
    if not v: return None
    if v in _INBOUND_SRC: return True
    if v in _OUTBOUND_SRC: return False
    return None

def _tier_of(vertical):
    """Vertical name -> ICP tier number (1-4) via the live icp-tiers map; None if unmatched.
    Normalizes a HubSpot 'Industry (Quinn)' option slug (e.g. 'hvac_service_provider')
    to its canonical TIERS key first, so a contact-sourced vertical tiers correctly
    instead of silently returning None and corrupting the fit/qualify routing."""
    if not vertical: return None
    return catz.TIERS.get(catz.canon_vertical(vertical))

def _fit(tier, fw, emp, inbound, lms_has):
    """Quinn-fit auto-check (Johnny 2026-06-23, locked ts1782249132):
      T1 -> qualify (outbound is the motion; an inbound T1 also passes).
      T2 -> only if INBOUND and (field workers >= 50  OR employees >= 100).
      T3 -> only if INBOUND and (field workers >= 200 OR employees >= 500).
      T4 -> always reject.
    Also: <25 field workers with an entrenched LMS is a don't-sell floor.
    Returns (ok True/False/None, reason)."""
    active_lms = (lms_has == "yes")
    if tier == 4: return False, "T4 vertical — don't-sell"
    if fw is not None and fw < 25 and active_lms: return False, f"{fw} field workers (<25) + active LMS"
    if tier == 1: return True, "T1 vertical"
    if tier in (2, 3):
        if inbound is not True: return False, f"T{tier} requires inbound (only T1 sells outbound)"
        bar_fw, bar_emp = (50, 100) if tier == 2 else (200, 500)
        size_ok = (fw is not None and fw >= bar_fw) or (emp is not None and emp >= bar_emp)
        if size_ok: return True, f"T{tier} inbound, size OK (FW {fw or '?'} / emp {emp or '?'} vs FW≥{bar_fw} or emp≥{bar_emp})"
        if fw is None and emp is None: return None, f"T{tier} inbound — size unknown, confirm on the call"
        return False, f"T{tier} inbound but below size bar (need FW≥{bar_fw} or emp≥{bar_emp})"
    if tier is None:
        # No vertical resolved to a Quinn tier — either no industry signal at all,
        # or the website categorizer high-confidence returned "not a Quinn vertical"
        # (e.g. a church). Size alone never establishes ICP membership, so NEVER
        # auto-pass: surface as unscored and make the AE classify on the call.
        # (QA loop 2026-06-24: the old catch-all returned True/"Meets fit floor"
        # whenever any size signal existed, silently passing out-of-ICP accounts.)
        if fw is None and emp is None:
            return None, "Vertical & size unknown — confirm on the call"
        return None, "Quinn-fit unverified — vertical not resolved; classify on the call"
    return True, "Meets fit floor"

def _recommend(total, floors_ok, floor_fail, tier, fw, emp, inbound, lms_has):
    """SOP §2 qualify/disqualify routing: fit gates first, then the BANT gate. Returns
    (rec, reason, flags)."""
    flags = []
    fit_ok, fit_reason = _fit(tier, fw, emp, inbound, lms_has)
    if fit_ok is False:
        return "DISQUALIFY", f"Fit: {fit_reason}.", flags
    if fw is not None and fw > 250:
        flags.append("Notify @arlen (>250 field workers) — deal stays with the booking AE")
    if not floors_ok:
        return "DISQUALIFY", "BANT floor not met: " + ", ".join(floor_fail) + ".", flags
    if total is not None and total >= 50:
        return "QUALIFY", f"BANT {total} ≥ 50, floors met" + (f"; {fit_reason}" if fit_ok else "") + ".", flags
    return "DISQUALIFY", f"BANT {total} < 50.", flags

def build_scorecard(raw, tier, tier_label, enrich, inbound, emp=None):
    """Turn ai.score_bant() output into the rich scorecard ui.py renders. None if no score.
    `emp` = company employee count (HubSpot numberofemployees) — the alternative size bar
    for the T2/T3 fit gate (FW>=N OR employees>=M)."""
    if not raw or raw.get("engine") == "error":
        return None
    def comp(d):
        # Tolerate the model returning a {score,rationale,quote} dict, a bare number,
        # a plain string rationale, or nothing — never raise (a single malformed AI
        # component must not crash the whole sync).
        if isinstance(d, dict):
            try: s = int(d.get("score") or 0)
            except (TypeError, ValueError): s = 0
            return s, (d.get("rationale") or "").strip(), (d.get("quote") or "").strip()
        if isinstance(d, bool):  return 0, "", ""
        if isinstance(d, (int, float)): return int(d), "", ""
        if isinstance(d, str):   return 0, d.strip(), ""
        return 0, "", ""
    bV,bW,bQ = comp(raw.get("budget"))
    aV,aW,aQ = comp(raw.get("authority"))
    tV,tW,tQ = comp(raw.get("timeline"))
    need_raw = raw.get("need")
    need = need_raw if isinstance(need_raw, dict) else {}
    need_str = need_raw.strip() if isinstance(need_raw, str) else ""
    subs = []
    need_total = 0
    for key,label,mx in _NEED_SUBS:
        v,w,q = comp(need.get(key))
        v = max(0, min(mx, v)); need_total += v
        subs.append({"k":label,"v":v,"max":mx,"why":w,"quote":q})
    bV=max(0,min(20,bV)); aV=max(0,min(20,aV)); tV=max(0,min(20,tV))
    total = bV + aV + need_total + tV
    floor_fail = []
    if bV < 10: floor_fail.append("Budget ≥ 10")
    if aV < 10: floor_fail.append("Authority ≥ 10")
    if need_total < 20: floor_fail.append("Need ≥ 20")
    if tV < 10: floor_fail.append("Timeline ≥ 10")
    floors_ok = not floor_fail
    # field workers: transcript training-scope count preferred; else booking-form band
    fw = raw.get("field_workers")
    fw = int(fw) if isinstance(fw,(int,float)) else None
    fw_note = (raw.get("field_workers_note") or "").strip()
    if fw is None:
        fw = (enrich or {}).get("fw_lower"); fw_note = "booking form" if fw else ""
    lms_has = raw.get("lms_has") or ((enrich or {}).get("lms") or "unknown") or "unknown"
    if lms_has not in ("yes","no","unknown"): lms_has = "unknown"
    lms_which = (raw.get("lms_which") or (enrich or {}).get("which_lms") or "").strip()
    emp = int(emp) if isinstance(emp, (int, float)) else None
    rec, reason, flags = _recommend(total, floors_ok, floor_fail, tier, fw, emp, inbound, lms_has)
    fit_ok, fit_reason = _fit(tier, fw, emp, inbound, lms_has)
    items = [
        {"k":"Budget","v":bV,"max":20,"why":bW,"quote":bQ},
        {"k":"Authority","v":aV,"max":20,"why":aW,"quote":aQ},
        {"k":"Need","v":need_total,"max":40,"why":(need.get("summary","") or need_str),"quote":"","subs":subs},
        {"k":"Timeline","v":tV,"max":20,"why":tW,"quote":tQ},
    ]
    return {"total":total,"rec":rec,"rec_reason":reason,"flags":flags,
            "tier":tier_label or ("T"+str(tier) if tier else ""),"items":items,
            "floors_ok":floors_ok,"floor_fail":floor_fail,
            "field_workers":fw,"fw_note":fw_note,"lms_has":lms_has,"lms_which":lms_which,
            "fit_ok":fit_ok,"fit_reason":fit_reason,
            "summary":(raw.get("summary") or "").strip(),
            "source":"salesos-rubric","rubric_version":raw.get("rubric_version","")}

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
    # dom2call maps EVERY external call's domain -> [call meta], so a booked first-call with no
    # deal yet can still find its discovery transcript by the contact's email domain. tx_for_ai
    # (labeled transcripts) is persisted so BANT survives a fast refresh — ai.score_bant() then
    # cache-hits on its rubric signature instead of re-pulling Gong or re-calling Claude.
    gong_by_deal = _load(f"gong-{rep}.json", {})    # {deal_id: [call meta]}
    tx_for_ai    = {}                                # {call_id: labeled transcript}
    call_parties = {}                                # {call_id: [parties]}
    dom2call     = {}                                # {domain: [call meta]} — ALL external calls
    call_meta_by_id = {}                             # {call_id: raw gong call} — full sync only
                                                     # (own name: the deal loop reuses `cmeta` as a list)
    if full:
        log("Gong: pulling fresh calls…")
        uid = gong.find_user(owner["email"]) or gong.find_user(f"{rep}@meetquinn.ai")
        calls = gong.calls_for_user(uid, days=180) if uid else []
        call_meta_by_id = {str(c.get('metaData',c).get('id')): c for c in calls}
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
            meta = {"id":cid, "title":md.get("title",""), "date":(md.get("started") or "")[:19],
                    "duration_min": round((md.get("duration") or 0)/60) or None,
                    "url": md.get("url") or GONG_URL.format(cid)}
            call_parties[cid] = gong.external_parties(c)
            for dm in doms:
                dom2call.setdefault(dm, []).append(meta)
            hit = set()
            for dm in doms:
                for did in dom2deal.get(dm, []): hit.add(did)
            for did in hit:
                gong_by_deal.setdefault(did, []).append(meta)
                matched_call_ids.setdefault(did, []).append(cid)
        json.dump(gong_by_deal, open(_cache(f"gong-{rep}.json"),"w"))
        json.dump(call_parties, open(_cache(f"gongparties-{rep}.json"),"w"))
        json.dump(dom2call, open(_cache(f"dom2call-{rep}.json"),"w"))
        # transcripts for every call on an OPEN deal we'll BANT-score (Johnny: score the live
        # pipeline only, exclude Closed Won/Lost). The earliest is the discovery call BANT reads.
        # Booked-lead transcripts are pulled below (we don't know the booked first-calls until
        # the meeting pass). tx_for_ai persists at end.
        want = set()
        for d in deal_objs:
            b = stages[d["properties"]["dealstage"]]
            if not b["closed"]:
                want.update(matched_call_ids.get(d["id"], []))
        if want:
            log(f"Gong: transcripts for {len(want)} deal calls…")
            raw = gong.transcripts(list(want))
            for cid, seg in raw.items():
                tx_for_ai[cid] = gong.labeled_text(call_meta_by_id.get(cid, {}), seg)
    else:
        tx_for_ai    = _load(f"gongtx-{rep}.json", {})
        call_parties = _load(f"gongparties-{rep}.json", {})
        dom2call     = _load(f"dom2call-{rep}.json", {})

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
        vertical = vertical_quinn or (vinf or {}).get("vertical") or ""
        deal_tier = _tier_of(vertical)
        deal_tier_label = catz.TIER_LABELS.get(str(deal_tier), "") if deal_tier else ""

        # ---- BANT: computed from the DISCOVERY (earliest) Gong transcript via the SOP §2 rubric.
        # Not the #gong-notifier props. enrich = booking-form fallback for FW/LMS; inbound from
        # the Primary Source property. Recommendation fuses BANT floors + fit routing.
        deal_enrich = None
        for cid in a_ct.get(did, []):
            cpp = contacts.get(cid, {})
            if cpp.get("num_of_learners") or cpp.get("lms") or cpp.get("which_lms_") or cpp.get("frontline_workers_est"):
                deal_enrich = contact_enrich(cpp); break
        if deal_enrich is None and a_ct.get(did):
            deal_enrich = contact_enrich(contacts.get(a_ct[did][0], {}))
        inbound_cp = None
        for cid in a_ct.get(did, []):
            if (contacts.get(cid, {}) or {}).get("lead_source_custom"): inbound_cp = contacts.get(cid, {}); break
        if inbound_cp is None and a_ct.get(did):
            inbound_cp = contacts.get(a_ct[did][0], {})
        deal_inbound = _inbound(inbound_cp)
        cmetas = gong_by_deal.get(did, [])
        disc = min(cmetas, key=lambda c: c.get("date") or "9999") if cmetas else None
        disc_tx = tx_for_ai.get(disc["id"], "") if disc else ""
        deal_bant = None
        if disc_tx:
            bant_ctx = {"company":co_name,"employees":_num(co.get("numberofemployees")),
                        "contact_title":(primary.get("title","") if primary else ""),
                        "vertical":vertical,"tier":deal_tier}
            try:
                raw_bant = ai.score_bant(disc_tx, bant_ctx, CACHE_DIR, f"deal-{did}", force=False)
                deal_bant = build_scorecard(raw_bant, deal_tier, deal_tier_label, deal_enrich, deal_inbound, _num(co.get("numberofemployees")))
            except Exception as ex:
                log(f"BANT scoring failed for deal {did}: {ex}"); deal_bant = None

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
                "closedate":p.get("closedate") or "",
                "source":(p.get("hs_analytics_source_data_1") or p.get("hs_analytics_source") or "—"),
                "dealtype":p.get("dealtype") or "newbusiness",
                "industry":co.get("industry_category") or co.get("industry") or "","vertical_quinn":vertical_quinn,
                "vertical_inferred":(vinf or {}).get("vertical") or "","vertical_inferred_meta":vinf or {},
                # Canonical ICP vertical NAME, always materialized (slug-or-inferred → canon_vertical).
                # vertical_inferred is ONLY the website-scrape fallback (empty when HubSpot has the slug),
                # so JSON consumers like Rita had no clean display name — they'd get a blank or the raw
                # slug. This is the single authoritative name field. (QA loop 2026-06-24, check-1.)
                "vertical_name":(catz.canon_vertical(vertical) if vertical else ""),
                "tier":deal_tier,"tier_label":deal_tier_label,"employees":_num(co.get("numberofemployees")),
                "locations":co.get("numberoflocations") or "","icp":"",
                "company_desc":co.get("description") or "","website":co.get("website") or "",
                "company_linkedin":co.get("linkedin_company_page") or "",
                "domain":(co.get("domain") or "").lower(),
                "primary_contact":{"name":primary.get("name",""),"title":primary.get("title","")},
                "stakeholders":stake,"calls":calls,"emails":elist,"timeline":tl,
                "intel":"","loss":None,
                # Authoritative AE-selected loss reason straight from HubSpot (source-of-record).
                # `loss` (above) is the AI-derived post-mortem narrative and is ALWAYS produced for a
                # closed-lost deal — so the Stage-07 §D "loss logged" DoD must grade off THIS field
                # (the AE actually selected/accepted it), not off the AI guess. (QA loop check-3.)
                "loss_logged":({"reason":p.get("closed_lost_reason") or "",
                                "detail":p.get("disqualification_reason") or "",
                                "notes":p.get("closed_lost_notes") or ""}
                               if bucket=="closed_lost" else None),
                "dcs":{"score":None,"color":"gray","scores":{},"rationale":"","days_in_stage":days_in_stage,
                       "baseline":BASELINE,"n_calls":len(calls),"n_emails":len(elist)},
                "hubspot_url":f"https://app.hubspot.com/contacts/deals/{did}",
                "is_open":is_open,"rubric_stage":rubric.HS_TO_STAGE.get(sid,"disc"),
                "bant":deal_bant,"enrich":deal_enrich,"inbound":deal_inbound,
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
    # Pipeline-hygiene post-pass: a company with >1 OPEN deal double-counts pipeline value and
    # splits the deal history — a real data-quality fault. Detect-and-flag ONLY; merging/closing
    # a deal is a live HubSpot write the AE owns, never the operator. (QA loop 2026-06-24 —
    # Cotulla Education carried two open $75k Quote deals = $75k phantom pipeline.)
    _open_co_counts = {}
    for d in deals:
        if d.get("is_open"):
            _k = (d.get("company") or "").strip().lower()
            _open_co_counts[_k] = _open_co_counts.get(_k, 0) + 1
    for d in deals:
        _k = (d.get("company") or "").strip().lower()
        if d.get("is_open") and _open_co_counts.get(_k, 0) > 1:
            d["alerts"].append({"sev":"high",
                "text":f"Duplicate open deal — {_open_co_counts[_k]} open deals for {d['company']}; merge/close one in HubSpot"})
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
    # Booked-lead BANT: match each booked first-call to a Gong call by the contact's email
    # DOMAIN, take the earliest (the discovery call). Pull those transcripts so score_bant runs.
    lead_call = {}   # meeting_id -> chosen call meta
    for mid in first_mids:
        cids = m2contact.get(mid, [])
        cp = f_contacts.get(cids[0], {}) if cids else {}
        if not isinstance(cp, dict):
            log(f"  booked-lead {mid}: contact {cids[0] if cids else '?'} props not a dict ({type(cp).__name__}) — skipping")
            cp = {}
        email = (cp.get("email") or "")
        dom = email.split("@")[-1].lower() if "@" in email else ""
        cand = dom2call.get(dom, []) if dom else []
        if cand:
            lead_call[mid] = min(cand, key=lambda c: c.get("date") or "9999")
    if full and lead_call:
        need = [m["id"] for m in lead_call.values() if m["id"] not in tx_for_ai]
        if need:
            log(f"Gong: transcripts for {len(set(need))} booked-lead calls…")
            raw = gong.transcripts(list(set(need)))
            for cid, seg in raw.items():
                tx_for_ai[cid] = gong.labeled_text(call_meta_by_id.get(cid, {}), seg)
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
        outcome = (mp.get("hs_meeting_outcome") or "").upper()
        is_future = start > now_iso          # ISO-Zulu strings compare lexically
        # A CANCELED or RESCHEDULED slot is not a live booked call (a rescheduled meeting
        # re-appears as its own new meeting object). Drop the dead slot so it neither shows in
        # Discovery Booked nor falsely reads as a held call. (Johnny 2026-06-23)
        if outcome in ("CANCELED", "RESCHEDULED"):
            continue
        # Keep genuine first-calls with no deal (Discovery Booked, even if just held) and any
        # future meeting; drop *past* deal-linked meetings — they belong to the deal's history,
        # and keeping them would wrongly satisfy hasFutureMeeting() / pollute the agenda.
        if not ((is_first and not did) or is_future):
            continue
        e = {"title":title,"start":start,
             "meeting_id":mid,"is_first":bool(is_first),"outcome":outcome,
             "contact":"","contact_title":"","company":(by_id[did]["company"] if did in by_id else _clean_mtg_title(title)),
             "employees":"","num_of_learners":"","lms":"","which_lms":"","fw_est":"",
             "vertical_quinn":"","vertical":"","vertical_meta":{},"tier":"",
             "bant":None,"enrich":None,"inbound":None,"bant_tier":"",
             "deal_id":did,"awaiting_outcome":False}
        if is_first and not did:
            cids = m2contact.get(mid, []); coids = m2company.get(mid, [])
            cp = f_contacts.get(cids[0], {}) if cids else {}
            co = f_companies.get(coids[0], {}) if coids else {}
            if not isinstance(cp, dict): cp = {}
            if not isinstance(co, dict): co = {}
            e["contact"] = ((cp.get("firstname") or "")+" "+(cp.get("lastname") or "")).strip()
            e["contact_title"] = cp.get("jobtitle","") or ""
            e["num_of_learners"] = cp.get("num_of_learners","") or ""
            e["lms"] = cp.get("which_lms_") or cp.get("lms") or ""
            en = contact_enrich(cp)
            e["enrich"] = en; e["which_lms"] = en["which_lms"]; e["fw_est"] = en["fw_est"]
            e["inbound"] = _inbound(cp)
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
            # BANT — computed from the discovery transcript (matched by contact domain), SOP §2.
            lead_vertical = e["vertical_quinn"] or e["vertical"] or ""
            lead_tier = _tier_of(lead_vertical)
            lead_tier_label = catz.TIER_LABELS.get(str(lead_tier), "") if lead_tier else ""
            e["tier"] = e["tier"] or lead_tier or ""
            e["vertical_name"] = catz.canon_vertical(lead_vertical) if lead_vertical else ""  # canonical display name (QA loop 2026-06-24)
            meta = lead_call.get(mid)
            disc_tx = tx_for_ai.get(meta["id"], "") if meta else ""
            if disc_tx:
                bant_ctx = {"company":e["company"],"employees":(_num(co.get("numberofemployees")) or ""),
                            "contact_title":e["contact_title"],"vertical":lead_vertical,"tier":lead_tier}
                try:
                    raw_bant = ai.score_bant(disc_tx, bant_ctx, CACHE_DIR, f"lead-{mid}", force=False)
                    e["bant"] = build_scorecard(raw_bant, lead_tier, lead_tier_label, en, e["inbound"], _num(co.get("numberofemployees")))
                except Exception as ex:
                    log(f"BANT scoring failed for lead {mid}: {ex}"); e["bant"] = None
            e["bant_tier"] = (e["bant"] or {}).get("tier","") or lead_tier_label
            # "Awaiting outcome" ghost: the first meeting's start time has passed but it was never
            # marked (still SCHEDULED/blank) and produced no transcript → no BANT. It sits in
            # Discovery Booked looking live when the call may have no-showed or quietly slipped.
            # Surface it so the AE sets an outcome instead of it hiding. (Johnny 2026-06-23)
            e["awaiting_outcome"] = bool(start and not is_future
                                         and outcome in ("", "SCHEDULED")
                                         and e["bant"] is None)
        up.append(e)
    up.sort(key=lambda x: x["start"])
    up = up[:200]   # one rep's meetings; raised from 30 so the 60-day booked look-back isn't truncated
    # Persist transcripts (deal + booked-lead) so a fast refresh keeps BANT — score_bant
    # cache-hits on the rubric signature instead of re-pulling Gong or re-calling Claude.
    if full:
        json.dump(tx_for_ai, open(_cache(f"gongtx-{rep}.json"),"w"))

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
    # Pipeline-hygiene: a priced stage with no deal amount = a quote/pipeline value gap. Only
    # fires at Quote/Verbal — at Discovery/Demo a null amount is expected (nothing priced until
    # the formal quote, stage 04), so it must NOT alarm there (QA loop 2026-06-24).
    if deal["is_open"] and deal["stage"] in ("Quote","Verbal") and not deal.get("amount"):
        a.append({"sev":"high","text":f"No deal amount set at {deal['stage']} — pipeline value missing"})
    # Qualify-gate back-stop: a deal PAST the qualify gate (rubric_stage roi|prop = Demo+/Proposal)
    # that still scores DISQUALIFY means the Stage-2 gate (BANT≥50 + fit) was bypassed when the AE
    # advanced it in HubSpot, and nothing surfaced the contradiction — the silent bypass applied to
    # the FIRST gate. Detect-and-flag ONLY: disqualifying / moving the stage is a live HubSpot write
    # the AE owns. Deals still AT Discovery with a DISQUALIFY rec are NOT flagged — the gate is doing
    # its job there. (QA loop 2026-06-24 — Church of Jesus Christ at Demo rec=DISQUALIFY; Gila River
    # + tKW Capital at Quote/Verbal on a T4 fit-fail.)
    _bant = deal.get("bant") or {}
    if deal["is_open"] and deal.get("rubric_stage") in ("roi","prop") and _bant.get("rec") == "DISQUALIFY":
        _why = _bant.get("rec_reason") or f"BANT {_bant.get('total')}"
        a.append({"sev":"high","text":f"Advanced to {deal['stage']} but qualification = DISQUALIFY ({_why}) — disqualify, or document why it's still live"})
    # Unscored-past-gate (sibling of the DISQUALIFY back-stop above): advanced PAST the qualify gate but
    # NEVER scored at all — bant is null / rec / total is None — because no call/transcript is bound, so
    # the rubric never executed. The gate did not merely FAIL here, it never RAN, yet the deal moved to
    # Demo+/Proposal anyway. The cockpit otherwise shows a BLANK BANT panel, which reads as "nothing to
    # see" rather than the truth: never qualified. Detect-and-flag only — binding the missing discovery
    # call or disqualifying is the AE's live action. Discovery-stage deals with no score are EXPECTED
    # (call not yet held) and are NOT flagged. A null verdict is NOT a failing verdict — never render it
    # as DISQUALIFY; it's a coverage gap. (QA loop 2026-06-24 — Cotulla Education x2 at Quote, $75k each,
    # calls=0 / deal_id=None: a $150k slice of pipeline past the gate with zero qualification on record;
    # same broken-deal_id / transcript-binding family as the dup-deal finding.)
    elif deal["is_open"] and deal.get("rubric_stage") in ("roi","prop") and (_bant.get("rec") is None or _bant.get("total") is None):
        a.append({"sev":"high","text":f"Advanced to {deal['stage']} but never qualified — no BANT on record (no call/transcript bound); bind the discovery call, or qualify/disqualify before advancing"})
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
