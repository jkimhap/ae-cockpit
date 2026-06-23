"""dash.py — Dashboard "Trends" data layer for the SalesOS cockpit.

Builds the exact DATA[view][rep][metricKey] structure that the QuinnOS-cloned
Trends renderer (ui.py DASHBOARD_BODY) consumes — computed server-side from the
cached per-rep cockpit payloads. Mirrors quinn-os/build_trends.py semantics,
adapted to the cockpit payload shape:

  * dates come from each deal's `timeline` stage events (no create/close_date
    scalars in the cockpit payload),
  * arr == amount; tcv falls back to arr when HubSpot has no separate TCV,
  * "first" sales call = the earliest Gong call on a deal; follow-ups = the rest.

Each metric series item == [{label, label_hover, value, items:[...]}], one entry
per period, exactly as the renderer's buildSVG()/showPop() expect.
"""
import os, json, datetime as dt
from config import CACHE_DIR, REPS

# ── Canonical names / goals (kept in lockstep with ui.py) ───────────────────
REPNAME = {"grant": "Grant", "arlen": "Arlen", "ian": "Ian", "luke": "Luke"}
OWNER_NAME_BY_ID = {"80532323": "Arlen", "77307934": "Derek", "80723038": "Grant",
                    "80723039": "Ian", "86257981": "Luke", "80734651": "Bo"}
MONTHS_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTHS_FULL = ["January", "February", "March", "April", "May", "June", "July",
               "August", "September", "October", "November", "December"]

TODAY = dt.date.today()
Q2_START = dt.date(2026, 4, 1)
Q2_END = dt.date(2026, 6, 30)

# Q2 GTM plan committed with Arlen (Derek excluded per Johnny). Keyed by rep slug.
Q2_CW_TARGET = {"arlen": 230000, "grant": 100000}
Q2_SRC_TARGET = {"grant": 75000, "luke": 100000, "ian": 90000}
DEAL_SIZE_ASSUMPTION = 17000   # ~avg ACV, for "deals needed" math


# ── Period helpers (ported verbatim from build_trends.py) ───────────────────
def week_of(d):   return d - dt.timedelta(days=d.weekday())   # Monday
def month_of(d):  return d.replace(day=1)

def week_range(weeks_back=8):
    """Last 8 full weeks + current week = 9 columns; each entry is that Monday."""
    cur = week_of(TODAY)
    return [cur - dt.timedelta(weeks=i) for i in range(weeks_back, -1, -1)]

def month_range():
    """Every month since Jan 1 of the current year + the current month."""
    out, y, m = [], TODAY.year, 1
    while True:
        d = dt.date(y, m, 1)
        out.append(d)
        if d.month == TODAY.month and d.year == TODAY.year:
            break
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out

def fmt_week_label(d):
    end = d + dt.timedelta(days=6)         # Sunday end-of-week
    return "%d/%d" % (end.month, end.day)
def fmt_week_hover(d):
    end = d + dt.timedelta(days=6)
    return "Week ending %d/%d" % (end.month, end.day)
def fmt_month_label(d):  return MONTHS_ABBR[d.month - 1]
def fmt_month_hover(d):  return "Month of %s %d" % (MONTHS_FULL[d.month - 1], d.year)

def period_end(p, view):
    if view == "weekly":
        return p + dt.timedelta(days=6)
    nxt = dt.date(p.year + 1, 1, 1) if p.month == 12 else dt.date(p.year, p.month + 1, 1)
    return nxt - dt.timedelta(days=1)

def period_key(view, d):
    if not d:
        return None
    return week_of(d) if view == "weekly" else month_of(d)


# ── Date parsing from cockpit timeline events ───────────────────────────────
def _date(s):
    """ISO-ish string → date. Handles '2026-05-29T19:54:19.060Z' and
    '2026-06-16T09:30:10'. Returns None on anything unparseable."""
    if not s or not isinstance(s, str):
        return None
    try:
        return dt.date(int(s[0:4]), int(s[5:7]), int(s[8:10]))
    except Exception:
        return None

def _stage_events(d):
    return [e for e in (d.get("timeline") or []) if e.get("kind") == "stage" and e.get("ts")]

