"""AI layer — our OWN deal intelligence over fresh Gong transcripts + HubSpot emails.

One Claude call per deal (cached by content signature), forced into a structured tool
schema. Extracts RUBRIC FIELD VALUES (so the cockpit auto-fills the source-of-truth
rubric, AE Accepts/edits), a 0-100 Deal Confidence Score, per-call summaries, next
steps, and a draft note. Heuristic fallback when Claude is unavailable. Nothing here
is inherited from QuinnOS.
"""
import os, re, json, hashlib, anthropic
import rubric

MODEL = "claude-sonnet-4-6"
_client = None
def client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client

TOOL = {
  "name": "deal_intelligence",
  "description": "Structured sales intelligence for one deal, grounded ONLY in the provided calls/emails.",
  "input_schema": {
    "type": "object",
    "properties": {
      "dcs": {"type":"object","properties":{
          "score":{"type":"integer","description":"0-100 deal confidence"},
          "pain":{"type":"integer"},"champion":{"type":"integer"},"multi_threading":{"type":"integer"},
          "buying_language":{"type":"integer"},"objection_status":{"type":"integer"},
          "rationale":{"type":"string","description":"2-3 sentences, concrete"}},
        "required":["score","rationale"]},
      "fields": {"type":"array","description":"Rubric values you can determine from evidence. Only include items you're confident about.",
        "items":{"type":"object","properties":{
          "item_id":{"type":"string","enum":rubric.ITEM_IDS},
          "value":{"type":"string","description":"yesno->'yes'/'no'; enum->exact option; number/money->just the number; text->concise"},
          "evidence":{"type":"string","description":"what in the calls/emails supports it"},
          "cite_call_id":{"type":"string"}},"required":["item_id","value"]}},
      "call_summaries":{"type":"array","items":{"type":"object","properties":{
          "call_id":{"type":"string"},"who":{"type":"string"},
          "discussed":{"type":"array","items":{"type":"string"}},
          "sentiment":{"type":"string"},"next_steps":{"type":"array","items":{"type":"string"}}},
          "required":["call_id"]}},
      "next_steps":{"type":"array","items":{"type":"string"}},
      "note":{"type":"string","description":"one-paragraph deal status note in the rep's voice"},
      "loss":{"type":"object","properties":{"reason":{"type":"string"},"lessons":{"type":"string"}}}
    },
    "required":["dcs","note"]
  }
}

def _sig(deal, calls):
    h = hashlib.sha1()
    h.update(json.dumps([deal.get("stage"), deal.get("amount"), sorted(c["id"] for c in calls),
                         [len(c.get("transcript","")) for c in calls], deal.get("n_emails")], sort_keys=True).encode())
    return h.hexdigest()[:16]

def _rubric_prompt():
    out=[]
    for s in rubric.STAGES:
        out.append(f"## {s['name']}")
        for it in s["items"]:
            t=it["type"]+("("+"/".join(it["options"])+")" if it.get("options") else "")
            out.append(f"  {it['id']} [{t}]: {it['label']} — {it['hint']}")
    return "\n".join(out)

