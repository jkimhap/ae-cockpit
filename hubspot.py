"""HubSpot client — reads CRM as the SOURCE OF TRUTH at request time.

No snapshot, no cache of CRM facts: every call hits api.hubapi.com so stages,
amounts, owners, contacts, and the engagement timeline are exactly what's in HubSpot.
"""
import os, time, requests

BASE = "https://api.hubapi.com"
PIPELINE_QUINN = "750234144"

def _headers():
    return {"Authorization": f"Bearer {os.environ['HUBSPOT_API_KEY']}", "Content-Type": "application/json"}

def _req(method, path, **kw):
    for attempt in range(5):
        r = requests.request(method, f"{BASE}{path}", headers=_headers(), timeout=40, **kw)
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(1.5 * (attempt + 1)); continue
        r.raise_for_status()
        return r.json() if r.content else {}
    r.raise_for_status()

def get(path, params=None):  return _req("GET", path, params=params or {})
def post(path, body):        return _req("POST", path, json=body)

# ---- pipeline / owners ----
def pipeline_stages():
    """{stage_id: {label, order, closed_won, closed_lost}}"""
    data = get("/crm/v3/pipelines/deals")
    out = {}
    for pl in data.get("results", []):
        if pl.get("id") != PIPELINE_QUINN:
            continue
        for s in pl.get("stages", []):
            md = s.get("metadata", {}) or {}
            out[s["id"]] = {"label": s["label"], "order": s.get("displayOrder", 0),
                            "won": md.get("isClosed") == "true" and md.get("probability") == "1.0",
                            "closed": md.get("isClosed") == "true"}
    return out

def resolve_owner(slug):
    """Match a rep slug to a HubSpot owner by first name / email local-part."""
    res = get("/crm/v3/owners", {"limit": 100}).get("results", [])
    slug = slug.lower()
    for o in res:
        fn = (o.get("firstName") or "").lower()
        em = (o.get("email") or "").lower()
        if fn == slug or em.split("@")[0].startswith(slug):
            return {"id": o["id"], "name": f"{o.get('firstName','')} {o.get('lastName','')}".strip(), "email": o.get("email","")}
    return None

# ---- generic helpers ----
def search(obj, properties, filters, limit=100):
    out, after = [], None
    while True:
        body = {"filterGroups": [{"filters": filters}], "properties": properties, "limit": limit}
        if after: body["after"] = after
        data = post(f"/crm/v3/objects/{obj}/search", body)
        out.extend(data.get("results", []))
        after = (data.get("paging", {}).get("next", {}) or {}).get("after")
        if not after: break
    return out

def batch_read(obj, ids, properties):
    out = {}
    ids = [str(i) for i in ids if i]
    for i in range(0, len(ids), 100):
        chunk = ids[i:i+100]
        data = post(f"/crm/v3/objects/{obj}/batch/read",
                    {"inputs": [{"id": x} for x in chunk], "properties": properties})
        for r in data.get("results", []):
            out[r["id"]] = r.get("properties", {})
    return out

def assoc(from_obj, to_obj, ids):
    """deal_id -> [associated ids of to_obj] via v4 batch."""
    out = {}
    ids = [str(i) for i in ids if i]
    for i in range(0, len(ids), 100):
        chunk = ids[i:i+100]
        data = post(f"/crm/v4/associations/{from_obj}/{to_obj}/batch/read",
                    {"inputs": [{"id": x} for x in chunk]})
        for r in data.get("results", []):
            fid = str(r["from"]["id"])
            out.setdefault(fid, []).extend(str(t["toObjectId"]) for t in r.get("to", []))
    return out

# ---- domain pulls ----
DEAL_PROPS_BASE = ["dealname","dealstage","amount","pipeline","dealtype","createdate","closedate",
                   "hs_lastmodifieddate","hs_analytics_source","hs_analytics_source_data_1",
                   "num_associated_contacts","description","hs_deal_stage_probability"]

def deals_for_owner(owner_id, stage_ids):
    props = DEAL_PROPS_BASE + [f"hs_v2_date_entered_{s}" for s in stage_ids]
    filters = [{"propertyName":"hubspot_owner_id","operator":"EQ","value":str(owner_id)},
               {"propertyName":"pipeline","operator":"EQ","value":PIPELINE_QUINN}]
    return search("deals", props, filters)

def companies_for(ids):
    return batch_read("companies", ids,
        ["name","domain","industry","industry_category","numberofemployees","annualrevenue",
         "city","state","numberoflocations","description","website","linkedin_company_page"])

def contacts_for(ids):
    # industry_category = the CONTACT "Industry (Quinn)" property — the real ICP vertical.
    # (The HubSpot company `industry` enum is coarse/useless and is not used for vertical/tier.)
    # num_of_learners / lms / which_lms_ are the booking-form answers the internal rep / prospect
    # fills when a Discovery call is booked ("How many frontline workers…", "Do you use software…",
    # "Which LMS?") — they pre-fill the Discovery Booked enrichment row; empty stays empty.
    return batch_read("contacts", ids,
        ["firstname","lastname","email","jobtitle","phone","industry_category",
         "num_of_learners","lms","which_lms_"])

def calls_for(ids):
    return batch_read("calls", ids,
        ["hs_timestamp","hs_call_title","hs_call_body","hs_call_duration","hs_call_direction",
         "hs_call_recording_url","hs_call_disposition"])

def emails_for(ids):
    return batch_read("emails", ids,
        ["hs_timestamp","hs_email_subject","hs_email_text","hs_email_direction","hs_email_html"])

def meetings_for(ids):
    return batch_read("meetings", ids,
        ["hs_timestamp","hs_meeting_title","hs_meeting_start_time","hs_meeting_end_time",
         "hs_meeting_outcome","hs_meeting_body"])

def notes_for(ids):
    return batch_read("notes", ids, ["hs_timestamp","hs_note_body"])

def upcoming_meetings(owner_id, now_iso):
    """Scheduled meetings for this owner with start in the future.
    hs_activity_type + hs_meeting_source let us tell a genuine *first* Discovery call
    (activity_type "First Meeting", booked via the public Meetings link) from follow-up
    demos/proposal calls — so the Discovery Booked tile shows first calls only (Task #19)."""
    filters = [{"propertyName":"hubspot_owner_id","operator":"EQ","value":str(owner_id)},
               {"propertyName":"hs_meeting_start_time","operator":"GT","value":now_iso}]
    try:
        return search("meetings",
            ["hs_meeting_title","hs_meeting_start_time","hs_meeting_outcome",
             "hs_internal_meeting_notes","hs_activity_type","hs_meeting_source"],
            filters)
    except Exception:
        return []