def created_date(d):
    """Earliest stage transition → the moment the deal entered the pipeline.
    Falls back to the earliest dated timeline event of any kind."""
    se = sorted(e["ts"] for e in _stage_events(d))
    if se:
        return _date(se[0])
    allts = sorted(e["ts"] for e in (d.get("timeline") or []) if e.get("ts"))
    return _date(allts[0]) if allts else None

def closed_date(d, word):
    """Date of the latest stage event whose title mentions `word` (Won/Lost)."""
    ev = sorted(e["ts"] for e in _stage_events(d) if word in (e.get("title") or ""))
    if ev:
        return _date(ev[-1])
    se = sorted(e["ts"] for e in _stage_events(d))
    return _date(se[-1]) if se else created_date(d)

def deal_money(d):
    arr = d.get("arr") or d.get("amount") or 0
    tcv = d.get("tcv") or arr
    return float(arr or 0), float(tcv or 0)

def _owner_label(d):
    rep = d.get("_rep")
    return REPNAME.get(rep, rep or "—")


# ── Payload loading ─────────────────────────────────────────────────────────
def load_payloads():
    """{rep_slug: payload} for every rep with a cached payload that has deals."""
    out = {}
    for rep in REPS:
        p = os.path.join(CACHE_DIR, "payload-%s.json" % rep)
        if not os.path.exists(p):
            continue
        try:
            pl = json.load(open(p))
        except Exception:
            continue
        if pl.get("deals"):
            out[rep] = pl
    return out

def deals_for(payloads, rep):
    """rep == 'all' → every loaded rep's deals (tagged _rep). Else that rep's."""
    out = []
    reps = list(payloads.keys()) if rep == "all" else ([rep] if rep in payloads else [])
    for r in reps:
        for d in (payloads[r].get("deals") or []):
            dd = dict(d); dd["_rep"] = r
            out.append(dd)
    return out


