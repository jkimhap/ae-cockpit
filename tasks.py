"""tasks.py — derive the SalesOS Cockpit Task Inbox from the assembled deal snapshot.

  ┌─────────────────────────────────────────────────────────────────────────┐
  │ PHASE 0 — HEURISTIC, NOT EVENT-DRIVEN.                                     │
  │ There is no event/timer runtime yet (that is Phase 2 of REPURPOSE-PLAN).  │
  │ These tasks are derived *heuristically from the current assembled deal    │
  │ snapshot* so the Inbox is populated and demonstrates the two-pane shape   │
  │ on live deals. They approximate the SalesOS wake/trigger model but do NOT │
  │ run on a real clock or off real Gong/HubSpot/email events.                │
  │                                                                            │
  │ In Phase 2 this module is REPLACED by the real wake runtime (poll_changes │
  │ + the activation agent emitting `{deal, type, payload, owner,             │
  │ gate_it_satisfies, status}` tasks). The UI consumes the SAME task shape,  │
  │ so the swap should not touch ui.py.                                       │
  └─────────────────────────────────────────────────────────────────────────┘

Task shape (the contract the UI renders):
    {
      "id":       stable string id (dedup-friendly),
      "deal_id":  HubSpot deal id this task is about,
      "type":     one of TASK_TYPES (Call Prep / Draft Follow-up / Gate-Capture /
                  Routing-Check / Multi-thread / Watch),
      "title":    short action label (the "what"),
      "why":      one-line "why now" (the trigger that would have woken the agent),
      "owner":    the AE the task is for (rep display name),
      "urgency":  one of "overdue" | "today" | "upcoming",
      "company":  deal/company name (for the inbox row),
      "section":  which right-pane section to focus when clicked
                  (one of: "prep","followup","gate","stakeholders","routing","activity"),
      "section_stage": rubric stage key to expand for gate/prep tasks ("disc"/"roi"/"prop"),
    }

The urgency buckets mirror the SOP inbox ("the inbox only surfaces tasks dated
today-or-earlier"): Overdue · Today · Upcoming.
"""
import re
import datetime

import rubric

# Canonical task-type labels (the badges in the inbox). Order = display priority.
TASK_TYPES = ["Routing-Check", "Call Prep", "Draft Follow-up", "Gate-Capture",
              "Multi-thread", "Watch"]

# Heuristic thresholds (Phase-0 stand-ins for the SOP's time-driven triggers).
# REPURPOSE-PLAN "Time-driven": prep ~2h pre-meeting, recap 30m post-call,
# quote age 14/30d, 2nd stakeholder 48h, inactive 21d.
PREP_WINDOW_DAYS   = 3    # an upcoming meeting within N days -> Call Prep
QUOTE_AGING_DAYS   = 14   # a Quote/Verbal deal sitting this long -> follow-up
STALE_DAYS         = 21   # no activity in N days -> Watch (kill-risk check)
SENIOR = re.compile(r"\b(vp|vice president|chief|coo|ceo|cfo|cio|chro|president|owner|founder|head of|director)\b", re.I)


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _parse_ts(s):
    """Best-effort parse of the mixed timestamp strings in the payload."""
    if not s or s == "0":
        return None
    try:
        s = str(s).replace("Z", "+00:00")
        if "T" in s:
            dt = datetime.datetime.fromisoformat(s)
        else:
            dt = datetime.datetime.fromisoformat(s.split(".")[0])
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt
    except Exception:
        return None


def _days_until(s):
    dt = _parse_ts(s)
    if not dt:
        return None
    return (dt - _now()).total_seconds() / 86400.0


def _days_since_iso(s):
    dt = _parse_ts(s)
    if not dt:
        return None
    return (_now() - dt).total_seconds() / 86400.0


def _last_activity_days(deal):
    """Days since the most recent timeline entry (calls/emails/meetings/notes/stage)."""
    best = None
    for t in deal.get("timeline", []):
        d = _days_since_iso(t.get("ts"))
        if d is not None and (best is None or d < best):
            best = d
    return best


