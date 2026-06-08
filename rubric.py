"""rubric.py — the deal source-of-truth rubric, organized by sales-cycle stage.

Each stage = the key Quinn-Shape / sales vectors an AE must CAPTURE at that point.
Reps capture/take notes against it; AI pre-fills what it can from calls (Accept/edit).
Grounded in Grant's checklist + the Sales KB (sales-motion/*) + the qualification decks.

item: id, label, hint, type(text|number|money|enum|yesno), options(enum), gate(hard must-have)
"""

STAGES = [
  {"key":"pre","name":"Pre-Discovery","blurb":"Context to gather before the first call",
   "items":[
     {"id":"pd_size","label":"Company size band","hint":"Headcount from LinkedIn/site. Quinn shape is 100–1,000; 1,000+ routes to Arlen.","type":"enum","options":["51–200","201–1,000","1,000+","<50"],"gate":True},
     {"id":"pd_field","label":"Field-team size (est.)","hint":"Frontline/deskless techs. Below ~50 field techs = likely disqualify.","type":"number","gate":True},
     {"id":"pd_sites","label":"# sites / locations","hint":"Branches/territories. 3+ sites is on-shape.","type":"number"},
     {"id":"pd_vertical","label":"Sub-vertical","hint":"HVAC, plumbing, pest, electrical, roofing, restoration, etc.","type":"text"},
     {"id":"pd_lms","label":"Current LMS?","hint":"Switching-or-none is on-shape; entrenched + happy is not.","type":"enum","options":["None","Has LMS","Unknown"]},
     {"id":"pd_title","label":"Champion title","hint":"Want VP Ops / COO / Training Director. HR-only = multi-thread, don't advance.","type":"text","gate":True},
     {"id":"pd_whynow","label":"Why-now signal","hint":"Hiring push, expansion/new branches, system switch, compliance/audit.","type":"text"},
   ]},
  {"key":"disc","name":"Discovery","blurb":"Pain in their words, scope, and the buyer map",
   "items":[
     {"id":"d_pain","label":"Pain statement","hint":"Layer 1 (process) + Layer 2 (friction), prospect-led. \"[Co] is losing [X] because [Y].\"","type":"text","gate":True},
     {"id":"d_quant","label":"Pain quantified / path","hint":"Layer 3 — they own the number, or enough math to calc before Call 2.","type":"money"},
     {"id":"d_frontline","label":"Frontline headcount in scope","hint":"\"How big is your frontline team today?\" Confirms the ≥50-tech floor.","type":"number","gate":True},
     {"id":"d_branches","label":"# branches / locations","hint":"\"How many locations would this cover?\"","type":"number"},
     {"id":"d_hiring","label":"Hiring frequency / volume","hint":"\"How often are you hiring? How many new hires this year?\"","type":"text"},
     {"id":"d_system","label":"Current system (LMS)","hint":"LMS in place, training process, or None. Capture Replace/Add/SCORM read.","type":"enum","options":["None","Has LMS — replacing","Has LMS — keeping"],"gate":True},
     {"id":"d_lmssat","label":"LMS satisfaction","hint":"Entrenched + happy = disqualify. N/A if no LMS.","type":"enum","options":["Happy","Neutral","Replacing","N/A"],"gate":True},
     {"id":"d_owner","label":"Operational owner","hint":"Who owns the problem day-to-day; read on champion strength.","type":"text","gate":True},
     {"id":"d_eb","label":"Economic buyer / approver","hint":"CFO/CEO/COO — NOT HR. Name + sign-off threshold.","type":"text","gate":True},
     {"id":"d_stake2","label":"Second stakeholder","hint":"At least one named beyond owner + buyer. VP+ AND a 2nd within 14 days.","type":"text","gate":True},
     {"id":"d_event","label":"Compelling event","hint":"Specific trigger + timing. \"Why now? If unsolved in 6 months, what gets worse?\"","type":"text"},
   ]},
  {"key":"roi","name":"ROI / Demo","blurb":"Quantify the $ with the DM in the room, prove it live",
   "items":[
     {"id":"m_dm","label":"Decision-maker present","hint":"Economic buyer actually on the call. If not — postpone.","type":"yesno","gate":True},
     {"id":"m_cost","label":"Annual pain cost ($)","hint":"The headline addressable $/yr, quantified live (first 8 min). Feeds the ROI calc below.","type":"money","gate":True},
     {"id":"m_demo","label":"Custom artifact delivered","hint":"Course/sim built from THEIR materials, shown live.","type":"yesno","gate":True},
     {"id":"m_agree","label":"DM agreed on ROI math","hint":"\"Does that math feel right? Anything you'd push back on?\"","type":"yesno"},
     {"id":"m_scope","label":"Proposed scope locked","hint":"CC-only vs CC+LMS, learner count, branches, languages, term.","type":"text","gate":True},
     {"id":"m_next","label":"Proposal call booked","hint":"All DMs; invite accepted before hangup.","type":"yesno","gate":True},
   ]},
  {"key":"prop","name":"Proposal","blurb":"Surface objections, anchor to pain, lock the commit",
   "items":[
     {"id":"p_obj","label":"Objections surfaced first","hint":"Make them speak BEFORE the number. \"Anything that'd hold you back?\"","type":"yesno","gate":True},
     {"id":"p_objlog","label":"Objections logged","hint":"Each objection + the response given.","type":"text"},
     {"id":"p_price","label":"Pricing structured","hint":"Flat-rate, tied to ROI (\"vs $Y pain, payback in Z mo\").","type":"money","gate":True},
     {"id":"p_arlen","label":"Arlen sign-off","hint":"250–500 emp notify Arlen; 500+ Arlen leads; >15% discount = stop, call Arlen.","type":"enum","options":["Not needed","Notified","Arlen leads"],"gate":True},
     {"id":"p_commit","label":"Verbal commit status","hint":"\"At $X with [scope], are we aligned?\"","type":"enum","options":["Committed","Unblocking step defined","Lost"],"gate":True},
     {"id":"p_onboard","label":"Onboarding scheduled","hint":"Booked live, 5–10 business days out, invite accepted.","type":"yesno","gate":True},
   ]},
]

# HubSpot stage id -> which rubric stage is "current" (expanded by default)
HS_TO_STAGE = {"1090549665":"disc","1090549667":"roi","1104822108":"prop","1329839734":"prop",
               "1090549670":"prop","1090549671":"disc"}

ALL_ITEMS = [it for s in STAGES for it in s["items"]]
ITEM_IDS  = [it["id"] for it in ALL_ITEMS]
def item(iid):
    return next((it for it in ALL_ITEMS if it["id"]==iid), None)