# ── The aggregator: one (view, rep) → {metricKey: series} ───────────────────
def aggregate(view, periods, deals):
    pset = set(periods)

    def blank():
        return {p: [] for p in periods}

    held_first, held_all, held_follow = blank(), blank(), blank()
    created = blank()
    pipe_arr, pipe_tcv = blank(), blank()
    won, lost = blank(), blank()

    for d in deals:
        arr, tcv = deal_money(d)
        company = d.get("company") or "—"
        owner = _owner_label(d)
        hs_id = str(d.get("id") or "")
        hs_url = d.get("hubspot_url") or ""

        # ── Sales calls held (first vs follow-up) ──
        calls = sorted([c for c in (d.get("calls") or []) if c.get("date")],
                       key=lambda c: c["date"])
        for idx, c in enumerate(calls):
            cd = _date(c.get("date"))
            pk = period_key(view, cd)
            if pk not in pset:
                continue
            item = {
                "label": company,
                "sublabel": (c.get("title") or "Sales call") + (
                    " · %dm" % c["duration_min"] if c.get("duration_min") else ""),
                "date": (c.get("date") or "")[:10],
                "gong_id": c.get("gid") or "",
                "gong_url": c.get("url") or "",
                "hubspot_deal_id": hs_id,
                "hubspot_url": hs_url,
            }
            held_all[pk].append(item)
            (held_first if idx == 0 else held_follow)[pk].append(item)

        # ── Deals created (entered the pipeline) ──
        cdt = created_date(d)
        pk = period_key(view, cdt)
        if pk in pset:
            created[pk].append({
                "label": company,
                "sublabel_arr": "$%s ARR · %s" % (format(int(arr), ","), owner),
                "sublabel_tcv": "$%s TCV · %s" % (format(int(tcv), ","), owner),
                "date": cdt.isoformat() if cdt else "",
                "source": d.get("source") or "—",
                "hubspot_deal_id": hs_id,
                "hubspot_url": hs_url,
            })

        # ── Point-in-time open pipeline at each period-end ──
        first_seen = cdt
        cl_word = "Won" if d.get("stage") == "Won" else ("Lost" if d.get("stage") == "Lost" else None)
        cl = closed_date(d, cl_word) if (cl_word and not d.get("is_open")) else None
        if first_seen:
            for p in periods:
                as_of = min(period_end(p, view), TODAY)
                if first_seen > as_of:
                    continue
                if cl and cl <= as_of:
                    continue
                pipe_arr[p].append({"label": company, "value": arr,
                                    "sublabel": "$%s ARR · %s" % (format(int(arr), ","), owner),
                                    "hubspot_deal_id": hs_id, "hubspot_url": hs_url})
                pipe_tcv[p].append({"label": company, "value": tcv,
                                    "sublabel": "$%s TCV · %s" % (format(int(tcv), ","), owner),
                                    "hubspot_deal_id": hs_id, "hubspot_url": hs_url})

        # ── Closed won / lost ──
        if not d.get("is_open") and d.get("stage") in ("Won", "Lost"):
            cl2 = closed_date(d, d["stage"])
            pk = period_key(view, cl2)
            if pk in pset:
                bucket = won if d["stage"] == "Won" else lost
                bucket[pk].append({
                    "label": company,
                    "sublabel_arr": "$%s ARR · %s" % (format(int(arr), ","), owner),
                    "sublabel_tcv": "$%s TCV · %s" % (format(int(tcv), ","), owner),
                    "arr": arr, "tcv": tcv,
                    "date": cl2.isoformat() if cl2 else "",
                    "hubspot_deal_id": hs_id, "hubspot_url": hs_url,
                })

    def srt(items):
        return sorted(items, key=lambda x: x.get("date") or "", reverse=True)

    def series(by_period, value_fn=lambda items: len(items)):
        out = []
        for p in periods:
            fmt = fmt_week_label if view == "weekly" else fmt_month_label
            hov = fmt_week_hover if view == "weekly" else fmt_month_hover
            out.append({"label": fmt(p), "label_hover": hov(p),
                        "value": value_fn(by_period[p]), "items": srt(by_period[p])})
        return out

    def money(items, k):
        return sum(i.get(k, 0) for i in items)

    # Avg closed-won deal size per period (total ÷ count), per metric.
    def avg_series(k):
        out = []
        for p in periods:
            its = won[p]
            fmt = fmt_week_label if view == "weekly" else fmt_month_label
            hov = fmt_week_hover if view == "weekly" else fmt_month_hover
            v = round(money(its, k) / len(its)) if its else 0
            out.append({"label": fmt(p), "label_hover": hov(p), "value": v, "items": srt(its)})
        return out

    # Cumulative all-time won value through each period-end (not windowed).
    all_won = []
    for d in deals:
        if d.get("is_open") or d.get("stage") != "Won":
            continue
        cl = closed_date(d, "Won")
        if not cl:
            continue
        arr, tcv = deal_money(d)
        all_won.append((cl, arr, tcv, d.get("company") or "—",
                        str(d.get("id") or ""), d.get("hubspot_url") or ""))
    all_won.sort(key=lambda t: t[0])

    def cumulative(idx, word):
        out = []
        for p in periods:
            pe = period_end(p, view)
            run = 0.0
            items = []
            for cl, arr, tcv, name, hid, hurl in all_won:
                if cl <= pe:
                    val = arr if idx == 1 else tcv
                    run += val
                    items.append({"label": name, "date": cl.isoformat(),
                                  "sublabel": "$%s %s" % (format(int(val), ","), word),
                                  "hubspot_deal_id": hid, "hubspot_url": hurl})
            fmt = fmt_week_label if view == "weekly" else fmt_month_label
            hov = fmt_week_hover if view == "weekly" else fmt_month_hover
            out.append({"label": fmt(p), "label_hover": hov(p), "value": round(run),
                        "items": srt(items)})
        return out

    return {
        "sales_calls_held_first":    series(held_first),
        "sales_calls_held_followup": series(held_follow),
        "sales_calls_held_all":      series(held_all),
        "deals_created":             series(created),
        "pipeline_arr":              series(pipe_arr, lambda its: round(money(its, "value"))),
        "pipeline_tcv":              series(pipe_tcv, lambda its: round(money(its, "value"))),
        "deals_closed":              series(won),
        "deals_lost":                series(lost),
        "value_closed_arr":          series(won,  lambda its: round(money(its, "arr"))),
        "value_closed_tcv":          series(won,  lambda its: round(money(its, "tcv"))),
        "value_lost_arr":            series(lost, lambda its: round(money(its, "arr"))),
        "value_lost_tcv":            series(lost, lambda its: round(money(its, "tcv"))),
        "avg_deal_size_arr":         avg_series("arr"),
        "avg_deal_size_tcv":         avg_series("tcv"),
        "cumulative_arr":            cumulative(1, "ARR"),
        "cumulative_tcv":            cumulative(2, "TCV"),
    }