def _norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _meeting_matches_deal(meeting, deal):
    """Phase-0 fuzzy match: does this upcoming meeting belong to this deal?

    Upcoming meetings carry generic titles ("Quinn <> <Company> Discussion") and
    arrive with deal_id=None from assemble.py (its exact company-name match misses).
    We re-match on a normalized substring of the company name — good enough to
    demo Call Prep, and explicitly heuristic.
    """
    if meeting.get("deal_id") and meeting["deal_id"] == deal["id"]:
        return True
    co = _norm(deal.get("company"))
    title = _norm(meeting.get("company") or meeting.get("title"))
    if not co or not title:
        return False
    # require a reasonably distinctive company token to avoid false hits
    return len(co) >= 4 and co in title


def _urgency_from_days(days_from_now, default="today"):
    """Map a due-offset (in days, negative = past) to an inbox bucket."""
    if days_from_now is None:
        return default
    if days_from_now < -0.01:
        return "overdue"
    if days_from_now <= 1.0:
        return "today"
    return "upcoming"


def _mk(deal, owner, ttype, title, why, urgency, section, stage=None, suffix=""):
    return {
        "id": f"{deal['id']}:{ttype}:{suffix}".rstrip(":"),
        "deal_id": deal["id"],
        "type": ttype,
        "title": title,
        "why": why,
        "owner": owner,
        "urgency": urgency,
        "company": deal.get("company") or "Unnamed deal",
        "section": section,
        "section_stage": stage or deal.get("rubric_stage"),
    }


def _unmet_gates(deal):
    """Gate items on the deal's CURRENT rubric stage that have no value yet.

    Phase-0 note: capture state lives in the browser (localStorage), so the
    server can't see what the AE already filled. We therefore surface a
    Gate-Capture task when the stage HAS gates and the deal has thin evidence
    (proxy for "gates likely unmet"): no AI autofill + low BANT/short history.
    The UI can refine this against localStorage; here we approximate.
    """
    stage = next((s for s in rubric.STAGES if s["key"] == deal.get("rubric_stage")), None)
    if not stage:
        return []
    return [it for it in stage["items"] if it.get("gate")]