def analyze_deal(deal, calls, emails, cache_dir, force=False):
    cdir = os.path.join(cache_dir, "ai"); os.makedirs(cdir, exist_ok=True)
    cpath = os.path.join(cdir, f"{deal['id']}.json")
    sig = _sig(deal, calls)
    if not force and os.path.exists(cpath):
        try:
            cached = json.load(open(cpath))
            if cached.get("sig") == sig and (cached.get("result") or {}).get("engine") == "claude":
                return cached["result"]
        except Exception:
            pass

    closed_lost = deal.get("bucket") == "closed_lost"
    calls_txt = "\n\n".join(
        f"### CALL {c['id']} — {c.get('title','')} ({c.get('date','')[:10]})\n{c.get('transcript','')[:4500]}"
        for c in calls[:6]) or "(no call transcripts available)"
    emails_txt = "\n".join(
        f"- [{e.get('ts','')[:10]} {e.get('dir','')}] {e.get('subject','')}: {e.get('snippet','')[:140]}"
        for e in emails[-8:]) or "(no emails)"
    stake_txt = "; ".join(f"{s['name']} ({s.get('title','')})" for s in deal.get("stakeholders",[])) or "unknown"

    prompt = f"""You are a sharp sales analyst for Quinn — an AI-powered training platform for deskless/field-service workforces (HVAC, plumbing, electrical, pest control, restoration, fire protection, roofing, etc.).

Quinn's value: replaces manual ride-alongs/shadowing with AI-generated courses + simulations built from the customer's own SOPs. Three ROI levers:
1. Onboarding productivity — faster ramp time (weeks off new-hire-to-productive timeline)
2. Quality/callbacks — fewer field errors and customer callbacks via better training
3. Retention — reduced turnover when techs feel supported and skilled up

ICP: 100–1,000 employee companies with 25+ field techs, ideally no current LMS or replacing one.
BANT scoring: Budget(0-20) + Authority(0-20) + Need(0-40) + Timeline(0-20) = 100 total. Threshold to qualify = 50.

Analyze ONE deal using ONLY the evidence below. Be AGGRESSIVE about extracting rubric fields — if a prospect mentions anything about team size, training process, pain points, tools, timeline, budget range, or decision-makers, capture it. Do not invent facts, but DO extract every signal you can find.

DEAL: {deal.get('name')}
Stage: {deal.get('stage_label')}  |  Amount: ${deal.get('amount')}  |  Company: {deal.get('company')} ({deal.get('industry','?')}, {deal.get('employees','?')} employees)
Stakeholders seen: {stake_txt}

RUBRIC — fill ALL `fields` you can determine from the evidence (value formatted per the item's type):
{_rubric_prompt()}

CALL TRANSCRIPTS (chronological — earliest/discovery call first, latest last):
{calls_txt}

RECENT EMAILS:
{emails_txt}

Call deal_intelligence with:
- dcs.score 0-100 (real pain, a champion, multi-threading, buying language, objections handled) + components 0-10 + a concrete rationale.
- fields: BE THOROUGH — extract every rubric item you can support from the evidence. Include BANT scores if you can assess them. Each field needs value + evidence + cite_call_id.
- call_summaries for EACH call (who, 3-5 discussed bullets, sentiment, next_steps).
- next_steps: the rep's 1-3 highest-leverage actions.
- note: one tight paragraph for the CRM.
{"- loss: why this CLOSED-LOST deal was lost + one lesson." if closed_lost else ""}"""

    try:
        msg = client().messages.create(model=MODEL, max_tokens=8000,
            tools=[TOOL], tool_choice={"type":"tool","name":"deal_intelligence"},
            messages=[{"role":"user","content":prompt}])
        result = {}
        for b in msg.content:
            if b.type == "tool_use": result = b.input; break
        result["engine"] = "claude"
        json.dump({"sig": sig, "result": result}, open(cpath,"w"))
        return result
    except Exception as e:
        res = _heuristic(deal, calls, emails); res["engine"]="heuristic"; res["engine_note"]=str(e)[:140]
        json.dump({"sig": sig, "result": res}, open(cpath,"w"))
        return res

# ================================================================= BANT (SOP §2 rubric)
# Lead-scoped BANT, computed from the Gong discovery transcript using the SalesOS SOP's
# OWN rubric — NOT the outdated #gong-notifier n8n algorithm (which we override/sunset).
# Rubric text is verbatim from quinn-sales-os-experiment/sop/gates.md §2 (v0.4); that SOP
# is the single source of truth — keep this constant in sync when the SOP rubric changes.
BANT_RUBRIC_VERSION = "sop-gates-v0.4"
BANT_RUBRIC = """\
BANT SCORING RUBRIC — score ONLY from the transcript evidence. Each component cites a verbatim quote.

BUDGET — x/20
  20 real money allocated and sized for this need · 15 money is solvable, clear willingness to find/redirect ·
  10 no budget but a credible path to secure it · 5 price-sensitive but exploring (pushback, door not closed) ·
  0 hard rejection.

AUTHORITY — x/20  (must be operationally-rooted to reach 20; HR/CHRO/CLO/training-only roles cap at 15)
  20 economic buyer with full signing authority AND ready to decide solo (could say yes next call). Must be
     ops-rooted (CEO/COO/Owner/VP Ops/GM).
  15 one of: (a) clearly-interested ops-rooted buyer with signing authority but needs team consensus;
     (b) strong external operational champion with a named decision-maker + scheduled engagement;
     (c) strong HR/Training champion orchestrating cross-functionally (this is the ceiling for HR/Training).
  10 real champion in evaluation; named decision-maker, escalation step discussed but not active ·
  5 engaged participant without ownership; vague deflection, no named DM · 0 no decision-making structure visible.

NEED — x/40 = Operational Pain (x/20) + Tech Stack (x/10) + Multi-Location (x/5) + Compliance (x/5)
  Operational Pain (x/20):
    20 CRISIS — unprompted, multi-vector quantified pain, actively shopping ASAP (ramp >1wk often 2-4wks ·
       growth/hiring 30%+ of field workforce/yr · callback 20%+ or explicit quality failures hurting revenue ·
       turnover replacing 30%+/yr).
    15 real ongoing pain articulated clearly, amplified by growth/hiring, wants to fix this year (ramp 3-7d a
       real cost · hiring 15-30%/yr or named scaling plans · callback 10-20% or one quantified issue ·
       elevated-not-bleeding turnover).
    10 present + acknowledged but coping, no amplifier, often single-vector, no $ attached.
    5 general desire to improve, no current pain, future-oriented, status quo works · 0 explicitly stable.
  Tech Stack (x/10):
    10 no LMS · 5 has an LMS but unhappy/not functioning for the FIELD population or intends to replace
       (renewal <3mo counts) · 0 well-adopted satisfactory LMS OR renewal 3+ months OR not discussed.
  Multi-Location (x/5): 5 = 3+ locations · 0 = 1-2.
  Compliance (x/5): 5 = specific regulatory framework named (OSHA, DOT, HIPAA, EPA, FDA, ASE, fire code...) or
    compliance/cert described as a pain · 0 not mentioned.

TIMELINE — x/20
  20 active buying now (~1mo), specific urgency event (audit/launch/deadline) · 15 near-term (~2mo), specific
  trigger or confident window · 10 named window, no specific trigger ("this summer","Q3") · 5 vague intent
  ("sometime this year") · 0 pure fact-finding.

ALSO EXTRACT (for fit + funnel columns):
  field_workers: the number of FIELD workers they would be looking to TRAIN in the context of THIS buying
    conversation (preferred); if only a total-company figure is stated, use that and note it. null if unknown.
  lms_has: "yes" if they use any LMS/training software, "no" if explicitly none, "unknown" if not discussed.
  lms_which: the named product if stated (e.g. "Cornerstone", "ADP"), else "".
"""