# ── Performance Goals ───────────────────────────────────────────────────────
def _q2_won_arr_by_rep(payloads):
    """Closed-won ARR in Q2, attributed to the deal-owner rep (slug)."""
    out = {}
    for rep, pl in payloads.items():
        v = 0.0
        for d in (pl.get("deals") or []):
            if d.get("is_open") or d.get("stage") != "Won":
                continue
            cl = closed_date(d, "Won")
            if not cl or cl < Q2_START or cl > Q2_END:
                continue
            arr, _ = deal_money(d)
            v += arr
        out[rep] = round(v)
    return out

def _q2_sourcing_by_rep(payloads):
    """Closed-won ARR in Q2 attributed to the sourcing AE (primary_contributor).
    primary_contributor is not yet populated in the cockpit payload, so this is
    best-effort and will read 0 until that field lands."""
    out = {}
    for rep, pl in payloads.items():
        for d in (pl.get("deals") or []):
            if d.get("is_open") or d.get("stage") != "Won":
                continue
            cl = closed_date(d, "Won")
            if not cl or cl < Q2_START or cl > Q2_END:
                continue
            nm = OWNER_NAME_BY_ID.get(str(d.get("primary_contributor") or ""))
            if not nm:
                continue
            slug = nm.lower()
            arr, _ = deal_money(d)
            out[slug] = out.get(slug, 0) + round(arr)
    return out

def goal_cards(payloads):
    pct_elapsed = max(0.0, min(100.0, (TODAY - Q2_START).days /
                               max(1, (Q2_END - Q2_START).days) * 100))
    cw_actual = _q2_won_arr_by_rep(payloads)
    src_actual = _q2_sourcing_by_rep(payloads)
    return [
        {
            "title": "Q2 Closed-Won Goal",
            "subtitle": "Closed-won ARR · Apr 1 – Jun 30 · deal-owner attribution",
            "target": 580000,
            "actual": sum(cw_actual.values()),
            "by_rep_target": Q2_CW_TARGET,
            "by_rep_actual": cw_actual,
            "pct_period_elapsed": pct_elapsed,
            "deal_size_assumption": DEAL_SIZE_ASSUMPTION,
        },
        {
            "title": "Q2 Sourcing Goal",
            "subtitle": "Closed-won ARR · Apr 1 – Jun 30 · primary-contributor (sourcing AE)",
            "target": 325000,
            "actual": sum(src_actual.values()),
            "by_rep_target": Q2_SRC_TARGET,
            "by_rep_actual": src_actual,
            "pct_period_elapsed": pct_elapsed,
            "deal_size_assumption": DEAL_SIZE_ASSUMPTION,
        },
    ]


# ── Conversion (win rate by rep + by creation cohort) ───────────────────────
# Win rate = won ÷ (won + lost) over RESOLVED deals; open deals are excluded.
# Shape matches QuinnOS renderConversion() exactly so its renderer is reused
# verbatim: cohorts[{label,won,lost,open,created,win_rate,maturing}],
# by_rep[{rep,alltime{won,lost,open,win_rate},t90{win_rate}}], renewals, _meta.
MATURE_DAYS = 46   # p90 create→close cycle; a younger cohort is "still maturing".

def _pct(w, l):
    dec = w + l
    return round(w / dec * 100) if dec else None

