"""rubric.py — the deal source-of-truth rubric, aligned to Quinn's 3-call playbook.

Stages mirror the actual AE workflow:
  1. Pre-Call Intel  — auto-populated lead scorecard before Discovery
  2. Discovery       — Call 1: Pain + Qualification (30 min)
  3. Demo + ROI      — Call 2: Custom demo + ROI quantification (45 min)
  4. Proposal & Close — Call 3: Proposal, objections, verbal close (30 min)

Each item has: id, label, hint (the actual question/prompt to use), type, options, gate.
"prompt" fields are the actual talk-track the AE should use on the call.
"""

STAGES = [
  {"key": "pre", "name": "Pre-Call Intel", "blurb": "Lead scorecard — know before you dial",
   "items": [
     {"id": "pd_field", "label": "Field-team size", "hint": "Frontline/deskless techs. <25 + active LMS = disqualify. 100+ = route to Arlen.", "type": "number", "gate": True},
     {"id": "pd_lms", "label": "Current LMS?", "hint": "None or replacing = on-shape. Entrenched + happy = off-shape.", "type": "enum", "options": ["None", "Has LMS — replacing", "Has LMS — happy", "Unknown"], "gate": True},
     {"id": "pd_size", "label": "Company size", "hint": "Total headcount. Quinn shape: 100–1,000. 1,000+ routes to Arlen.", "type": "enum", "options": ["<50", "50–200", "201–1,000", "1,000+"]},
     {"id": "pd_vertical", "label": "Industry / vertical", "hint": "HVAC, plumbing, pest, electrical, roofing, restoration, fire protection, etc.", "type": "text"},
     {"id": "pd_sites", "label": "# locations", "hint": "3+ sites is on-shape.", "type": "number"},
     {"id": "pd_title", "label": "Champion title", "hint": "VP Ops / COO / Training Dir = strong. HR-only = multi-thread before advancing.", "type": "text"},
     {"id": "pd_source", "label": "Lead source", "hint": "Cold call, conference, email, LinkedIn, ad, organic. High-intel sources signal more intent.", "type": "text"},
     {"id": "pd_whynow", "label": "Why-now signal", "hint": "Hiring push, expansion, system switch, compliance audit, LMS renewal.", "type": "text"},
   ]},

  {"key": "disc", "name": "Discovery", "blurb": "Call 1 — Pain + Qualification (30 min)",
   "items": [
     # --- Core discovery questions (in call order) ---
     {"id": "d_scale", "label": "Scale", "hint": "How many people do you train in a given year? How many new hires planned?", "type": "text", "prompt": "How many people do you train in a given year? How many new hires are you planning to onboard?"},
     {"id": "d_process", "label": "Current process", "hint": "Walk me through training today — hire to fully productive.", "type": "text", "prompt": "Walk me through training today — from the day someone is hired to when they're fully productive."},
     {"id": "d_tools", "label": "Tools / platforms", "hint": "Any platforms, or mostly manual — ride-alongs, shadowing, checklists?", "type": "enum", "options": ["None / manual", "Has platform — replacing", "Has platform — keeping"], "gate": True, "prompt": "Are you using any platforms today, or is it mostly manual — ride-alongs, shadowing, paper checklists?"},
     {"id": "d_pain", "label": "Pain statement", "hint": "In their words: what's giving the most headaches on training right now?", "type": "text", "gate": True, "prompt": "What's giving you the most headaches on the training side right now?"},
     {"id": "d_priority", "label": "One thing to fix", "hint": "If you could fix one thing about training today, what would it be?", "type": "text", "prompt": "If you could fix one thing about how training works today, what would it be?"},
     {"id": "d_decision", "label": "Decision map", "hint": "Who else is typically involved in a decision about a new training tool?", "type": "text", "gate": True, "prompt": "When it comes to a new training tool, who else would typically be involved in that decision?"},
     # --- Qualification signals ---
     {"id": "d_timeline", "label": "Timeline / urgency", "hint": "Is this 'needed yesterday' or more next-quarter?", "type": "enum", "options": ["Urgent (this month)", "Near-term (1–2 months)", "This quarter", "Exploring / no rush"], "prompt": "Is this a 'we needed this yesterday' situation, or more of a next-quarter priority?"},
     {"id": "d_competition", "label": "Competition", "hint": "Evaluating other solutions or exploratory?", "type": "enum", "options": ["Not evaluating others", "Evaluating alternatives", "Deep in another eval"], "prompt": "Are you evaluating any other solutions right now, or is this more exploratory?"},
     {"id": "d_budget", "label": "Budget signal", "hint": "Companies typically invest $10K–$50K/yr with Quinn. Reaction?", "type": "enum", "options": ["In range", "Pushback but exploring", "Hard rejection", "Not discussed"], "gate": True, "prompt": "I want to be upfront so there are no surprises — depending on team size, companies typically invest between $10K and $50K annually with Quinn. Does that feel in the right ballpark?"},
     # --- BANT scoring (auto-calculated or manually set) ---
     {"id": "d_bant_b", "label": "Budget score", "hint": "0–20. 20=allocated, 15=solvable, 10=credible path, 5=pushback, 0=hard no.", "type": "number"},
     {"id": "d_bant_a", "label": "Authority score", "hint": "0–20. 20=economic buyer w/ signing authority, 15=buyer needs consensus, 10=champion, 5=participant, 0=none.", "type": "number"},
     {"id": "d_bant_n", "label": "Need score", "hint": "0–40. 20=crisis (multi-vector, quantified, urgent), 15=real ongoing, 10=present but coping, 5=general desire, 0=no pain. +10 Tech Stack (no LMS), +5 Multi-location (3+), +5 Compliance.", "type": "number"},
     {"id": "d_bant_t", "label": "Timeline score", "hint": "0–20. 20=buying NOW, 15=2mo+trigger, 10=named window, 5=vague intent, 0=fact-finding.", "type": "number"},
     {"id": "d_qualify", "label": "Qualification decision", "hint": "BANT ≥50 = Qualify. <50 = Disqualify. 100+ FW + BANT≥50 = re-route to Arlen.", "type": "enum", "options": ["Qualified", "Qualified — route to Arlen (100+ FW)", "Disqualified"], "gate": True},
   ]},

  {"key": "roi", "name": "Demo + ROI", "blurb": "Call 2 — Custom demo + ROI quantification (45 min)",
   "items": [
     {"id": "m_dm", "label": "Decision-maker present", "hint": "Economic buyer on the call. If not — pause and reschedule.", "type": "yesno", "gate": True, "prompt": "Before we dive in — is [economic buyer name] able to join today?"},
     {"id": "m_shifted", "label": "Anything shifted?", "hint": "Since we last spoke, has anything changed on the training side?", "type": "text", "prompt": "Since we last spoke, has anything shifted on the training side — or is [X] still the main thing you're trying to solve?"},
     {"id": "m_demo_reaction", "label": "Demo reaction", "hint": "Their honest reaction to the custom artifact. Watch energy, voice, pacing.", "type": "text"},
     {"id": "m_demo_delivered", "label": "Custom demo delivered", "hint": "Course/sim built from THEIR materials, shown live.", "type": "yesno", "gate": True},
     # --- ROI Discovery ---
     {"id": "m_onboarding", "label": "Onboarding pain", "hint": "What does first 90 days look like? Where do things go sideways?", "type": "text", "prompt": "Walk me through what happens when you bring someone new on — what does the first 90 days look like, and where do things tend to go sideways?"},
     {"id": "m_beyond", "label": "Beyond onboarding", "hint": "Where else does training not keep pace with business needs?", "type": "text", "prompt": "Beyond onboarding — where else does training feel like it's not keeping pace with what the business actually needs?"},
     {"id": "m_cost_source", "label": "Where it costs most", "hint": "Manager time, field errors, or something else?", "type": "text", "prompt": "Where does that end up costing you the most — is it the time your managers are spending, the errors or inconsistencies in the field, or something else?"},
     {"id": "m_annual_cost", "label": "Annual pain cost ($)", "hint": "Their ballpark of total annual cost. Feeds the ROI calculator.", "type": "money", "gate": True, "prompt": "When you add all of that up, what do you think it's costing the business in a given year — even a rough ballpark is helpful?"},
     {"id": "m_vision", "label": "Vision if solved", "hint": "What actually changes for them and the business?", "type": "text", "prompt": "If that problem was solved, what does that actually change for you and the business?"},
     {"id": "m_scope", "label": "Scope locked", "hint": "Learner count, branches, languages, term.", "type": "text", "gate": True},
     {"id": "m_next", "label": "Proposal call booked", "hint": "All DMs; invite accepted before hangup. Never leave without a specific day and time.", "type": "yesno", "gate": True},
   ]},

  {"key": "prop", "name": "Proposal & Close", "blurb": "Call 3 — Proposal, objections, verbal close (30 min)",
   "items": [
     {"id": "p_dm_present", "label": "Decision-maker confirmed", "hint": "Confirm DM is present before opening the deck. If not — reschedule.", "type": "yesno", "gate": True},
     {"id": "p_shifted", "label": "Anything shifted?", "hint": "Before I dive in — has anything shifted on your end since we last spoke?", "type": "text", "prompt": "Before I dive in — has anything shifted on your end since we last spoke?"},
     {"id": "p_obj", "label": "Objections surfaced", "hint": "Make them speak BEFORE the number. Unspoken objection = 'let me think about it'.", "type": "yesno", "gate": True, "prompt": "Before I walk through the options — is there anything that would hold you back from moving forward, assuming the numbers work?"},
     {"id": "p_objlog", "label": "Objections + responses", "hint": "Each objection and how it was handled.", "type": "text"},
     {"id": "p_price", "label": "Pricing presented", "hint": "Restate ROI case FIRST, then walk 2–3 tiered options. Present price, then go silent.", "type": "money", "gate": True},
     {"id": "p_arlen", "label": "Arlen sign-off", "hint": "250–500 emp notify Arlen; 500+ Arlen leads; >15% discount = stop, call Arlen.", "type": "enum", "options": ["Not needed", "Notified", "Arlen leads"], "gate": True},
     {"id": "p_commit", "label": "Verbal commit", "hint": "At [scope] and [price], are we aligned? Book onboarding immediately.", "type": "enum", "options": ["Committed", "Unblocking step defined", "Lost"], "gate": True},
     {"id": "p_onboard", "label": "Onboarding scheduled", "hint": "5–10 business days out, invite accepted. Send paperwork same day.", "type": "yesno", "gate": True},
   ]},
]

# HubSpot stage id -> which rubric stage is "current" (expanded by default)
HS_TO_STAGE = {
    "1090549665": "disc",      # Discovery Complete
    "1090549667": "roi",       # Demo Complete
    "1104822108": "prop",      # Quote Sent
    "1329839734": "prop",      # Verbal Commit
    "1090549670": "prop",      # Closed Won
    "1090549671": "disc",      # Closed Lost
}

ALL_ITEMS = [it for s in STAGES for it in s["items"]]
ITEM_IDS  = [it["id"] for it in ALL_ITEMS]
def item(iid):
    return next((it for it in ALL_ITEMS if it["id"] == iid), None)

# BANT threshold for qualification
BANT_THRESHOLD = 50
BANT_FIELDS = ["d_bant_b", "d_bant_a", "d_bant_n", "d_bant_t"]