_COMP = {
  "score":{"type":"integer"},
  "rationale":{"type":"string","description":"1-2 sentences: HOW and WHY it scored this, per the rubric band."},
  "quote":{"type":"string","description":"verbatim supporting quote from the transcript, or '' if none"}
}
BANT_TOOL = {
  "name":"bant_score",
  "description":"Score a Discovery call on the SalesOS BANT rubric, grounded ONLY in the transcript.",
  "input_schema":{"type":"object","properties":{
    "budget":{"type":"object","properties":dict(_COMP),"required":["score","rationale"]},
    "authority":{"type":"object","properties":dict(_COMP),"required":["score","rationale"]},
    "need":{"type":"object","properties":{
        "operational_pain":{"type":"object","properties":dict(_COMP),"required":["score","rationale"]},
        "tech_stack":{"type":"object","properties":dict(_COMP),"required":["score","rationale"]},
        "multi_location":{"type":"object","properties":dict(_COMP),"required":["score","rationale"]},
        "compliance":{"type":"object","properties":dict(_COMP),"required":["score","rationale"]}},
      "required":["operational_pain","tech_stack","multi_location","compliance"]},
    "timeline":{"type":"object","properties":dict(_COMP),"required":["score","rationale"]},
    "field_workers":{"type":["integer","null"],"description":"# field workers they'd TRAIN in this deal; null if unknown"},
    "field_workers_note":{"type":"string","description":"'training scope' or 'company total' — which the number reflects"},
    "lms_has":{"type":"string","enum":["yes","no","unknown"]},
    "lms_which":{"type":"string"},
    "summary":{"type":"string","description":"one-line overall read of the lead's qualification"}
  },"required":["budget","authority","need","timeline"]}
}

def _bant_sig(text):
    h = hashlib.sha1(); h.update((BANT_RUBRIC_VERSION+"|"+(text or "")).encode()); return h.hexdigest()[:16]

def score_bant(transcript, ctx, cache_dir, lead_key, force=False):
    """Compute lead-scoped BANT from a discovery transcript via the SOP rubric.
    ctx: {company, employees, contact_title, vertical, tier}. Returns the raw component
    scorecard (scores+subscores+rationale+quote+field_workers+lms); the qualify/disqualify
    recommendation + floors are computed by the caller (combines BANT with fit routing).
    Returns None if there's no transcript to score."""
    if not (transcript or "").strip():
        return None
    cdir = os.path.join(cache_dir, "bant"); os.makedirs(cdir, exist_ok=True)
    cpath = os.path.join(cdir, f"{lead_key}.json")
    sig = _bant_sig(transcript)
    if not force and os.path.exists(cpath):
        try:
            cached = json.load(open(cpath))
            if cached.get("sig") == sig and (cached.get("result") or {}).get("engine") == "claude":
                return cached["result"]
        except Exception:
            pass
    prompt = f"""You are Quinn's sales qualification analyst. Quinn is an AI training platform for deskless/field-service workforces (HVAC, plumbing, electrical, pest control, restoration, roofing, etc.) — it replaces manual ride-alongs with AI courses built from the customer's own SOPs (ROI levers: faster onboarding ramp, fewer callbacks/quality issues, lower turnover).

Score this Discovery call STRICTLY on the rubric below. Use ONLY the transcript — do not invent facts. For every component give the score, a 1-2 sentence rationale tied to the rubric band, and a verbatim quote (or '' if none).

LEAD: {ctx.get('company','?')} — {ctx.get('employees','?')} employees · primary contact title: {ctx.get('contact_title','?')} · vertical/tier (pre-call): {ctx.get('vertical','?')} / {ctx.get('tier','?')}

{BANT_RUBRIC}

TRANSCRIPT:
{(transcript or '')[:14000]}

Call bant_score with every component scored."""
    try:
        msg = client().messages.create(model=MODEL, max_tokens=3500,
            tools=[BANT_TOOL], tool_choice={"type":"tool","name":"bant_score"},
            messages=[{"role":"user","content":prompt}])
        result = {}
        for b in msg.content:
            if b.type == "tool_use": result = b.input; break
        result["engine"] = "claude"; result["rubric_version"] = BANT_RUBRIC_VERSION
        json.dump({"sig": sig, "result": result}, open(cpath,"w"))
        return result
    except Exception as e:
        return {"engine":"error","error":str(e)[:140]}