def derive_tasks(payload):
    """Return the heuristic Task Inbox for an assembled payload.

    Pure function of the snapshot — no clock-driven side effects, no writes.
    """
    owner = payload.get("rep") or ""
    deals = payload.get("deals", [])
    upcoming = payload.get("upcoming", [])
    open_deals = [d for d in deals if d.get("is_open")]
    tasks = []

    for d in open_deals:
        stage = d.get("stage") or ""
        rstage = d.get("rubric_stage") or "disc"
        dis = (d.get("dcs") or {}).get("days_in_stage")
        stk = d.get("stakeholders") or []
        amount = d.get("amount") or 0
        employees = d.get("employees") or 0
        last_act = _last_activity_days(d)
        has_senior = any(SENIOR.search(s.get("title") or "") for s in stk)

        # ---- Routing-Check (SOP "Deal routing": large/strategic -> Arlen) -------
        # large ≈ >~$40k or 100+ field workers; strategic ≈ 1,000+ employees.
        # Phase-0 proxy: flag big/strategic deals and deals with no stakeholder
        # identity at all (a stand-in for "lacking a clear owner/contact").
        if amount and amount > 40000:
            tasks.append(_mk(
                d, owner, "Routing-Check",
                "Confirm routing — large deal",
                f"${int(amount):,} exceeds the ~$40k large-deal line — verify it shouldn't route to Arlen.",
                "today", "routing"))
        elif employees and employees >= 1000:
            tasks.append(_mk(
                d, owner, "Routing-Check",
                "Confirm routing — strategic size",
                f"{int(employees):,} employees — strategic-size deal; confirm ownership vs. Arlen.",
                "today", "routing"))
        elif not stk:
            tasks.append(_mk(
                d, owner, "Routing-Check",
                "No contact on file",
                "Deal has no known stakeholder — confirm routing/ownership before working it.",
                "overdue", "routing"))

        # ---- Call Prep (time-driven: ~2h pre-meeting) ---------------------------
        upcoming_for_deal = sorted(
            (m for m in upcoming if _meeting_matches_deal(m, d)),
            key=lambda m: m.get("start") or "")
        if upcoming_for_deal:
            m = upcoming_for_deal[0]
            du = _days_until(m.get("start"))
            if du is not None and du <= PREP_WINDOW_DAYS:
                tasks.append(_mk(
                    d, owner, "Call Prep",
                    "Prep sheet for upcoming call",
                    f"Meeting {('today' if du is not None and du <= 1 else 'in ' + str(max(1, round(du))) + 'd')} — prep sheet must exist before the call.",
                    _urgency_from_days(du), "prep", stage=rstage,
                    suffix=str(m.get("start") or "")[:10]))
        elif rstage == "disc" and dis is not None and dis <= 7 and (d.get("calls") or d.get("emails")):
            # No meeting data, but an early-stage recently-active deal -> prep proxy.
            tasks.append(_mk(
                d, owner, "Call Prep",
                "Prep sheet for Discovery",
                f"Early-stage and active ({dis}d in {stage}) — have a Discovery prep sheet ready.",
                "upcoming", "prep", stage=rstage))

        # ---- Draft Follow-up / Recap (recent call, stage not advancing; or aging quote)
        if rstage in ("prop",) and dis is not None and dis >= QUOTE_AGING_DAYS:
            tasks.append(_mk(
                d, owner, "Draft Follow-up",
                "Follow up on aging quote",
                f"{dis}d in {stage} with no advance — draft a nudge to keep the quote alive.",
                "overdue" if dis >= QUOTE_AGING_DAYS * 2 else "today", "followup", stage=rstage))
        elif last_act is not None and 0.5 <= last_act <= 10 and dis is not None and dis > last_act + 2:
            # A recent touch happened but the stage hasn't moved since -> recap/nudge.
            tasks.append(_mk(
                d, owner, "Draft Follow-up",
                "Send post-call follow-up",
                f"Last activity {round(last_act)}d ago but still in {stage} ({dis}d) — draft the recap/next-step.",
                "today", "followup", stage=rstage))

        # ---- Gate-Capture (current stage has gate fields) -----------------------
        gates = _unmet_gates(d)
        # Surface when the stage has gates AND there's no AI autofill waiting
        # (so the AE has to capture them) — heuristic proxy for "gates unmet".
        if gates and not d.get("ai_fields"):
            stage_name = next((s["name"] for s in rubric.STAGES if s["key"] == rstage), stage)
            tasks.append(_mk(
                d, owner, "Gate-Capture",
                f"Capture {stage_name} gate fields",
                f"{len(gates)} gate field(s) on {stage_name} — capture them to advance the stage.",
                "today", "gate", stage=rstage))

        # ---- Multi-thread (single-threaded deal) --------------------------------
        if len(stk) < 2:
            tasks.append(_mk(
                d, owner, "Multi-thread",
                "Add a 2nd stakeholder",
                f"Single-threaded ({len(stk)} contact) — single-threading is the #1 post-Discovery killer.",
                "today", "stakeholders"))
        elif not has_senior:
            tasks.append(_mk(
                d, owner, "Multi-thread",
                "Reach a decision-maker",
                "No VP+/decision-maker engaged yet — multi-thread up before advancing.",
                "upcoming", "stakeholders"))

        # ---- Watch (no recent activity -> scheduled kill-risk check) ------------
        if last_act is not None and last_act >= STALE_DAYS:
            tasks.append(_mk(
                d, owner, "Watch",
                "Kill-risk check — gone quiet",
                f"No activity in {round(last_act)}d (past the {STALE_DAYS}d inactivity line) — watch for stall.",
                "overdue", "activity"))

    return _prioritize(tasks)


# Inbox sort: overdue first, then by task-type priority, then company name.
_URGENCY_RANK = {"overdue": 0, "today": 1, "upcoming": 2}


def _prioritize(tasks):
    type_rank = {t: i for i, t in enumerate(TASK_TYPES)}
    return sorted(
        tasks,
        key=lambda t: (_URGENCY_RANK.get(t["urgency"], 3),
                       type_rank.get(t["type"], 99),
                       t["company"].lower()))


def grouped(payload):
    """Convenience: tasks already split into the three inbox buckets + counts."""
    tasks = derive_tasks(payload)
    buckets = {"overdue": [], "today": [], "upcoming": []}
    for t in tasks:
        buckets.get(t["urgency"], buckets["today"]).append(t)
    return {"tasks": tasks,
            "buckets": buckets,
            "counts": {k: len(v) for k, v in buckets.items()},
            "total": len(tasks),
            # Phase-0 banner the UI shows so nobody mistakes these for real events.
            "heuristic": True}
