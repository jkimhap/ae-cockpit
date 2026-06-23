"""dash.py — Dashboard "Trends" data layer for the SalesOS cockpit.

SOURCE OF TRUTH: QuinnOS. The Dashboard numbers used to be recomputed here from
the cockpit's per-rep payload caches, which lack `primary_contributor` (sourcing
attribution) and summed ARR differently — so every figure diverged from QuinnOS
(Arlen Q2 CW read $509K vs QuinnOS's $211K; Grant sourcing read $0; the $3M
year-end box was missing). This module now DELEGATES the entire trends data
layer to QuinnOS's build_trends.py: it builds the identical DATA tree, goal
cards, and conversion block that QuinnOS's own Trends page renders, so the
SalesOS Dashboard matches QuinnOS by construction.

QuinnOS reads from quinn-os/data/snapshots.db + deal_meta.json +
canonical_customers.json (NOT the cockpit payloads). We pin build_trends' data
resolution to those files explicitly (env DATA_DIR/DB_PATH) so nothing in the
cockpit process environment can redirect it.
"""
import os, sys
from pathlib import Path

# ── Wire up QuinnOS as an importable source-of-truth module ─────────────────
_QUINN_OS = (Path(__file__).resolve().parent.parent / "quinn-os").resolve()
_QOS_DATA = _QUINN_OS / "data"
# Pin build_trends' data resolution to QuinnOS's own files, regardless of any
# ambient DATA_DIR/DB_PATH already set in the cockpit process environment.
os.environ["DATA_DIR"] = str(_QOS_DATA)
os.environ["DB_PATH"] = str(_QOS_DATA / "snapshots.db")
if str(_QUINN_OS) not in sys.path:
    sys.path.insert(0, str(_QUINN_OS))

import build_trends as bt  # QuinnOS Trends engine — the source of truth.

# Short display labels for the rep toggle. data-rep stays the full owner_name so
# it keys straight into build_trends' DATA tree + each goal card's by_rep maps.
_SHORT = {
    "Arlen Marmel": "Arlen", "Derek Goldberg": "Derek", "Grant Amerling": "Grant",
    "Ian Lewis": "Ian", "Luke Adrianzen": "Luke", "Bo Brooks": "Bo",
}


def trends_data():
    """Reproduce QuinnOS build_trends.main()'s embedded payload exactly:
    tree[weekly|monthly][rep] + goal_cards + conversion, plus the SalesOS rep
    menu and refresh stamp the cockpit shell (ui.dashboard_html) expects."""
    weekly_periods = bt.week_range(8)
    monthly_periods = bt.month_range()
    rep_keys = ["all"] + bt.SALES_REPS

    tree = {"weekly": {}, "monthly": {}}
    for rk in rep_keys:
        rep_filter = None if rk == "all" else rk
        tree["weekly"][rk] = bt.aggregate("weekly", weekly_periods, rep_filter)
        tree["monthly"][rk] = bt.aggregate("monthly", monthly_periods, rep_filter)

    # Year-End CW ($3M ARR, company-wide), Q2 CW (per-rep deal-owner targets),
    # Q2 Sourcing (per-rep primary_contributor targets) — the same three cards,
    # same shape, QuinnOS renders. The renderer filters them by the rep toggle
    # (Total shows the $3M company box; a rep shows their own slice).
    tree["goal_cards"] = [
        bt.compute_year_end_cw_goal(),
        bt.compute_q2_cw_goal(),
        bt.compute_q2_sourcing_goal(),
    ]
    tree["conversion"] = bt.compute_conversion()

    # Rep menu: Total + the full QuinnOS roster. data-rep == owner_name so it
    # keys the DATA tree and by_rep goal maps directly. Luke (GTM Engineer,
    # sourcing-goal only) and Derek/Bo are included for QuinnOS parity.
    tree["reps"] = [{"slug": "all", "label": "Total"}] + [
        {"slug": r, "label": _SHORT.get(r, r)} for r in bt.SALES_REPS]

    tree["refreshed"] = {"snapshot": bt.get_refresh_timestamp(bt.SNAPSHOTS_DB)}
    return tree


if __name__ == "__main__":
    import json
    d = trends_data()
    print("reps:", [(r["slug"], r["label"]) for r in d["reps"]])
    print("refreshed:", d["refreshed"])
    print("--- goal cards ---")
    for c in d["goal_cards"]:
        if c.get("missing"):
            print("  %-22s MISSING" % c.get("title")); continue
        a = c.get("actual") or 0; t = c.get("target") or 0
        by = {k: int(v) for k, v in (c.get("by_rep_actual") or {}).items() if v}
        print("  %-22s $%s / $%s   by_rep_actual=%s" % (
            c["title"], format(int(a), ","), format(int(t), ","), by))
    print("--- weekly/all spot checks ---")
    wa = d["weekly"]["all"]
    print("  sales_calls_held_first:", [x["value"] for x in wa["sales_calls_held_first"]])
    print("  deals_closed:          ", [x["value"] for x in wa["deals_closed"]])
    print("  deals_lost:            ", [x["value"] for x in wa["deals_lost"]])