# ----------------------------------------------------------------- heuristic fallback
PAIN_KW=["pain","problem","struggle","challenge","headache","bottleneck","turnover","callback","ramp","onboard","compliance","manual","inconsistent","tribal","retention"]
BUY_KW =["pricing","price","budget","cost","contract","proposal","timeline","when can we","sign","move forward","next step","roi","invest"]
OBJ_KW =["concern","worried","hesitant","expensive","not sure","competitor","already have","objection","pushback"]
LMS_KW =["lms","ukg","adp","cornerstone","articulate","docebo","paycom","workday","training system","scorm"]
SENIOR =re.compile(r"\b(vp|vice president|chief|coo|ceo|cfo|cio|chro|president|owner|founder|head of|director)\b",re.I)
EB_RE  =re.compile(r"\b(coo|ceo|cfo|owner|founder|president|chief)\b",re.I)

def _blob(calls): return " ".join((c.get("transcript","") or "") for c in calls).lower()
def _hits(b,kw): return sum(1 for k in kw if k in b)

def _heuristic(deal, calls, emails):
    blob=_blob(calls); stakes=deal.get("stakeholders",[])
    senior=[s for s in stakes if SENIOR.search(s.get("title") or "")]
    eb=[s for s in stakes if EB_RE.search(s.get("title") or "")]
    pain=min(10,_hits(blob,PAIN_KW)*2); buying=min(10,_hits(blob,BUY_KW)*2)
    obj=min(10,10-_hits(blob,OBJ_KW)*2) if blob else 5; multi=min(10,len(stakes)*3)
    champ=7 if senior else (4 if stakes else 2)
    score=int(round((pain*0.25+champ*0.2+multi*0.2+buying*0.2+obj*0.15)*10)) if blob else None
    emp=deal.get("employees")
    fields=[]
    def f(iid,val,ev): fields.append({"item_id":iid,"value":str(val),"evidence":ev,"cite_call_id":(calls[0]["id"] if calls else None)})
    if emp:
        band="<50" if emp<50 else "50–200" if emp<=200 else "201–1,000" if emp<=1000 else "1,000+"
        f("pd_size",band,f"~{emp} employees on file")
        f("pd_field",int(emp),f"~{emp} employees on file (estimate, confirm field split)")
    if len(stakes)>=1 and stakes[0].get("name"): f("d_decision",stakes[0]["name"]+(f" — {stakes[0]['title']}" if stakes[0].get('title') else ""),"primary contact on calls")
    if senior: f("m_dm","yes","senior stakeholder present on calls")
    if _hits(blob,LMS_KW): f("d_tools","Has platform — keeping","LMS/platform mentioned on calls")
    summaries=[{"call_id":c["id"],"who":"; ".join(s["name"] for s in stakes[:3]) or "—","discussed":[],"sentiment":"","next_steps":[]} for c in calls[:5]]
    note=(f"{deal.get('company')} — {deal.get('stage_label')} stage, ${deal.get('amount')}. {len(stakes)} stakeholder(s)"
          f"{' incl. a decision-maker' if senior else ''}. Heuristic read: pain {pain}/10, buying {buying}/10. "
          f"Add Anthropic credits + Full sync for Claude analysis.")
    return {"dcs":{"score":score,"pain":pain,"champion":champ,"multi_threading":multi,"buying_language":buying,
                   "objection_status":obj,"rationale":"Heuristic estimate from transcript keywords + stakeholder signals (Claude unavailable)."},
            "fields":fields,"call_summaries":summaries,"next_steps":[],"note":note}