def conversion(payloads):
    all_deals = deals_for(payloads, "all")

    # ── per-rep win rate (all-time + trailing 90 days) ──
    by_rep = []
    for rep, pl in payloads.items():
        a_w = a_l = a_o = t_w = t_l = 0
        for d in (pl.get("deals") or []):
            if d.get("is_open"):
                a_o += 1
                continue
            st = d.get("stage")
            if st not in ("Won", "Lost"):
                continue
            if st == "Won":
                a_w += 1
            else:
                a_l += 1
            cl = closed_date(d, st)
            if cl and (TODAY - cl).days <= 90:
                if st == "Won":
                    t_w += 1
                else:
                    t_l += 1
        by_rep.append({
            "rep": REPNAME.get(rep, rep),
            "alltime": {"won": a_w, "lost": a_l, "open": a_o, "win_rate": _pct(a_w, a_l)},
            "t90": {"win_rate": _pct(t_w, t_l)},
        })
    by_rep.sort(key=lambda r: (r["alltime"]["win_rate"] is None, -(r["alltime"]["win_rate"] or 0)))

    # ── creation-cohort win rate (company-wide, by created-month) ──
    cohorts = {}
    for d in all_deals:
        cdt = created_date(d)
        if not cdt:
            continue
        k = (cdt.year, cdt.month)
        c = cohorts.setdefault(k, {"w": 0, "l": 0, "o": 0, "n": 0})
        c["n"] += 1
        if d.get("is_open"):
            c["o"] += 1
        elif d.get("stage") == "Won":
            c["w"] += 1
        elif d.get("stage") == "Lost":
            c["l"] += 1
    cohort_rows = []
    for (y, m) in sorted(cohorts):
        c = cohorts[(y, m)]
        m_end = (dt.date(y + 1, 1, 1) if m == 12 else dt.date(y, m + 1, 1)) - dt.timedelta(days=1)
        cohort_rows.append({
            "label": MONTHS_ABBR[m - 1] + ("" if y == TODAY.year else " '%02d" % (y % 100)),
            "won": c["w"], "lost": c["l"], "open": c["o"], "created": c["n"],
            "win_rate": _pct(c["w"], c["l"]),
            "maturing": (TODAY - m_end).days < MATURE_DAYS,
        })

    return {
        "by_rep": by_rep,
        "cohorts": cohort_rows,
        "renewals": {"won": 0, "lost": 0, "open": 0, "win_rate": None},
        "_meta": {"mature_days": MATURE_DAYS},
    }


# ── Top-level entry point ───────────────────────────────────────────────────
def trends_data():
    payloads = load_payloads()
    weekly_p = week_range(8)
    monthly_p = month_range()
    reps = ["all"] + list(payloads.keys())
    data = {"weekly": {}, "monthly": {}}
    for rep in reps:
        data["weekly"][rep] = aggregate("weekly", weekly_p, deals_for(payloads, rep))
        data["monthly"][rep] = aggregate("monthly", monthly_p, deals_for(payloads, rep))
    data["goal_cards"] = goal_cards(payloads)
    data["conversion"] = conversion(payloads)
    # rep menu (slug + display label), Total first; only loaded reps appear.
    data["reps"] = [{"slug": "all", "label": "Total"}] + [
        {"slug": r, "label": REPNAME.get(r, r)} for r in payloads.keys()]
    data["refreshed"] = {r: (pl.get("refreshed") or "") for r, pl in payloads.items()}
    return data


if __name__ == "__main__":
    from config import load_env
    load_env()
    d = trends_data()
    print("reps:", [r["slug"] for r in d["reps"]])
    for view in ("weekly", "monthly"):
        s = d[view]["all"]["sales_calls_held_first"]
        print("%s calls_held_first values:" % view, [x["value"] for x in s], "labels:", [x["label"] for x in s])
    print("created (weekly all):", [x["value"] for x in d["weekly"]["all"]["deals_created"]])
    print("pipeline_arr (weekly all):", [x["value"] for x in d["weekly"]["all"]["pipeline_arr"]])
    print("won (weekly all):", [x["value"] for x in d["weekly"]["all"]["deals_closed"]])
    print("goal_cards:", json.dumps(d["goal_cards"], indent=1)[:900])
