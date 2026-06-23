"""ui.py — the cockpit SPA. Stage-aware deal view with talk-track prompts,
live ROI calculator, and BANT qualification scoring. Served by serve.py."""

def _tab_bar(active):
    """Server-rendered Quinn-OS top-level tab bar. `active` is one of
    'dashboard' | 'grant' | 'arlen' | 'ian'. Appears on every page."""
    tabs = [("Dashboard", "/?tab=dashboard", "dashboard"),
            ("Grant", "/?rep=grant", "grant"),
            ("Arlen", "/?rep=arlen", "arlen"),
            ("Ian", "/?tab=ian", "ian")]
    cells = "".join(
        '<a class="tab%s" href="%s">%s</a>' % (" active" if key == active else "", href, label)
        for label, href, key in tabs)
    return '<nav class="tabs-bar">%s</nav>' % cells

def html(rep, active=None):
    """The per-rep cockpit SPA. `active` decides which top-level tab is lit —
    defaults to the rep name when it's a known tab (grant/arlen), else 'grant'."""
    if active is None:
        active = rep if rep in ("grant", "arlen") else "grant"
    return (TEMPLATE.replace("__TAB_BAR__", _tab_bar(active))
                    .replace("__REP__", rep))

def _head():
    """The shared <head>…</head> block (fonts + the full <style>) lifted verbatim
    from the cockpit TEMPLATE so the Dashboard/Ian pages render in the exact same
    Quinn-OS skin without duplicating ~300 lines of CSS."""
    return TEMPLATE.split("</head>")[0] + "</head>"

def _topbar(meta=""):
    """Minimal Quinn-OS topbar for the non-SPA pages (no refresh buttons).
    Built with concatenation (not %-formatting) — _head() carries raw CSS with
    literal % signs that would break any %/format substitution."""
    return ('<header class="topbar">'
            '<div class="brand"><b>Quinn SalesOS</b></div><span class="sp"></span>'
            '<span class="refreshed">' + meta + '</span></header>')

def placeholder_html(title, message, active="ian"):
    """A minimal page sharing the full shell (head + topbar + tab bar + reskin)
    with a centered Quinn-OS message. Used for the Ian (SDR) tab."""
    return ('<!doctype html><html lang="en">' + _head() + '<body>'
            + _topbar() + _tab_bar(active)
            + '<div class="ph-wrap"><div class="ttl">' + title + '</div>'
            + '<div class="msg">' + message + '</div></div>'
            + '</body></html>')

def dashboard_html():
    """Cross-AE Dashboard — a faithful clone of the QuinnOS *Trends* page,
    sales-tuned. The DATA[view][rep][metric] series + goal cards + conversion
    are computed server-side in dash.py from the cached payloads and embedded;
    the QuinnOS renderer (buildSVG / renderCard / renderGoalCards / showPop /
    toggles, ported verbatim) draws everything client-side, driven by the
    Weekly/Monthly, ARR/TCV, and rep (Total / Grant / Arlen / Ian) toggles."""
    import json, dash
    try:
        data = dash.trends_data()
    except Exception:
        data = {"weekly": {}, "monthly": {}, "goal_cards": [], "conversion": {},
                "reps": [{"slug": "all", "label": "Total"}], "refreshed": {}}
    conv = data.pop("conversion", {})
    reps = data.get("reps") or [{"slug": "all", "label": "Total"}]
    rep_buttons = "".join(
        '<button data-rep="%s"%s>%s</button>' % (
            r["slug"], ' class="active"' if i == 0 else "", r["label"])
        for i, r in enumerate(reps))
    refreshed = " · ".join("%s %s" % (k.title(), v[:16].replace("T", " "))
                           for k, v in (data.get("refreshed") or {}).items()) or "—"
    def _embed(obj):
        # \/ keeps a stray "</script>" in any string field from closing the tag.
        return json.dumps(obj).replace("</", "<\\/")
    body = (DASHBOARD_BODY
            .replace("__REP_BUTTONS__", rep_buttons)
            .replace("__REFRESHED__", refreshed)
            .replace("__TREND_DATA__", _embed(data))
            .replace("__CONVERSION_DATA__", _embed(conv)))
    return ('<!doctype html><html lang="en">' + _head() + '<body>'
            + _topbar() + _tab_bar('dashboard') + body + '</body></html>')

DASHBOARD_BODY = r"""
<style>
/* ===== QuinnOS "Trends" chart system — ported verbatim for exact RGB + layout
   parity. These vars are scoped after the cockpit :root so the dashboard charts
   use QuinnOS's exact palette (incl. the muted brick --lost and amber --quote).
   The per-rep cockpit pages are unaffected (different served page). ===== */
:root {
  --paper: #f7f3eb; --softer: #f1ecdf; --soft: #e8e0cf; --line: #d6cdb7;
  --ink: #2b2b2b; --muted: #8a8275;
  --core: #3a6a3a; --core-bg: #d4e4cb;
  --quote: #b87b1f; --quote-bg: #f1e2c4;
  --won: #3a6a3a; --won-bg: #d4e4cb;
  --lost: #a8454c; --lost-bg: #ecd0cd;
}
/* Full-bleed wrapper — no max-width, so charts span the whole page width like
   QuinnOS (the SalesOS dashboard used to be narrow/capped). */
.trends-wrap { padding: 22px 36px 80px; }
.trends-meta {
  font-family: 'JetBrains Mono', monospace; font-size: 10px;
  text-transform: uppercase; letter-spacing: 1px; color: var(--muted);
  margin-bottom: 14px;
}
/* Controls row (rep + period + metric toggles) — top-right cluster */
.controls {
  display: flex; justify-content: flex-end; align-items: center; gap: 14px;
  margin-bottom: 22px; flex-wrap: wrap;
}
.toggle-group {
  display: inline-flex; border: 1px solid var(--ink);
  font-family: 'JetBrains Mono', monospace; font-size: 10px;
  text-transform: uppercase; letter-spacing: 1px;
}
.toggle-group button {
  border: none; background: transparent; padding: 7px 14px;
  cursor: pointer; color: var(--ink); font-family: inherit; font-size: inherit;
  text-transform: inherit; letter-spacing: inherit;
}
.toggle-group button.active { background: var(--ink); color: var(--paper); }
.toggle-group button:not(:last-child) { border-right: 1px solid var(--ink); }

.section-title { font-family: 'Fraunces', serif; font-size: 22px; font-weight: 600; letter-spacing: -0.3px; margin-bottom: 4px; margin-top: 24px; }
.section-sub { font-size: 12px; color: var(--muted); margin-bottom: 16px; }
.chart-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
  gap: 16px; margin-bottom: 32px;
}
.chart-card {
  background: var(--paper); border: 1px solid var(--ink); padding: 18px 20px;
}
/* ── Goal cards (Q2 CW, Q2 Sourcing) ───────────────────────────────────── */
.goal-card {
  background: var(--paper); border: 1px solid var(--ink); padding: 18px 24px;
  margin-bottom: 16px; max-width: 920px;
}
.goal-title { font-family: 'Fraunces', serif; font-size: 18px; font-weight: 600; margin-bottom: 2px; }
.goal-sub   { font-family: 'JetBrains Mono', monospace; font-size: 10px;
              color: var(--muted); margin-bottom: 14px; }
.goal-headline { display: flex; align-items: baseline; gap: 12px; margin-bottom: 12px; flex-wrap: wrap; }
.goal-big { font-family: 'Fraunces', serif; font-size: 36px; font-weight: 600; letter-spacing: -1px; line-height: 1; }
.goal-of  { font-family: 'Fraunces', serif; font-size: 18px; color: var(--muted); }
.goal-pace {
  margin-left: auto; font-family: 'JetBrains Mono', monospace; font-size: 11px;
  font-weight: 600; padding: 4px 10px; border-radius: 2px; letter-spacing: 1px;
  text-transform: uppercase; border: 1px solid;
}
.pace-ahead  { color: var(--core); background: var(--core-bg); border-color: var(--core); }
.pace-behind { color: #c4757b; background: #fbeeed; border-color: #e7c0bf; }
.goal-bar {
  position: relative; height: 12px; background: var(--soft);
  border: 1px solid var(--ink); margin-bottom: 14px; overflow: visible;
}
.goal-fill { height: 100%; background: var(--core); transition: width 0.4s ease; }
.goal-marker {
  position: absolute; top: -3px; bottom: -3px; width: 2px; background: var(--ink);
}
.goal-marker::after {
  content: ''; position: absolute; left: -3px; top: -3px;
  width: 8px; height: 8px; background: var(--ink); border-radius: 50%;
}
.goal-row { display: flex; gap: 32px; font-family: 'JetBrains Mono', monospace; font-size: 11px; flex-wrap: wrap; }
.goal-row > div { display: flex; flex-direction: column; gap: 4px; }
.goal-label { color: var(--muted); text-transform: uppercase; letter-spacing: 1.5px; font-size: 9px; }
.goal-val   { font-size: 18px; font-family: 'Fraunces', serif; color: var(--ink); }
.goal-sublabel { font-family: 'JetBrains Mono', monospace; font-size: 9px; color: var(--muted); margin-top: -2px; }
.chart-card .label {
  font-family: 'JetBrains Mono', monospace; font-size: 9px;
  text-transform: uppercase; letter-spacing: 2px; color: var(--muted); margin-bottom: 4px;
}
.chart-card .headline {
  font-family: 'Fraunces', serif; font-size: 20px; font-weight: 600; margin-bottom: 2px;
}
.chart-card { position: relative; }
.chart-card .sublabel {
  font-family: 'JetBrains Mono', monospace; font-size: 10px; color: var(--muted); margin-bottom: 14px;
  min-height: 1.2em;
}
.card-toggle {
  position: absolute; top: 14px; right: 18px;
  display: inline-flex; border: 1px solid var(--soft);
  font-family: 'JetBrains Mono', monospace; font-size: 8.5px;
  text-transform: uppercase; letter-spacing: 0.5px;
}
.card-toggle button {
  border: none; background: transparent; padding: 4px 8px;
  cursor: pointer; color: var(--muted); font-family: inherit; font-size: inherit;
  text-transform: inherit; letter-spacing: inherit;
}
.card-toggle button.active { background: var(--ink); color: var(--paper); }
.card-toggle button:not(:last-child) { border-right: 1px solid var(--soft); }
.chart-card .chart-svg { display: block; width: 100%; height: 150px; cursor: crosshair; }
.chart-card .footnote {
  font-family: 'JetBrains Mono', monospace; font-size: 9px; line-height: 1.4;
  color: var(--muted); margin-top: 10px; padding-top: 8px;
  border-top: 1px dotted var(--soft); font-style: italic;
}
.chart-card .trend-bar { cursor: pointer; transition: opacity 0.12s; }
.chart-card .trend-bar:hover { opacity: 1 !important; }

/* ── Conversion section ─────────────────────────────────────────────────── */
#conversion { display: grid; grid-template-columns: 1.4fr 1fr; gap: 20px; align-items: start; }
@media (max-width: 900px) { #conversion { grid-template-columns: 1fr; } }
.conv-card {
  background: var(--paper); border: 1px solid var(--soft); padding: 18px 20px;
}
.conv-card h3 {
  font-family: 'JetBrains Mono', monospace; font-size: 10px; font-weight: 600;
  text-transform: uppercase; letter-spacing: 1.5px; color: var(--muted);
  margin-bottom: 2px;
}
.conv-card .sub {
  font-size: 11px; color: var(--muted); margin-bottom: 16px; line-height: 1.4;
}
.cohort-row { display: grid; grid-template-columns: 52px 1fr 90px; align-items: center; gap: 10px; margin-bottom: 7px; }
.cohort-row .mlabel { font-family: 'JetBrains Mono', monospace; font-size: 10px; color: var(--ink); }
.cohort-track { position: relative; height: 18px; background: var(--soft); border-radius: 2px; overflow: hidden; }
.cohort-fill { height: 100%; background: var(--won, #3a6a3a); }
.cohort-fill.maturing { background: repeating-linear-gradient(45deg, var(--quote,#b8893a), var(--quote,#b8893a) 4px, rgba(0,0,0,0.08) 4px, rgba(0,0,0,0.08) 8px); }
.cohort-row .cstat { font-family: 'JetBrains Mono', monospace; font-size: 10px; color: var(--muted); text-align: right; white-space: nowrap; }
.cohort-row .cstat b { color: var(--ink); font-size: 11px; }
.cohort-row.maturing .cstat::after { content: ' 🟡'; }
table.conv-tbl { width: 100%; border-collapse: collapse; font-size: 12px; }
table.conv-tbl th {
  font-family: 'JetBrains Mono', monospace; font-size: 9px; text-transform: uppercase;
  letter-spacing: 1px; color: var(--muted); text-align: right; padding: 5px 8px;
  border-bottom: 1px solid var(--ink); white-space: nowrap;
}
table.conv-tbl th:first-child { text-align: left; }
table.conv-tbl td { padding: 7px 8px; text-align: right; font-variant-numeric: tabular-nums; border-bottom: 1px solid var(--soft); }
table.conv-tbl td:first-child { text-align: left; font-weight: 600; }
table.conv-tbl td .wr { font-weight: 700; }
table.conv-tbl tr.renewals td { color: var(--muted); font-style: italic; border-top: 1px solid var(--soft); }
.conv-foot {
  font-family: 'JetBrains Mono', monospace; font-size: 9px; line-height: 1.5;
  color: var(--muted); margin-top: 14px; font-style: italic;
}
#trend-popover {
  position: absolute; z-index: 200; display: none;
  background: var(--paper); border: 1px solid var(--ink);
  box-shadow: 0 10px 28px rgba(0,0,0,0.18);
  padding: 14px 18px; max-width: 380px; min-width: 280px;
  pointer-events: auto;
}
#trend-popover.open { display: block; }
#trend-popover .tp-week {
  font-family: 'JetBrains Mono', monospace; font-size: 9px;
  text-transform: uppercase; letter-spacing: 2px; color: var(--muted); margin-bottom: 4px;
}
#trend-popover .tp-value {
  font-family: 'Fraunces', serif; font-size: 22px; font-weight: 600; margin-bottom: 10px;
  padding-bottom: 10px; border-bottom: 1px solid var(--soft);
}
#trend-popover .tp-items { font-size: 12px; max-height: 380px; overflow-y: auto; }
#trend-popover .tp-item { padding: 4px 0; border-bottom: 1px dotted var(--soft); }
#trend-popover .tp-item:last-child { border-bottom: none; }
#trend-popover .tp-item .name { font-weight: 500; color: var(--ink); }
#trend-popover .tp-ext-link {
  color: var(--ink); text-decoration: none;
  border-bottom: 1px dotted var(--muted);
  transition: border-color 0.15s, color 0.15s;
}
#trend-popover .tp-ext-link:hover { color: var(--core); border-bottom-color: var(--core); }
#trend-popover .tp-ext-link::after { content: ' ↗'; font-size: 9px; color: var(--muted); }
#trend-popover .tp-item .sub  { font-size: 10px; font-family: 'JetBrains Mono', monospace; color: var(--muted); }
#trend-popover .tp-empty { color: var(--muted); font-style: italic; font-size: 12px; }
#trend-popover .tp-breakdown {
  margin-bottom: 12px; padding-bottom: 10px; border-bottom: 1px solid var(--soft);
}
#trend-popover .tp-section-label {
  font-family: 'JetBrains Mono', monospace; font-size: 9px;
  text-transform: uppercase; letter-spacing: 2px; color: var(--muted);
  margin-top: 4px; margin-bottom: 6px;
}
#trend-popover .tp-bd-row {
  display: flex; justify-content: space-between; align-items: baseline;
  font-size: 12px; padding: 2px 0;
}
#trend-popover .tp-bd-name { color: var(--ink); }
#trend-popover .tp-bd-count {
  font-family: 'JetBrains Mono', monospace; font-weight: 700; color: var(--core);
}
</style>

<div class="trends-wrap">
  <div class="trends-meta">SalesOS · trends data refreshed __REFRESHED__</div>

  <div class="controls">
    <div class="toggle-group" role="tablist" aria-label="Rep" id="rep-toggle">
      __REP_BUTTONS__
    </div>
    <div class="toggle-group" role="tablist" aria-label="Period">
      <button data-view="weekly" class="active">Weekly</button>
      <button data-view="monthly">Monthly</button>
    </div>
    <div class="toggle-group" role="tablist" aria-label="Metric">
      <button data-metric="arr" class="active">ARR</button>
      <button data-metric="tcv">TCV</button>
    </div>
  </div>

  <div class="section-title">Leading Indicators</div>
  <div class="section-sub" id="leading-sub">Top-of-funnel activity. Hover any bar/point for the underlying deals/calls.</div>
  <div class="chart-grid">
    <div class="chart-card" data-metric="sales_calls_held"  data-kind="count" data-type="bar"></div>
    <div class="chart-card" data-metric="deals_created"     data-kind="count" data-type="bar"></div>
    <div class="chart-card" data-metric="pipeline"          data-kind="money" data-type="line" data-toggleable="1"></div>
  </div>

  <div class="section-title">Performance Goals</div>
  <div class="section-sub">Closed-won + sourcing targets. Pace dot = Ahead/Behind vs how much of the period has elapsed.</div>
  <div id="goal-cards"></div>

  <div class="section-title">Trailing Indicators</div>
  <div class="section-sub" id="trailing-sub">What we actually closed.</div>
  <div class="chart-grid">
    <div class="chart-card" data-metric="deals_closed"    data-kind="count" data-type="bar"></div>
    <div class="chart-card" data-metric="value_closed"    data-kind="money" data-type="bar"  data-toggleable="1"></div>
    <div class="chart-card" data-metric="deals_lost"      data-kind="count" data-type="bar"></div>
    <div class="chart-card" data-metric="value_lost"      data-kind="money" data-type="bar"  data-toggleable="1"></div>
    <div class="chart-card" data-metric="avg_deal_size"   data-kind="money" data-type="bar"  data-toggleable="1"></div>
    <div class="chart-card" data-metric="cumulative"      data-kind="money" data-type="line" data-toggleable="1"></div>
  </div>

  <div class="section-title">Conversion</div>
  <div class="section-sub">Win rate = won ÷ (won + lost) over <em>resolved</em> deals — open deals excluded (their outcome is unknown). New-business only; renewals segmented out below.</div>
  <div id="conversion"></div>
</div>

<div id="trend-popover"></div>

<script id="conversion-data" type="application/json">__CONVERSION_DATA__</script>
<script id="trend-data" type="application/json">__TREND_DATA__</script>

<script>
(function() {
  const DATA = JSON.parse(document.getElementById('trend-data').textContent);
  const ICP_LABELS = {}, ICP_TOOLTIPS = {};
  const TOGGLEABLE = new Set(['pipeline', 'avg_deal_size', 'value_closed', 'value_lost', 'cumulative']);
  const localState = { meetings_booked: 'first', sales_calls_held: 'first' };

  function titleFor(metric, m) {
    const word = m.toUpperCase();
    switch (metric) {
      case 'sales_calls_held': {
        const s = localState.sales_calls_held;
        if (s === 'first')    return 'First sales calls held';
        if (s === 'followup') return 'Follow-up sales calls held';
        return 'All sales calls held';
      }
      case 'deals_created':   return 'Deals created';
      case 'pipeline':        return `Open pipeline (${word})`;
      case 'avg_deal_size':   return `Avg closed-won deal size (${word})`;
      case 'deals_closed':    return 'Closed-won deals';
      case 'value_closed':    return `Closed-won deal value (${word})`;
      case 'deals_lost':      return 'Closed-lost deals';
      case 'value_lost':      return `Closed-lost deal value (${word})`;
      case 'cumulative':      return `Cumulative ${word} (all-time)`;
    }
    return metric;
  }
  function footnoteFor(metric, m, view) {
    const word = m.toUpperCase();
    const longWord = m === 'arr'
      ? 'ARR (annualized recurring revenue — first-year value for multi-year deals)'
      : 'TCV (total contract value — full multi-year sum)';
    const periodNoun = view === 'weekly' ? 'week' : 'month';
    const periodEnd  = view === 'weekly' ? 'week-end' : 'month-end';
    const arrTcvLine = `Currently showing ${longWord}. Toggle ARR/TCV in the top right to switch.`;
    switch (metric) {
      case 'sales_calls_held': {
        const s = localState.sales_calls_held;
        const align = 'First = the first Gong-recorded sales call on a deal; follow-ups = any later call with that prospect. Internal / investor / hiring calls excluded.';
        if (s === 'first')    return `First sales calls held per deal. ${align}`;
        if (s === 'followup') return `Follow-up sales calls (every call after the first on a deal). ${align}`;
        return `All sales calls — first calls plus follow-ups. ${align}`;
      }
      case 'deals_created':
        return `Deals that entered the pipeline in each ${periodNoun} (earliest HubSpot stage-history transition for the deal).`;
      case 'pipeline':
        return `Point-in-time sum of ${word} across deals open at each ${periodEnd} (today for the current ${periodNoun}). ${arrTcvLine}`;
      case 'avg_deal_size':
        return `Average ${word} per closed-won deal that ${periodNoun} (total ${word} ÷ deal count). Zero when no closes that ${periodNoun}. ${arrTcvLine}`;
      case 'deals_closed':
        return `Count of deals that reached Closed Won, bucketed by close date into each ${periodNoun}.`;
      case 'value_closed':
        return `Sum of ${word} for Closed Won deals in each ${periodNoun}, bucketed by close date. ${arrTcvLine}`;
      case 'deals_lost':
        return `Count of deals that reached Closed Lost, bucketed by close date into each ${periodNoun}. A leading signal too — a spike flags pipeline-quality problems early.`;
      case 'value_lost':
        return `Sum of ${word} for Closed Lost deals in each ${periodNoun}, bucketed by close date — the dollar value that slipped away. ${arrTcvLine}`;
      case 'cumulative':
        return `Running total of all-time Closed Won ${word} through each ${periodEnd}. Not filtered to the visible window — earliest closed deals always contribute to the running total. ${arrTcvLine}`;
    }
    return '';
  }
  let state = { view: 'weekly', rep: 'all', metric: 'arr' };

  function dataKey(metric) {
    if (TOGGLEABLE.has(metric)) return `${metric}_${state.metric}`;
    if (metric === 'sales_calls_held')  return `sales_calls_held_${localState.sales_calls_held}`;
    return metric;
  }

  function fmtMoney(v) {
    if (v == null) return '—';
    const av = Math.abs(v);
    if (av >= 1000000) return `$${(v/1000000).toFixed(1)}M`;
    if (av >= 1000)    return `$${(v/1000).toFixed(0)}K`;
    return `$${v.toFixed(0)}`;
  }
  function fmtItemDate(iso) {
    if (!iso || typeof iso !== 'string') return '';
    const parts = iso.slice(0, 10).split('-');
    if (parts.length !== 3) return iso;
    return `${parseInt(parts[1], 10)}/${parseInt(parts[2], 10)}`;
  }
  function fmtValue(v, kind) { return kind === 'money' ? fmtMoney(v) : String(Math.round(v)); }

  function deltaSub(series, kind) {
    if (state.view !== 'monthly') return '';
    if (!series || series.length < 2) return '';
    const cur = series[series.length - 1].value || 0;
    const prev = series[series.length - 2].value || 0;
    if (prev === 0) return `prior month: ${fmtValue(prev, kind)}`;
    const ch = cur - prev;
    const pct = Math.abs((ch/prev)*100);
    const arrow = ch > 0 ? '↑' : (ch < 0 ? '↓' : '→');
    return `${arrow} ${pct.toFixed(0)}% vs prior month (${fmtValue(prev, kind)})`;
  }

  function buildSVG(series, kind, type, metric) {
    const isLost = (metric === 'deals_lost' || metric === 'value_lost');
    const curColor  = isLost ? 'var(--lost)' : 'var(--core)';
    const baseColor = isLost ? 'var(--lost)' : 'var(--ink)';
    const W = 380, H = 140, PAD_L = 8, PAD_R = 8, PAD_B = 22;
    const PAD_T = type === 'line' ? 22 : 14;
    const plotW = W - PAD_L - PAD_R, plotH = H - PAD_T - PAD_B;
    const n = series.length;
    if (!n) return `<svg class="chart-svg" viewBox="0 0 ${W} ${H}"><text x="${W/2}" y="${H/2}" text-anchor="middle" fill="#999" font-size="11">No data</text></svg>`;
    const maxV = Math.max(1, ...series.map(s => s.value || 0));
    const gap = 3;
    const bw = (plotW - gap * (n - 1)) / n;
    let svg = '';
    const points = [];
    for (let i = 0; i < n; i++) {
      const s = series[i];
      const v = s.value || 0;
      const bh = (v / maxV) * plotH;
      const x = PAD_L + i * (bw + gap);
      const y = PAD_T + plotH - bh;
      const isCurrent = (i === n - 1);
      const color = isCurrent ? curColor : baseColor;
      const opacity = isCurrent ? '1' : (isLost ? '0.55' : '0.7');
      const itemsAttr = encodeURIComponent(JSON.stringify(s.items || []));
      const hoverLabel = s.label_hover || s.label;
      if (type === 'bar') {
        svg += `<rect class="trend-bar" x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${bw.toFixed(1)}" height="${Math.max(bh,1).toFixed(1)}" fill="${color}" opacity="${opacity}" data-label="${hoverLabel}" data-value="${fmtValue(v, kind)}" data-items="${itemsAttr}"/>`;
      } else {
        points.push([x + bw/2, y, i, s, v, hoverLabel]);
      }
      const tx = x + bw / 2, ty = PAD_T + plotH + 14;
      svg += `<text x="${tx.toFixed(1)}" y="${ty}" text-anchor="middle" font-size="9" font-family="JetBrains Mono, monospace" fill="var(--muted)">${s.label}</text>`;
      const labelOffset = (type === 'line') ? 10 : 3;
      const labelY = v > 0 ? (y - labelOffset) : (PAD_T + plotH - 3);
      svg += `<text x="${tx.toFixed(1)}" y="${labelY.toFixed(1)}" text-anchor="middle" font-size="9" font-family="JetBrains Mono, monospace" fill="var(--ink)" font-weight="${isCurrent ? '700' : '500'}">${fmtValue(v, kind)}</text>`;
    }
    if (type === 'line' && points.length) {
      const pathD = points.map((p, i) => `${i===0?'M':'L'} ${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(' ');
      if (points.length >= 2) {
        const yBase = PAD_T + plotH;
        const areaD = pathD + ` L ${points[points.length-1][0].toFixed(1)} ${yBase.toFixed(1)} L ${points[0][0].toFixed(1)} ${yBase.toFixed(1)} Z`;
        svg += `<path d="${areaD}" fill="var(--core)" opacity="0.08"/>`;
      }
      svg += `<path d="${pathD}" fill="none" stroke="var(--core)" stroke-width="2" opacity="0.9"/>`;
      for (const [x, y, i, s, v, hoverLabel] of points) {
        const isCurrent = (i === n - 1);
        const r = isCurrent ? 4 : 3;
        const itemsAttr = encodeURIComponent(JSON.stringify(s.items || []));
        svg += `<circle class="trend-bar" cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${r}" fill="var(--core)" data-label="${hoverLabel}" data-value="${fmtValue(v, kind)}" data-items="${itemsAttr}"/>`;
      }
    }
    return `<svg class="chart-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">${svg}</svg>`;
  }

  function renderCard(card) {
    const metric = card.dataset.metric;
    const kind = card.dataset.kind;
    const type = card.dataset.type;
    const series = (DATA[state.view][state.rep] || {})[dataKey(metric)] || [];
    const lastV = series.length ? (series[series.length - 1].value || 0) : 0;
    const title = titleFor(metric, state.metric);
    const head = fmtValue(lastV, kind);
    let sub = deltaSub(series, kind);
    if (metric === 'cumulative') {
      sub = `running total of closed-won ${state.metric.toUpperCase()} through ${state.view === 'weekly' ? 'week-end' : 'month-end'}`;
    }
    const footnote = footnoteFor(metric, state.metric, state.view);
    let cardToggle = '';
    if (metric === 'sales_calls_held') {
      const cur = localState[metric];
      const tips = {
        first:    `Count only the first held call per deal`,
        followup: `Count only follow-up held calls (exclude the first per deal)`,
        all:      `Count every held call including first + follow-ups`,
      };
      cardToggle = `
        <div class="card-toggle" role="tablist" aria-label="Scope">
          <button data-card-toggle="${metric}" data-value="first"    class="${cur === 'first' ? 'active' : ''}"    title="${tips.first}">First</button>
          <button data-card-toggle="${metric}" data-value="followup" class="${cur === 'followup' ? 'active' : ''}" title="${tips.followup}">Follow-up</button>
          <button data-card-toggle="${metric}" data-value="all"      class="${cur === 'all' ? 'active' : ''}"      title="${tips.all}">All</button>
        </div>`;
    }
    card.innerHTML = `
      ${cardToggle}
      <div class="label">${title}</div>
      <div class="headline">${head}</div>
      <div class="sublabel">${sub}</div>
      ${buildSVG(series, kind, type, metric)}
      ${footnote ? `<div class="footnote">${footnote}</div>` : ''}
    `;
  }

  function fmtMoneyGoal(v) {
    if (v >= 1e6) return '$' + (v / 1e6).toFixed(2) + 'M';
    if (v >= 1e3) return '$' + Math.round(v / 1e3) + 'K';
    return '$' + Math.round(v).toLocaleString();
  }

  function renderGoalCards() {
    const cards = DATA.goal_cards || [];
    const root  = document.getElementById('goal-cards');
    if (!root) return;
    root.innerHTML = '';
    for (const card of cards) {
      if (card.missing) continue;
      const isAll  = state.rep === 'all';
      const actual = isAll ? (card.actual || 0) : (card.by_rep_actual[state.rep] || 0);
      const target = isAll ? card.target : (card.by_rep_target[state.rep] || 0);
      const pctGoal   = target > 0 ? (actual / target) * 100 : 0;
      const pctPeriod = card.pct_period_elapsed || 0;
      const ahead     = pctGoal >= pctPeriod;
      const gap       = Math.max(0, target - actual);
      const dealsNeeded = card.deal_size_assumption
        ? Math.ceil(gap / card.deal_size_assumption) : null;
      const repSuffix = isAll ? '' : ` — ${state.rep}`;
      const noRepTarget = !isAll && !card.by_rep_target[state.rep];

      const el = document.createElement('div');
      el.className = 'goal-card';
      if (noRepTarget) {
        el.innerHTML = `
          <div class="goal-title">${card.title}${repSuffix}</div>
          <div class="goal-sub">${state.rep} doesn't have an explicit ${card.title} target.</div>`;
      } else {
        el.innerHTML = `
          <div class="goal-title">${card.title}${repSuffix}</div>
          <div class="goal-sub">${card.subtitle}</div>
          <div class="goal-headline">
            <div class="goal-big">${fmtMoneyGoal(actual)}</div>
            <div class="goal-of">/ ${fmtMoneyGoal(target)}</div>
            <div class="goal-pace pace-${ahead ? 'ahead' : 'behind'}">
              ${ahead ? '▲ Ahead' : '▼ Behind'} pace
            </div>
          </div>
          <div class="goal-bar">
            <div class="goal-fill" style="width:${Math.min(100, pctGoal).toFixed(1)}%"></div>
            <div class="goal-marker" style="left:${Math.min(100, pctPeriod).toFixed(1)}%"
                 title="${pctPeriod.toFixed(0)}% of period elapsed"></div>
          </div>
          <div class="goal-row">
            <div><span class="goal-label">% to goal</span><span class="goal-val">${pctGoal.toFixed(1)}%</span></div>
            <div><span class="goal-label">% period elapsed</span><span class="goal-val">${pctPeriod.toFixed(1)}%</span></div>
            <div><span class="goal-label">$ to go</span><span class="goal-val">${fmtMoneyGoal(gap)}</span></div>
            ${dealsNeeded != null ? `
              <div><span class="goal-label">deals needed</span><span class="goal-val">${dealsNeeded}</span><span class="goal-sublabel">@ $${(card.deal_size_assumption/1000).toFixed(0)}K avg</span></div>
            ` : ''}
          </div>`;
      }
      root.appendChild(el);
    }
  }

  function render() {
    document.querySelectorAll('.chart-card[data-metric]').forEach(renderCard);
    renderGoalCards();
    const periodLabel = state.view === 'weekly' ? 'last 8 full weeks + this week-to-date' : 'every month since Jan 1 + month-to-date';
    const filterSuffix = state.rep === 'all' ? '' : ` Filtered to ${state.rep}.`;
    document.getElementById('leading-sub').textContent = `Top-of-funnel activity. Showing ${periodLabel}.${filterSuffix}`;
    document.getElementById('trailing-sub').textContent = `Closed-won outcomes. Showing ${periodLabel}.${filterSuffix}`;
  }

  // ── Hover popover ────────────────────────────────────────────────────────
  const pop = document.getElementById('trend-popover');
  let hideTimer = null;
  function showPop(target) {
    if (hideTimer) { clearTimeout(hideTimer); hideTimer = null; }
    const label = target.dataset.label || '';
    const value = target.dataset.value || '';
    let items = [];
    try { items = JSON.parse(decodeURIComponent(target.dataset.items || '%5B%5D')); } catch (e) {}
    let html = `<div class="tp-week">${label}</div>`;
    html += `<div class="tp-value">${value}</div>`;
    if (items.length) {
      const hasSource = items.some(it => it.source);
      if (hasSource) {
        const counts = {};
        for (const it of items) {
          const s = it.source || 'Unknown';
          counts[s] = (counts[s] || 0) + 1;
        }
        const ranked = Object.entries(counts).sort((a, b) => b[1] - a[1]);
        html += '<div class="tp-breakdown"><div class="tp-section-label">Source breakdown</div>';
        for (const [src, n] of ranked) {
          html += `<div class="tp-bd-row"><span class="tp-bd-name">${src}</span><span class="tp-bd-count">${n}</span></div>`;
        }
        html += '</div>';
        html += '<div class="tp-section-label">All items</div>';
      }
      html += '<div class="tp-items">';
      for (const it of items) {
        const datePrefix = it.date ? `${fmtItemDate(it.date)} · ` : '';
        const labelText = it.label || '';
        let labelHTML = labelText;
        const gongHref = it.gong_url || (it.gong_id ? `https://us-26175.app.gong.io/call?id=${it.gong_id}` : '');
        const hsHref = it.hubspot_url || (it.hubspot_deal_id ? `https://app.hubspot.com/contacts/deals/${it.hubspot_deal_id}` : '');
        if (gongHref) {
          labelHTML = `<a class="tp-ext-link" href="${gongHref}" target="_blank" rel="noopener">${labelText}</a>`;
        } else if (hsHref) {
          labelHTML = `<a class="tp-ext-link" href="${hsHref}" target="_blank" rel="noopener">${labelText}</a>`;
        }
        const sub = it[`sublabel_${state.metric}`] || it.sublabel || '';
        let bantHTML = '';
        const bits = [];
        if (it.bant && it.bant.score != null) {
          const s = it.bant.score;
          const tier = s >= 70 ? 'hi' : s >= 40 ? 'mid' : 'lo';
          bits.push(`<span class="tp-bant-score tier-${tier}">BANT: ${s}</span>`);
        }
        if (it.icp_fit) {
          const lbl = ICP_LABELS[it.icp_fit] || it.icp_fit;
          const def = (ICP_TOOLTIPS[it.icp_fit] || '').replace(/"/g, '&quot;');
          bits.push(`<span class="tp-icp-pill icp-${it.icp_fit}" title="${def}">${lbl}</span>`);
        }
        if (it.bant && it.bant.icp) {
          const icpClean = it.bant.icp.replace(/^T\d+\s*[—–\-·]\s*/, '');
          if (icpClean) bits.push(`<span class="tp-bant-icp">${icpClean}</span>`);
        }
        if (bits.length) {
          bantHTML = `<div class="tp-bant-line">${bits.join('')}</div>`;
        }
        html += `<div class="tp-item"><div class="name">${labelHTML}</div>`;
        if (datePrefix || sub) {
          html += `<div class="sub">${datePrefix}${sub}</div>`;
        }
        html += bantHTML;
        html += '</div>';
      }
      html += '</div>';
    } else {
      html += '<div class="tp-empty">No items.</div>';
    }
    pop.innerHTML = html;
    pop.classList.add('open');
    const r = target.getBoundingClientRect();
    let left = r.right + window.scrollX + 8;
    let top  = r.top   + window.scrollY;
    const popW = 400, popH = pop.offsetHeight || 320;
    if (left + popW > window.scrollX + window.innerWidth - 12) left = r.left + window.scrollX - popW - 8;
    if (top + popH > window.scrollY + window.innerHeight - 12) top = window.scrollY + window.innerHeight - popH - 12;
    if (top < window.scrollY + 8) top = window.scrollY + 8;
    pop.style.left = left + 'px';
    pop.style.top  = top + 'px';
  }
  function hidePopSoon() {
    if (hideTimer) clearTimeout(hideTimer);
    hideTimer = setTimeout(() => pop.classList.remove('open'), 300);
  }
  document.addEventListener('mouseover', (e) => {
    const t = e.target.closest('.trend-bar');
    if (t) showPop(t);
  });
  document.addEventListener('mouseout', (e) => {
    if (e.target.closest('.trend-bar')) hidePopSoon();
  });
  pop.addEventListener('mouseenter', () => {
    if (hideTimer) { clearTimeout(hideTimer); hideTimer = null; }
  });
  pop.addEventListener('mouseleave', hidePopSoon);

  // ── Toggle wiring ───────────────────────────────────────────────────────
  document.querySelectorAll('.toggle-group button[data-view]').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.toggle-group button[data-view]').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.view = btn.dataset.view;
      render();
    });
  });
  document.querySelectorAll('.toggle-group button[data-metric]').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.toggle-group button[data-metric]').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.metric = btn.dataset.metric;
      render();
    });
  });
  document.querySelectorAll('#rep-toggle button[data-rep]').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('#rep-toggle button[data-rep]').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.rep = btn.dataset.rep;
      render();
    });
  });
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-card-toggle]');
    if (!btn) return;
    const key = btn.dataset.cardToggle;
    const value = btn.dataset.value;
    if (!key || !value) return;
    localState[key] = value;
    render();
  });

  render();
  renderConversion();
})();

// ── Conversion section (static — cohorts + per-rep table) ───────────────────
function renderConversion() {
  const root = document.getElementById('conversion');
  if (!root) return;
  let C;
  try { C = JSON.parse(document.getElementById('conversion-data').textContent); }
  catch { return; }
  if (!C || !C.cohorts) return;

  const wr = (v) => v == null ? '—' : v + '%';

  const cohortRows = C.cohorts.map(c => {
    const pct = c.win_rate == null ? 0 : c.win_rate;
    const w = Math.round((pct / 100) * 100);
    return `<div class="cohort-row ${c.maturing ? 'maturing' : ''}" title="${c.label}: ${c.won} won / ${c.lost} lost / ${c.open} still open — of ${c.created} created${c.maturing ? '  (still maturing — not all resolved yet)' : ''}">
      <div class="mlabel">${c.label}</div>
      <div class="cohort-track"><div class="cohort-fill ${c.maturing ? 'maturing' : ''}" style="width:${w}%;"></div></div>
      <div class="cstat"><b>${wr(c.win_rate)}</b> · ${c.won}/${c.won + c.lost}</div>
    </div>`;
  }).join('');

  const repRows = C.by_rep.map(r => {
    const a = r.alltime, t = r.t90;
    return `<tr>
      <td>${r.rep.split(' ')[0]}</td>
      <td>${a.won}</td><td>${a.lost}</td><td>${a.open}</td>
      <td><span class="wr">${wr(a.win_rate)}</span></td>
      <td>${wr(t.win_rate)}</td>
    </tr>`;
  }).join('');
  const rn = C.renewals;
  const renewalRow = (rn && (rn.won + rn.lost + rn.open) > 0)
    ? `<tr class="renewals"><td>Renewals*</td><td>${rn.won}</td><td>${rn.lost}</td><td>${rn.open}</td><td>${wr(rn.win_rate)}</td><td>—</td></tr>`
    : '';

  root.innerHTML = `
    <div class="conv-card">
      <h3>Win rate by deal-creation cohort</h3>
      <div class="sub">Of the new-business deals we <em>opened</em> each month, the share of resolved ones we won. 🟡 = still maturing (younger than the ${C._meta.mature_days}-day p90 sales cycle, so some deals haven't resolved).</div>
      ${cohortRows}
    </div>
    <div class="conv-card">
      <h3>Win rate by rep</h3>
      <div class="sub">New-business only, resolved deals. Counts shown because samples are small — read the numbers, not just the percentage.</div>
      <table class="conv-tbl">
        <thead><tr><th>Rep</th><th>Won</th><th>Lost</th><th>Open</th><th>Win rate</th><th>90d</th></tr></thead>
        <tbody>${repRows}${renewalRow}</tbody>
      </table>
      <div class="conv-foot">
        *Renewals/expansions segmented out of every rate above.<br>
        Win rate excludes open deals. "90d" = trailing-90-day resolved win rate.
      </div>
    </div>`;
}
</script>
"""

TEMPLATE = r"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Quinn · SalesOS Cockpit</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600;9..144,700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
/* Quinn OS warm-paper palette (re-skin). Variable NAMES kept so the cascade still
   reaches every component; only VALUES are remapped. The 7 stage hues + their -bg
   are intentionally unchanged (stakeholder-approved). */
:root{--bg:#f7f3eb;--panel:#f7f3eb;--panel2:#f1ecdf;--ink:#2b2b2b;--muted:#8a8275;--faint:#a9a290;
--line:#d6cdb7;--line2:#e0d8c4;--accent:#2b2b2b;--accent-soft:#f1ecdf;--accent-ink:#3a6a3a;
--core:#3a6a3a;--core-bg:#d4e4cb;
--green:#3a6a3a;--green-bg:#d4e4cb;--amber:#8a6300;--amber-bg:#f4eedd;--red:#b42318;--red-bg:#fbeae9;
--shadow-sm:none;--shadow:0 1px 0 rgba(43,43,43,.04);
--radius:4px;--booked:#3554a0;--booked-bg:#eaeef8;--disc:#7c4dd1;--disc-bg:#f2ecfb;--demo:#0f8aa3;--demo-bg:#e1f1f5;--quote:#8a6300;--quote-bg:#f4eedd;
--verbal:#b5179e;--verbal-bg:#f7e4f3;--won:#127a4f;--won-bg:#eaf3ee;--lost:#b42318;--lost-bg:#fbeae9;}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--ink);font-family:'Fraunces',Georgia,serif;font-size:14px;line-height:1.5;-webkit-font-smoothing:antialiased;letter-spacing:-0.004em}
.tnum,.ktag,.kf-src,.engtag,.tbadge,.kf-l{font-family:'JetBrains Mono',monospace}
button{font-family:inherit;cursor:pointer;border:none;background:none;color:inherit}a{color:inherit}.tnum{font-variant-numeric:tabular-nums}
input,select,textarea{font-family:inherit;font-size:13px;color:var(--ink)}
::-webkit-scrollbar{width:10px;height:10px}::-webkit-scrollbar-thumb{background:#dcdad4;border-radius:8px;border:3px solid var(--bg)}
.topbar{position:sticky;top:0;z-index:30;background:rgba(250,249,247,.88);backdrop-filter:blur(8px);border-bottom:1px solid var(--line);display:flex;align-items:center;gap:12px;padding:12px 30px}
.brand{display:flex;align-items:center;gap:9px}.brand .dot{width:9px;height:9px;border-radius:50%;background:var(--green)}
.brand b{font-family:'Fraunces',Georgia,serif;font-weight:700;font-size:22px;letter-spacing:-0.02em}.brand span{font-family:'JetBrains Mono',monospace;color:var(--faint);font-size:10px;font-weight:500;text-transform:uppercase;letter-spacing:.06em}
.brand .who{margin-left:10px;padding-left:12px;border-left:1px solid var(--line2);font-size:13px;font-weight:600}
.sp{margin-left:auto}
.engine{font-family:'JetBrains Mono',monospace;font-size:10px;font-weight:600;padding:3px 9px;border-radius:6px;display:inline-flex;gap:6px;align-items:center;background:var(--panel);border:1px solid var(--line2);color:var(--faint);text-transform:uppercase;letter-spacing:.04em}
.engine .ed{width:6px;height:6px;border-radius:50%;background:currentColor}
.engine.claude{color:var(--green)}.engine.heuristic{color:var(--amber)}.engine.none{color:var(--faint)}
.cur-tag{font-size:10px;font-weight:600;color:var(--accent-ink);border:1px solid var(--accent-ink);border-radius:5px;padding:1px 6px;margin-left:7px}
.ktag{font-size:9px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:var(--faint);border:1px solid var(--line2);border-radius:4px;padding:2px 0;width:42px;text-align:center;flex-shrink:0}
.refreshed{font-family:'JetBrains Mono',monospace;font-size:10.5px;color:var(--faint)}
.rfx{font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:500;padding:7px 13px;border-radius:var(--radius);background:var(--ink);color:var(--bg);text-transform:uppercase;letter-spacing:.04em}.rfx:hover{opacity:.9}.rfx.ghost{background:var(--panel2);color:var(--ink);border:1px solid var(--line)}.rfx[disabled]{opacity:.5;cursor:default}
.main{padding:26px 30px 90px;max-width:1180px;margin:0 auto}
.h1{font-family:'Fraunces',Georgia,serif;font-size:26px;font-weight:600;letter-spacing:-0.02em}.sub{color:var(--muted);font-size:13px;margin-top:3px}
.grp{margin-top:26px}.grp-h{display:flex;align-items:baseline;gap:9px;margin-bottom:11px}
.grp-h .nm{font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}
.grp-h .ct{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--faint)}
.funnel{display:grid;grid-template-columns:repeat(5,1fr) .82fr .82fr;gap:9px}
@media(max-width:1100px){.funnel{grid-template-columns:repeat(4,1fr)}}
@media(max-width:680px){.funnel{grid-template-columns:repeat(2,1fr)}}
.fstage{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:14px 15px;cursor:pointer;transition:.13s;position:relative;overflow:hidden}
.fstage:hover{box-shadow:var(--shadow);transform:translateY(-1px)}.fstage.sel{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent)}
.fstage.synthetic{border-style:dashed;background:var(--panel2)}
.fstage .fb{position:absolute;left:0;top:0;height:4px;width:100%}
.fstage .lab{font-family:'JetBrains Mono',monospace;font-size:10px;font-weight:500;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}.fstage .n{font-family:'Fraunces',Georgia,serif;font-size:30px;font-weight:600;letter-spacing:-0.02em;margin-top:6px}
.fstage .arr{font-family:'JetBrains Mono',monospace;color:var(--faint);font-size:11px;margin-top:2px;font-weight:500}
.frollup{margin-top:9px;display:flex;flex-direction:column;gap:3px}
.frl{display:flex;justify-content:space-between;align-items:center;font-size:10.5px;font-weight:600;padding:2px 7px;border-radius:6px}
.frl .fk{color:var(--muted);text-transform:uppercase;letter-spacing:.03em}
.frl.ok{background:var(--green-bg)}.frl.ok .fv{color:var(--green)}
.frl.warn{background:var(--amber-bg)}.frl.warn .fv{color:var(--amber)}
.frl.bad{background:var(--red-bg)}.frl.bad .fv{color:var(--red)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:12px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:15px 16px;cursor:pointer;transition:.13s}
.card:hover{box-shadow:var(--shadow);transform:translateY(-1px)}
.card .top{display:flex;justify-content:space-between;align-items:flex-start;gap:8px}.card .co{font-weight:600;font-size:15px;letter-spacing:-0.015em;line-height:1.3}
.card .row{display:flex;align-items:center;gap:8px;margin-top:10px;flex-wrap:wrap}.card .amt{font-weight:600;font-size:13.5px}
.card .ctc{color:var(--muted);font-size:12px;margin-top:8px;line-height:1.45}
.card .prog{margin-top:11px}.card .alerts{margin-top:10px;display:flex;flex-direction:column;gap:4px}
.chip{display:inline-flex;align-items:center;gap:6px;font-size:11px;font-weight:600;padding:3px 9px;border-radius:6px;white-space:nowrap;background:#fff;border:1px solid var(--line2);color:var(--muted)}
.chip::before{content:"";width:6px;height:6px;border-radius:50%;background:currentColor}
.st-Discovery{color:var(--disc);background:var(--disc-bg);border-color:var(--disc-bg)}.st-Demo{color:var(--demo);background:var(--demo-bg);border-color:var(--demo-bg)}.st-Quote{color:var(--quote);background:var(--quote-bg);border-color:var(--quote-bg)}.st-Verbal{color:var(--verbal);background:var(--verbal-bg);border-color:var(--verbal-bg)}.st-Won{color:var(--won);background:var(--won-bg);border-color:var(--won-bg)}.st-Lost{color:var(--lost);background:var(--lost-bg);border-color:var(--lost-bg)}
.dcs{display:inline-flex;align-items:center;gap:6px;font-weight:700;font-size:12px;padding:3px 9px;border-radius:6px;background:#fff;border:1px solid var(--line2);color:var(--faint)}.dcs .d{width:6px;height:6px;border-radius:50%;background:currentColor}
.dcs.green{color:var(--green)}.dcs.yellow{color:var(--amber)}.dcs.red{color:var(--red)}.dcs.gray{color:var(--faint)}
.flag{display:flex;align-items:center;gap:6px;font-size:11.5px;font-weight:500;padding:4px 9px;border-radius:6px;line-height:1.35;border-left:2px solid currentColor}.flag.high{background:var(--red-bg);color:var(--red)}.flag.med{background:var(--amber-bg);color:var(--amber)}
.pbar{height:5px;background:var(--panel2);border-radius:4px;overflow:hidden}.pbar i{display:block;height:100%;background:var(--accent);border-radius:4px;transition:.2s}
.pmeta{font-size:11px;color:var(--faint);margin-bottom:4px;display:flex;justify-content:space-between}
.up-row{display:flex;gap:11px;overflow-x:auto;padding-bottom:6px}
.up{min-width:230px;background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:12px 14px;flex-shrink:0;cursor:pointer;transition:.13s}.up:hover{box-shadow:var(--shadow);transform:translateY(-1px)}
.up .when{font-family:'JetBrains Mono',monospace;font-size:10.5px;font-weight:600;color:var(--accent-ink)}.up .ti{font-weight:600;margin-top:5px;font-size:13.5px;line-height:1.3}.up .who{font-family:'JetBrains Mono',monospace;color:var(--muted);font-size:11px;margin-top:4px}
.toggle{font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:500;color:var(--muted);cursor:pointer;display:inline-flex;gap:6px;align-items:center;text-transform:uppercase;letter-spacing:.04em}.toggle:hover{color:var(--ink)}
.back{display:inline-flex;align-items:center;gap:6px;color:var(--muted);font-size:13px;font-weight:500;margin-bottom:14px;cursor:pointer}.back:hover{color:var(--ink)}
.dhead{display:flex;justify-content:space-between;align-items:flex-start;gap:20px;flex-wrap:wrap}
.dhead .co{font-size:24px;font-weight:600;letter-spacing:-0.03em}.dhead .meta{color:var(--muted);font-size:12.5px;margin-top:6px;display:flex;gap:8px;flex-wrap:wrap;align-items:center}.dhead .meta .sep{color:var(--line2)}
.ring{width:58px;height:58px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:20px;font-weight:700;flex-shrink:0}
.dlayout{display:grid;grid-template-columns:1fr 330px;gap:20px;margin-top:20px;align-items:start}
@media(max-width:1020px){.dlayout{grid-template-columns:1fr}}
.lk{color:var(--accent-ink);font-weight:600;font-size:12px;cursor:pointer}.lk:hover{text-decoration:underline}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:16px 17px}.panel+.panel{margin-top:13px}
.panel h3{font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-bottom:12px;display:flex;align-items:center;gap:8px}.panel h3 .ct{margin-left:auto;color:var(--faint);font-size:11px;font-weight:600;text-transform:none;letter-spacing:0}
/* stage accordion */
.stage{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);margin-bottom:12px;overflow:hidden}
.stage.cur{border-color:var(--line2);box-shadow:var(--shadow-sm)}
.stage-head{display:flex;align-items:center;gap:12px;padding:15px 17px;cursor:pointer}
.stage-head:hover{background:var(--panel2)}
.stage-num{width:24px;height:24px;border-radius:50%;background:var(--panel2);color:var(--muted);font-size:12px;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.stage.done .stage-num{background:var(--green);color:#fff}.stage.cur .stage-num{background:var(--accent);color:#fff}
.stage-tt{flex:1;min-width:0}.stage-tt .nm{font-weight:600;font-size:15px;letter-spacing:-0.01em}.stage-tt .bl{font-size:12px;color:var(--faint);margin-top:1px}
.stage-prog{text-align:right;min-width:120px}.stage-prog .n{font-size:12px;font-weight:600;color:var(--muted);margin-bottom:4px}
.stage-prog .pbar{width:120px}
.caret{color:var(--faint);font-size:13px;transition:.2s;width:14px;text-align:center}.stage.open .caret{transform:rotate(90deg)}
.stage-body{padding:4px 17px 17px;border-top:1px solid var(--line);display:none}.stage.open .stage-body{display:block}
.ritem{padding:12px 0;border-bottom:1px solid var(--line)}.ritem:last-child{border-bottom:none}
.ritem .rl{display:flex;align-items:center;gap:7px;font-size:13px;font-weight:500}
.ritem .gate{width:6px;height:6px;border-radius:50%;background:var(--accent);flex-shrink:0}.ritem.cap .gate{background:var(--green)}
.ritem .ai-src{font-size:10px;color:var(--accent-ink);font-weight:700}
.ritem .rh{font-size:11.5px;color:var(--faint);margin-top:2px;line-height:1.4}
.ritem .rin{margin-top:8px}
/* Talk-track prompt */
.ritem .prompt{margin-top:6px;padding:7px 10px;background:var(--accent-soft);border-radius:7px;font-size:12px;color:var(--accent-ink);line-height:1.45;font-style:italic;border-left:2px solid var(--accent-ink);cursor:pointer;position:relative}
.ritem .prompt::before{content:"SAY";font-size:9px;font-weight:700;letter-spacing:.05em;font-style:normal;position:absolute;top:-8px;left:8px;background:var(--accent-soft);padding:0 4px;color:var(--accent-ink);opacity:.7}
.ritem .prompt:hover{background:var(--demo-bg)}
.rin input,.rin select,.rin textarea{width:100%;border:1px solid var(--line2);border-radius:8px;padding:8px 10px;outline:none;background:var(--panel)}
.rin input:focus,.rin select:focus,.rin textarea:focus{border-color:var(--accent)}
.rin textarea{resize:vertical;min-height:38px;line-height:1.45}
.yn{display:inline-flex;gap:6px}.yn button{padding:7px 16px;border-radius:8px;border:1px solid var(--line2);font-size:12.5px;font-weight:600;color:var(--muted)}
.yn button.on{background:var(--ink);color:#fff;border-color:var(--ink)}.yn button.on.no{background:var(--muted)}
.ai-sug{margin-top:8px;background:var(--panel2);border-left:2px solid var(--accent-ink);border-radius:0 8px 8px 0;padding:9px 11px}
.ai-sug .hd{font-size:10px;font-weight:700;color:var(--accent-ink);text-transform:uppercase;letter-spacing:.05em}
.ai-sug .vv{font-size:13px;color:var(--ink);font-weight:600;margin-top:3px}.ai-sug .ev{font-size:11.5px;color:var(--muted);margin-top:3px;line-height:1.4}
.ai-sug .acts{display:flex;gap:7px;margin-top:8px;align-items:center}.ai-sug button{font-size:11.5px;font-weight:600;padding:4px 11px;border-radius:6px}.ai-sug .ok{background:var(--ink);color:#fff}.ai-sug .no{color:var(--muted)}.ai-sug .cite{margin-left:auto;font-size:10.5px}
.snotes{margin-top:14px}.snotes label{font-size:11px;font-weight:600;color:var(--faint);text-transform:uppercase;letter-spacing:.03em}
.snotes textarea{width:100%;border:1px solid var(--line2);border-radius:9px;padding:9px 11px;font-size:12.5px;resize:vertical;min-height:54px;margin-top:6px;outline:none}.snotes textarea:focus{border-color:var(--accent)}
/* BANT Score */
.bant{margin-top:14px;background:var(--disc-bg);border:1px solid var(--disc);border-radius:10px;padding:16px 17px}
.bant h4{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:var(--disc);margin-bottom:10px;display:flex;justify-content:space-between;align-items:center}
.bant h4 .score{font-size:20px;letter-spacing:-0.02em}
.bant-row{display:grid;grid-template-columns:70px 1fr 36px;align-items:center;gap:8px;padding:5px 0}
.bant-row .lab{font-size:11.5px;font-weight:500;color:var(--muted)}
.bant-row .track{height:7px;background:rgba(110,89,192,.15);border-radius:4px;overflow:hidden}
.bant-row .track i{display:block;height:100%;border-radius:4px;background:var(--disc);transition:.3s}
.bant-row .bv{font-size:12px;font-weight:600;color:var(--disc);text-align:right;font-variant-numeric:tabular-nums}
.bant .threshold{margin-top:10px;padding-top:10px;border-top:1px solid rgba(110,89,192,.2);font-size:11.5px;color:var(--muted);display:flex;justify-content:space-between;align-items:center}
.bant .threshold .status{font-weight:700;font-size:12px}.bant .threshold .status.pass{color:var(--green)}.bant .threshold .status.fail{color:var(--red)}
/* ROI calc */
.roi{margin-top:14px;background:linear-gradient(135deg,#f8fffe,#f3f8fc);border:1px solid var(--demo);border-radius:10px;padding:18px 17px}
.roi h4{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:var(--demo);margin-bottom:4px;display:flex;align-items:center;gap:8px}
.roi h4 .live{width:6px;height:6px;border-radius:50%;background:var(--green);animation:pulse 2s infinite}@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
.roi .rsub{font-size:11.5px;color:var(--muted);margin-bottom:14px;line-height:1.45}
.roi-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.roi-in{display:flex;flex-direction:column;gap:3px}.roi-in label{font-size:10.5px;font-weight:500;color:var(--muted)}
.roi-in input{background:#fff;border:1px solid var(--line2);border-radius:7px;padding:8px 10px;color:var(--ink);font-size:13px;outline:none;font-weight:500}.roi-in input:focus{border-color:var(--demo);box-shadow:0 0 0 2px rgba(47,111,143,.1)}
.roi-out{margin-top:16px;display:grid;grid-template-columns:repeat(3,1fr);gap:10px;border-top:1px solid rgba(47,111,143,.15);padding-top:14px}
.roi-out .o{text-align:center}.roi-out .o .v{font-size:20px;font-weight:700;letter-spacing:-0.02em;color:var(--ink)}.roi-out .o .l{font-size:10px;color:var(--muted);margin-top:2px;line-height:1.3}
.roi-tot{margin-top:14px;display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;border-top:1px solid rgba(47,111,143,.15);padding-top:14px}.roi-tot .big{font-size:26px;font-weight:700;color:var(--demo);letter-spacing:-0.02em}.roi-tot .x{font-size:12.5px;color:var(--muted)}
.roi-cp{margin-top:12px;font-size:11.5px;font-weight:600;color:#fff;background:var(--demo);padding:8px 15px;border-radius:8px}.roi-cp:hover{opacity:.9}
/* Side panels */
.bars{display:flex;flex-direction:column;gap:8px}.barrow{display:grid;grid-template-columns:92px 1fr 24px;align-items:center;gap:9px;font-size:12px}.barrow .bl{color:var(--muted)}.barrow .bv{text-align:right;font-weight:600;font-variant-numeric:tabular-nums;color:var(--muted)}
.track{height:6px;background:var(--panel2);border-radius:4px;overflow:hidden}.track i{display:block;height:100%;border-radius:4px;background:var(--accent)}
.rationale{font-size:12px;color:var(--muted);line-height:1.5;margin-top:11px;padding-top:11px;border-top:1px solid var(--line)}
.engtag{font-size:9.5px;font-weight:700;text-transform:uppercase;letter-spacing:.03em;padding:1px 6px;border-radius:10px}.engtag.claude{background:var(--green-bg);color:var(--green)}.engtag.heuristic{background:var(--amber-bg);color:var(--amber)}
.stk{display:flex;flex-wrap:wrap;gap:6px}.stk .p{background:var(--panel2);border-radius:8px;padding:5px 9px;font-size:11.5px}.stk .p b{font-weight:600}.stk .p span{color:var(--faint)}.stk .p.dm{background:var(--won-bg)}
.act{margin-top:0}.act .it{display:grid;grid-template-columns:46px 1fr;gap:11px;padding:9px 0;border-bottom:1px solid var(--line);align-items:start}.act .it:last-child{border-bottom:none}
.act .ktag{margin-top:1px}
.act .ti{font-weight:600;font-size:12.5px;line-height:1.3}.act .mt{color:var(--faint);font-size:11px;margin-top:1px}
.loss{border-color:var(--lost-bg)!important;background:var(--lost-bg)}
.pop{position:fixed;z-index:90;background:var(--panel);border:1px solid var(--line2);border-radius:var(--radius);box-shadow:var(--shadow);padding:16px 17px;width:370px;max-height:70vh;overflow:auto;display:none}.pop.open{display:block}
.pop .pt{font-weight:600;font-size:14px;line-height:1.3}.pop .pm{color:var(--faint);font-size:11.5px;margin-top:3px}.pop .lab{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);margin:12px 0 5px}.pop .who{font-size:12.5px;color:var(--muted)}.pop ul{margin:0;padding-left:16px}.pop li{font-size:12.5px;line-height:1.5;margin-bottom:4px}.pop .sent{font-size:12.5px;color:var(--muted);font-style:italic;line-height:1.5}
.scrim{position:fixed;inset:0;background:rgba(28,27,25,.28);z-index:95;opacity:0;pointer-events:none;transition:.2s}.scrim.on{opacity:1;pointer-events:auto}
.drawer{position:fixed;top:0;right:0;height:100vh;width:520px;max-width:92vw;background:var(--panel);z-index:96;box-shadow:-8px 0 30px rgba(28,27,25,.14);transform:translateX(100%);transition:.24s cubic-bezier(.4,0,.2,1);display:flex;flex-direction:column}.drawer.on{transform:none}
.drawer .dh{padding:18px 22px;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:12px}.drawer .dh b{font-size:15px;font-weight:600}
.drawer .tabs{display:flex;gap:4px;padding:12px 16px 0;flex-wrap:wrap}.drawer .tabs button{font-size:12px;font-weight:600;color:var(--muted);padding:6px 11px;border-radius:8px}.drawer .tabs button.on{background:var(--accent-soft);color:var(--accent-ink)}
.drawer .body{padding:8px 22px 30px;overflow:auto;flex:1}
.md h1,.md h2,.md h3{font-size:14px;font-weight:600;margin:15px 0 6px}.md h1{font-size:16px}.md p{font-size:13px;line-height:1.6;margin:7px 0}.md ul{margin:7px 0;padding-left:19px}.md li{font-size:13px;line-height:1.55;margin-bottom:4px}.md strong{font-weight:600}.md code{background:var(--panel2);padding:1px 5px;border-radius:5px;font-size:12px}
.kbfab{position:fixed;right:24px;bottom:24px;z-index:80;background:var(--ink);color:#fff;font-weight:600;font-size:13px;padding:11px 17px;border-radius:30px;box-shadow:var(--shadow);display:flex;gap:8px;align-items:center}.kbfab:hover{background:#000}
.empty{color:var(--faint);font-size:13px;padding:16px;text-align:center}
.toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%) translateY(20px);background:var(--ink);color:#fff;font-size:13px;font-weight:500;padding:10px 18px;border-radius:10px;box-shadow:var(--shadow);z-index:120;opacity:0;transition:.2s;pointer-events:none}.toast.on{opacity:1;transform:translateX(-50%) translateY(0)}
.loading{display:flex;align-items:center;justify-content:center;height:60vh;color:var(--faint);gap:10px}
.spin{width:15px;height:15px;border:2px solid var(--line2);border-top-color:var(--accent);border-radius:50%;animation:sp .7s linear infinite;display:inline-block}@keyframes sp{to{transform:rotate(360deg)}}
.hide{display:none!important}
/* ===== SalesOS two-pane shell (Phase 0) ===== */
.shell{display:grid;grid-template-columns:1fr;align-items:stretch;min-height:calc(100vh - 53px)}
@media(max-width:900px){.shell{grid-template-columns:1fr}.inbox{display:none}.inbox.mobile-on{display:flex}}
.inbox{display:flex;flex-direction:column;border-right:1px solid var(--line);background:var(--panel2);position:sticky;top:53px;height:calc(100vh - 53px);overflow:hidden}
.inbox-h{padding:16px 18px 12px;border-bottom:1px solid var(--line)}
.inbox-h .ti{font-family:'Fraunces',Georgia,serif;font-size:16px;font-weight:600;letter-spacing:-0.01em;display:flex;align-items:center;gap:8px}
.inbox-h .ti .cnt{margin-left:auto;font-size:11px;font-weight:600;color:var(--faint);background:#fff;border:1px solid var(--line2);border-radius:20px;padding:2px 9px}
.inbox-h .note{font-size:11px;color:var(--faint);margin-top:6px;line-height:1.4;display:flex;gap:5px;align-items:flex-start}
.inbox-h .note b{color:var(--amber);font-weight:700}
.inbox-list{overflow-y:auto;flex:1;padding:8px 10px 24px}
.ibgrp{margin-top:10px}.ibgrp:first-child{margin-top:4px}
.ibgrp-h{display:flex;align-items:center;gap:7px;padding:6px 8px 5px;font-size:10.5px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;color:var(--muted)}
.ibgrp-h .dotg{width:6px;height:6px;border-radius:50%}.ibgrp-h.overdue .dotg{background:var(--red)}.ibgrp-h.today .dotg{background:var(--amber)}.ibgrp-h.upcoming .dotg{background:var(--faint)}
.ibgrp-h .n{margin-left:auto;color:var(--faint);font-weight:600}
.task{background:var(--panel);border:1px solid var(--line);border-radius:9px;padding:10px 11px;margin:6px 0;cursor:pointer;transition:.12s}
.task:hover{box-shadow:var(--shadow-sm);border-color:var(--line2);transform:translateY(-1px)}
.task.sel{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent)}
.task .tr1{display:flex;align-items:center;gap:7px}
.tbadge{font-size:9.5px;font-weight:700;letter-spacing:.03em;text-transform:uppercase;padding:2px 7px;border-radius:5px;white-space:nowrap;flex-shrink:0}
.tbadge.prep{background:var(--demo-bg);color:var(--demo)}
.tbadge.followup{background:var(--quote-bg);color:var(--quote)}
.tbadge.gate{background:var(--disc-bg);color:var(--disc)}
.tbadge.routing{background:var(--verbal-bg);color:var(--verbal)}
.tbadge.multi{background:var(--won-bg);color:var(--won)}
.tbadge.watch{background:var(--accent-soft);color:var(--accent-ink)}
.task .co{font-weight:600;font-size:13px;letter-spacing:-0.01em;line-height:1.25;flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.task .why{font-size:11.5px;color:var(--muted);line-height:1.4;margin-top:6px}
.task .tmeta{font-size:10.5px;color:var(--faint);margin-top:6px;display:flex;gap:6px;align-items:center}
.workspace{min-width:0;overflow-x:hidden}
.workspace .main{padding:24px 36px 90px;max-width:none;margin:0}
.ws-empty{display:flex;flex-direction:column;align-items:center;justify-content:center;height:70vh;color:var(--faint);gap:10px;text-align:center;padding:30px}
.ws-empty .big{font-size:15px;font-weight:600;color:var(--muted)}
.ibtoggle{display:none}
@media(max-width:900px){.ibtoggle{display:inline-flex}}
.focus-flash{animation:flash 1.4s ease-out}@keyframes flash{0%{box-shadow:0 0 0 3px var(--accent-soft)}100%{box-shadow:none}}
/* ===== Reimagined deal workspace (task-centric) ===== */
.statusbar{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-top:16px;padding:13px 16px;background:var(--panel);border:1px solid var(--line);border-radius:var(--radius)}
.statusbar .next{font-size:13px;font-weight:600;color:var(--ink);line-height:1.4;min-width:0}
.statusbar .next .lab{font-size:9.5px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;color:var(--faint);margin-right:6px}
.grts{display:flex;gap:7px;margin-left:auto;flex-wrap:wrap}
.grt{display:inline-flex;align-items:center;gap:6px;font-size:11px;font-weight:600;padding:4px 10px;border-radius:20px;border:1px solid var(--line2);background:#fff;color:var(--muted)}
.grt .gi{font-weight:800;font-size:10px}
.grt.ok{color:var(--green);border-color:var(--green-bg);background:var(--green-bg)}
.grt.warn{color:var(--amber);border-color:var(--amber-bg);background:var(--amber-bg)}
.grt.bad{color:var(--red);border-color:var(--red-bg);background:var(--red-bg)}
.sec-h{display:flex;align-items:baseline;gap:9px;margin:24px 0 12px}
.sec-h .nm{font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:600;letter-spacing:.08em;text-transform:uppercase}.sec-h .ct{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--faint)}
.aq{display:flex;flex-direction:column;gap:12px}
.acard{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);overflow:hidden;box-shadow:var(--shadow-sm)}
.acard.urgent{border-left:3px solid var(--red)}.acard.soon{border-left:3px solid var(--amber)}
.acard-h{display:flex;align-items:center;gap:9px;padding:13px 15px;border-bottom:1px solid var(--line)}
.acard-h .ti{font-weight:600;font-size:14px;letter-spacing:-0.01em}
.acard-h .u{margin-left:auto;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;padding:2px 8px;border-radius:5px}
.acard-h .u.overdue{background:var(--red-bg);color:var(--red)}.acard-h .u.today{background:var(--amber-bg);color:var(--amber)}.acard-h .u.upcoming{background:var(--accent-soft);color:var(--accent-ink)}
.acard .why{padding:11px 15px 0;font-size:12px;color:var(--muted);line-height:1.45}
.acard .did{margin:11px 15px 0;padding:8px 11px;background:var(--accent-soft);border-radius:8px;font-size:12px;color:var(--accent-ink);line-height:1.45;display:flex;gap:9px;align-items:flex-start}
.acard .did b{font-weight:700;flex-shrink:0}
.artifact{margin:12px 15px 0}
.draftbox{width:100%;border:1px solid var(--line2);border-radius:9px;padding:11px 12px;font-size:12.5px;line-height:1.55;resize:vertical;min-height:140px;outline:none;background:var(--panel2);color:var(--ink);white-space:pre-wrap;font-family:inherit}
.draftbox:focus{border-color:var(--accent);background:#fff}
.f-meta{font-size:11px;color:var(--faint);margin-bottom:7px;display:flex;gap:7px;flex-wrap:wrap}
.f-meta .pill{background:var(--panel2);border-radius:6px;padding:2px 8px;color:var(--muted);font-weight:500}
.prepsheet{font-size:12.5px;line-height:1.55}
.prepsheet .blk{margin-top:11px}.prepsheet .blk:first-child{margin-top:0}
.prepsheet .bh{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);margin-bottom:5px}
.prepsheet ul{margin:0;padding-left:17px}.prepsheet li{margin-bottom:4px}.qlist li{color:var(--ink)}
.gateprop{border:1px solid var(--line2);border-radius:9px;overflow:hidden}
.gaterow{padding:10px 12px;border-bottom:1px solid var(--line)}.gaterow:last-child{border-bottom:none}
.gaterow .gl{font-size:12.5px;font-weight:600;display:flex;align-items:center;gap:6px}.gaterow .gl .g{width:6px;height:6px;border-radius:50%;background:var(--disc);flex-shrink:0}
.gaterow .gv{font-size:12.5px;color:var(--ink);margin-top:3px}
.gaterow .gev{font-size:11.5px;color:var(--muted);font-style:italic;margin-top:4px;line-height:1.4;border-left:2px solid var(--line2);padding-left:8px}
.gaterow .gacts{display:flex;gap:7px;margin-top:8px}
.aq-acts{display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:13px 15px;border-top:1px solid var(--line);margin-top:12px;background:var(--panel2)}
.aq-acts .spacer{margin-left:auto}
.btn{font-size:12px;font-weight:600;padding:7px 13px;border-radius:8px;border:1px solid var(--line2);background:#fff;color:var(--ink)}.btn:hover{border-color:var(--accent)}
.btn.primary{background:var(--ink);color:#fff;border-color:var(--ink)}.btn.primary:hover{opacity:.9}
.btn.ai{background:var(--accent-soft);color:var(--accent-ink);border-color:var(--accent-soft)}
.btn.ghost{background:transparent;border-color:transparent;color:var(--muted)}.btn.ghost:hover{color:var(--ink);border-color:var(--line2)}
.btn.sm{font-size:11px;padding:4px 10px}
.resolved{margin-top:10px}
.rsv-row{display:flex;align-items:center;gap:9px;padding:8px 12px;border:1px solid var(--line);border-radius:8px;margin-bottom:6px;font-size:12px;color:var(--muted);background:var(--panel2)}
.rsv-row .tick{color:var(--green);font-weight:700}.rsv-row .undo{margin-left:auto}
.allclear{padding:24px;text-align:center;color:var(--muted);background:var(--panel);border:1px dashed var(--line2);border-radius:var(--radius);font-size:12.5px;line-height:1.5}
.allclear .big{font-size:14px;font-weight:600;color:var(--green);margin-bottom:4px}
.facts-wrap{margin-top:22px}
.facts-toggle{display:inline-flex;align-items:center;gap:7px;font-size:12.5px;font-weight:600;color:var(--muted);cursor:pointer;padding:8px 0}.facts-toggle:hover{color:var(--ink)}.facts-toggle .cv{font-size:11px}
.facts-grid{display:grid;grid-template-columns:1fr 330px;gap:18px;align-items:start;margin-top:6px}
@media(max-width:1020px){.facts-grid{grid-template-columns:1fr}}
.factbox{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:15px 16px;margin-bottom:13px}
.factbox h3{font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:.03em;color:var(--muted);margin-bottom:11px}
.kv{display:grid;grid-template-columns:auto 1fr;gap:7px 14px;font-size:12.5px}.kv .k{color:var(--muted)}.kv .v{font-weight:500;text-align:right}
/* Ask the agent dock */
.askdock{margin-top:26px;background:var(--panel);border:1px solid var(--line2);border-radius:14px;overflow:hidden;box-shadow:var(--shadow-sm)}
.askdock-h{display:flex;align-items:center;gap:8px;padding:12px 15px;border-bottom:1px solid var(--line)}
.askdock-h .ic{width:8px;height:8px;border-radius:50%;background:var(--accent-ink)}
.askdock-h b{font-size:13px;font-weight:600}.askdock-h span{font-size:11px;color:var(--faint)}
.asklog{padding:6px 15px;max-height:300px;overflow:auto}
.askmsg{margin:9px 0;font-size:12.5px;line-height:1.5}
.askmsg.you{text-align:right}.askmsg.you .b{background:var(--ink);color:#fff;border-radius:12px 12px 4px 12px}
.askmsg .b{display:inline-block;padding:8px 12px;border-radius:12px 12px 12px 4px;background:var(--panel2);max-width:88%;text-align:left}
.askmsg.agent .b{border:1px solid var(--line)}
.askchips{display:flex;gap:7px;flex-wrap:wrap;padding:10px 15px 4px}
.askchip{font-size:11.5px;font-weight:600;color:var(--accent-ink);background:var(--accent-soft);border-radius:18px;padding:5px 11px;cursor:pointer}.askchip:hover{opacity:.85}
.askin{display:flex;gap:8px;padding:12px 15px;border-top:1px solid var(--line)}
.askin input{flex:1;border:1px solid var(--line2);border-radius:10px;padding:9px 12px;outline:none;font-size:13px}.askin input:focus{border-color:var(--accent)}
.askin button{background:var(--ink);color:#fff;font-weight:600;font-size:12.5px;padding:9px 16px;border-radius:10px}
/* Key facts — the live deal record */
.keyfacts{margin-top:14px;background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:13px 16px}
.kf-h{display:flex;align-items:baseline;gap:10px;margin-bottom:9px}
.kf-h b{font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:.03em;color:var(--muted)}
.kf-note{font-size:11px;color:var(--faint)}
.kf-grid{display:grid;grid-template-columns:1fr 1fr;gap:2px 26px}
@media(max-width:760px){.kf-grid{grid-template-columns:1fr}}
.kf-row{display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid var(--line);min-height:34px}
.kf-l{width:104px;flex:none;color:var(--muted);font-size:12px}
.kf-v{flex:1;font-size:12.5px;font-weight:500;display:flex;align-items:center;gap:7px;flex-wrap:wrap}
.kf-empty{color:var(--faint);font-weight:400;font-style:italic}
.kf-src{font-size:9.5px;font-weight:700;text-transform:uppercase;letter-spacing:.03em;padding:1px 6px;border-radius:9px}
.kf-src.you{background:var(--accent-soft);color:var(--accent-ink)}
.kf-src.gong{background:var(--green-bg);color:var(--green)}
.kf-src.hs{background:var(--panel2);color:var(--faint)}
.kf-edit{flex:none;width:24px;height:24px;border-radius:7px;color:var(--faint);font-size:12px;opacity:.5}.kf-edit:hover{opacity:1;background:var(--panel2)}
.kf-in{flex:1;min-width:120px;border:1px solid var(--accent);border-radius:8px;padding:5px 9px;font-size:12.5px;outline:none}
.kf-desc{margin-top:10px;padding-top:10px;border-top:1px solid var(--line);font-size:12px;color:var(--muted);line-height:1.5}
/* ===== Quinn OS top-level tab bar (server-rendered) ===== */
.tabs-bar{display:flex;gap:0;border-bottom:1px solid var(--ink);padding:0 30px;background:var(--bg);position:sticky;top:53px;z-index:25}
.tab{font-family:'JetBrains Mono',monospace;font-size:11px;text-transform:uppercase;letter-spacing:1.5px;padding:10px 18px;border:1px solid var(--ink);border-bottom:none;background:var(--panel2);text-decoration:none;color:var(--ink);margin-right:-1px;cursor:pointer}
.tab.active{background:var(--bg);position:relative;top:1px}
/* ===== Dashboard / placeholder pages ===== */
.dashwrap{padding:26px 36px 90px;max-width:none;margin:0}
.masthead{border-bottom:1px solid var(--ink);padding-bottom:16px;margin-bottom:22px;display:flex;align-items:flex-end;justify-content:space-between;gap:20px;flex-wrap:wrap}
.masthead .ttl{font-family:'Fraunces',Georgia,serif;font-size:30px;font-weight:600;letter-spacing:-0.02em;line-height:1.1}
.masthead .meta{font-family:'JetBrains Mono',monospace;font-size:10.5px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-top:6px}
.toggle-group{display:inline-flex;border:1px solid var(--ink);font-family:'JetBrains Mono',monospace;font-size:10px;text-transform:uppercase;letter-spacing:1px}
.toggle-group button{border:none;background:transparent;padding:7px 14px;cursor:pointer;color:var(--ink);font:inherit;text-transform:inherit;letter-spacing:inherit}
.toggle-group button.active{background:var(--ink);color:var(--bg)}
.toggle-group button:not(:last-child){border-right:1px solid var(--ink)}
.kpirow{display:grid;grid-template-columns:repeat(5,1fr);gap:0;border:1px solid var(--line);margin-bottom:8px}
@media(max-width:980px){.kpirow{grid-template-columns:repeat(3,1fr)}}
@media(max-width:560px){.kpirow{grid-template-columns:repeat(2,1fr)}}
.kpi{padding:18px 20px;border-right:1px solid var(--line)}.kpi:last-child{border-right:none}
@media(max-width:760px){.kpi:nth-child(2){border-right:none}.kpi:nth-child(1),.kpi:nth-child(2){border-bottom:1px solid var(--line)}}
.kpi .v{font-family:'Fraunces',Georgia,serif;font-size:32px;font-weight:600;letter-spacing:-0.02em;line-height:1;color:var(--core)}
.kpi .l{font-family:'JetBrains Mono',monospace;font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-top:8px}
.kpi .sub2{font-family:'JetBrains Mono',monospace;font-size:10.5px;color:var(--faint);margin-top:3px}
.section-title{font-family:'Fraunces',Georgia,serif;font-size:21px;font-weight:600;letter-spacing:-0.01em;margin:30px 0 4px}
.section-sub{font-family:'JetBrains Mono',monospace;font-size:10px;text-transform:uppercase;letter-spacing:.07em;color:var(--faint);margin-bottom:13px}
.chartgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:16px}
@media(max-width:760px){.chartgrid{grid-template-columns:1fr}}
.chartbox .headline{font-family:'Fraunces',Georgia,serif;font-size:24px;font-weight:600;color:var(--ink);letter-spacing:-0.02em;margin-bottom:2px}
.chartbox .delta{font-family:'JetBrains Mono',monospace;font-size:10px;margin-bottom:10px}
.chartbox .delta.up{color:var(--green)}.chartbox .delta.down{color:var(--red)}.chartbox .delta.flat{color:var(--faint)}
.wrow{display:grid;grid-template-columns:64px 1fr 92px;align-items:center;gap:11px;margin-bottom:9px}
.wrow .wl{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--ink);text-transform:capitalize}
.wtrack{position:relative;height:18px;background:var(--panel2);border:1px solid var(--line2);overflow:hidden}
.wfill{height:100%;background:var(--core)}
.wrow .wstat{font-family:'JetBrains Mono',monospace;font-size:10px;color:var(--muted);text-align:right;white-space:nowrap}
.wrow .wstat b{color:var(--ink);font-size:11px}
.chartbox{border:1px solid var(--line);padding:16px 18px;background:var(--panel)}
.chartbox h3{font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-bottom:14px}
.chartbox svg{width:100%;height:auto;display:block}
.chartbox .axlab,.chartbox .vlab{font-family:'JetBrains Mono',monospace}
.dash-empty{display:flex;flex-direction:column;align-items:center;justify-content:center;height:55vh;gap:12px;text-align:center;color:var(--muted)}
.dash-empty .big{font-family:'Fraunces',Georgia,serif;font-size:22px;font-weight:600;color:var(--ink)}
.dash-empty .sm{font-family:'JetBrains Mono',monospace;font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--faint)}
.ph-wrap{display:flex;flex-direction:column;align-items:center;justify-content:center;height:calc(100vh - 200px);gap:14px;text-align:center;padding:30px}
.ph-wrap .ttl{font-family:'Fraunces',Georgia,serif;font-size:34px;font-weight:600;letter-spacing:-0.02em;color:var(--ink)}
.ph-wrap .msg{font-family:'JetBrains Mono',monospace;font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}
</style></head>
<body>
<header class="topbar">
  <div class="brand"><b>Quinn SalesOS</b><span class="who" id="repName">…</span></div>
  <span class="sp"></span>
  <span class="engine none" id="engine">—</span><span class="refreshed" id="refreshed"></span>
  <button class="rfx" id="rbtn" onclick="refresh(false)">↻ Refresh</button>
  <button class="rfx ghost" id="rfull" onclick="refresh(true)" title="Re-pull Gong + regenerate AI">⟳ Full sync</button>
</header>
__TAB_BAR__
<div class="shell">
  <div class="workspace"><main class="main" id="view"><div class="loading"><span class="spin"></span> Loading live HubSpot data…</div></main></div>
</div>
<div class="pop" id="pop"></div>
<button class="kbfab" onclick="openKB()">Playbook</button>
<div class="scrim" id="scrim" onclick="closeKB()"></div>
<aside class="drawer" id="drawer"><div class="dh"><b>Playbook & KB</b><button class="lk" style="margin-left:auto" onclick="closeKB()">Close</button></div>
  <div class="tabs" id="kbTabs"></div><div class="body md" id="kbBody"></div></aside>
<div class="toast" id="toast"></div>
<script>
const REP="__REP__"; let D=null;
const $=s=>document.querySelector(s);
const esc=s=>(s==null?'':String(s)).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const money=v=>v==null||v===''||isNaN(v)?'—':'$'+Math.round(+v).toLocaleString();
const dealById=id=>D.deals.find(d=>d.id===id);
const fmtDate=s=>{if(!s)return '';const d=new Date(s);return isNaN(d)?String(s).slice(0,10):d.toLocaleDateString('en-US',{month:'short',day:'numeric'});};
const fmtDT=s=>{const d=new Date(s);return isNaN(d)?s:d.toLocaleDateString('en-US',{weekday:'short',month:'short',day:'numeric'})+' · '+d.toLocaleTimeString('en-US',{hour:'numeric',minute:'2-digit'});};
const ago=s=>{if(!s)return '';const d=new Date(s.replace(' UTC','Z').replace(' ','T'));if(isNaN(d))return s;const h=(Date.now()-d)/36e5;return h<1?Math.max(1,Math.round(h*60))+'m ago':h<24?Math.round(h)+'h ago':Math.round(h/24)+'d ago';};
const openDeals=()=>D.deals.filter(d=>d.is_open);
const LS={k:id=>'cockpit:'+REP+':'+id,get(id){try{return JSON.parse(localStorage.getItem(this.k(id)))||{}}catch(e){return {}}},set(id,v){localStorage.setItem(this.k(id),JSON.stringify(v))}};
function dst(id){const s=LS.get(id);s.cap=s.cap||{};s.src=s.src||{};s.dis=s.dis||{};s.notes=s.notes||{};s.roi=s.roi||{};return s;}
function save(id,s){LS.set(id,s);}
const rubricById={};
async function fetchJSON(u,o){const url=new URL(u,location.origin);const r=await fetch(url.href,o);return r.json();}
async function load(){try{D=await fetchJSON('/api/data?rep='+REP);D.rubric.forEach(s=>s.items.forEach(it=>rubricById[it.id]=it));hydrate();route();}catch(e){$('#view').innerHTML='<div class="empty">Failed to load: '+esc(e.message)+'</div>';}}
let refreshing=false;
async function refresh(full,silent){if(refreshing)return;refreshing=true;$('#rbtn').disabled=true;$('#rfull').disabled=true;const o=$('#rbtn').textContent;$('#rbtn').textContent=full?'Full syncing…':'Refreshing…';
  try{const j=await fetchJSON('/api/refresh?rep='+REP+'&full='+(full?1:0),{method:'POST'});if(j.ok){D=j.payload;D.rubric.forEach(s=>s.items.forEach(it=>rubricById[it.id]=it));hydrate();route();if(!silent)toast((full?'Full sync':'Refreshed')+' · '+j.took+'s');}else toast('Refresh failed: '+(j.error||''));}
  catch(e){toast('Refresh failed');}finally{refreshing=false;$('#rbtn').disabled=false;$('#rfull').disabled=false;$('#rbtn').textContent=o;}}
function hydrate(){$('#repName').textContent=D.rep;$('#refreshed').textContent='HubSpot '+ago(D.refreshed);
  const e=$('#engine');e.className='engine '+(D.ai_engine||'none');e.innerHTML='<span class="ed"></span>'+(D.ai_engine==='claude'?'Claude':D.ai_engine==='heuristic'?'Heuristic':'No AI');
  e.title=D.ai_engine==='heuristic'?'Anthropic key out of credits — add credits then Full sync to upgrade to Claude':'';
  }
function toast(t){const el=$('#toast');el.textContent=t;el.classList.add('on');setTimeout(()=>el.classList.remove('on'),2600);}
window.addEventListener('hashchange',route);
function route(){if(!D)return;const h=location.hash||'#/';if(h.startsWith('#/deal/'))renderDeal(h.slice(7));else renderMain();window.scrollTo(0,0);}

/* ---------- LEFT PANE: SalesOS Task Inbox (Phase 0, heuristic) ----------
   Tasks are derived server-side in tasks.py from the current deal snapshot
   (payload.inbox). They are NOT event-driven yet — that's Phase 2. Clicking a
   task selects its deal in the right pane and focuses the relevant section. */
const TBADGE={'Call Prep':['prep','Prep'],'Draft Follow-up':['followup','Follow-up'],
  'Gate-Capture':['gate','Gate'],'Routing-Check':['routing','Routing'],
  'Multi-thread':['multi','Multi-thread'],'Watch':['watch','Watch']};
const BUCKET_LABEL={overdue:'Overdue',today:'Today',upcoming:'Upcoming'};
let selTask=null;          // currently selected task id
let pendingFocus=null;     // {deal_id, section, stage} to focus after renderDeal
function inboxData(){return (D&&D.inbox)||{buckets:{overdue:[],today:[],upcoming:[]},total:0};}
function renderInbox(){
  const ib=inboxData();const list=$('#inboxList');if(!list)return;
  $('#inboxCount').textContent=ib.total||0;
  let html='';
  ['overdue','today','upcoming'].forEach(b=>{
    const ts=(ib.buckets&&ib.buckets[b])||[];if(!ts.length)return;
    html+=`<div class="ibgrp"><div class="ibgrp-h ${b}"><span class="dotg"></span>${BUCKET_LABEL[b]}<span class="n">${ts.length}</span></div>${ts.map(taskRow).join('')}</div>`;
  });
  list.innerHTML=html||'<div class="empty">No open tasks — inbox clear.</div>';
}
function taskRow(t){
  const tb=TBADGE[t.type]||['watch',t.type];
  return `<div class="task ${selTask===t.id?'sel':''}" onclick="selectTask('${esc(t.id)}')">
    <div class="tr1"><span class="tbadge ${tb[0]}">${esc(tb[1])}</span><span class="co" title="${esc(t.company)}">${esc(t.company)}</span></div>
    <div class="why">${esc(t.why)}</div>
    <div class="tmeta"><span>${esc(t.title)}</span><span>·</span><span>${esc(t.owner)}</span></div></div>`;
}
function findTask(id){const ib=inboxData();for(const b of ['overdue','today','upcoming']){const t=((ib.buckets||{})[b]||[]).find(x=>x.id===id);if(t)return t;}return null;}
function selectTask(id){
  const t=findTask(id);if(!t)return;selTask=id;
  pendingFocus={deal_id:t.deal_id,task_id:t.id};
  renderInbox();
  if(location.hash==='#/deal/'+t.deal_id)route();      // already there → re-render & focus
  else location.hash='#/deal/'+t.deal_id;               // else navigate (route() fires)
}
/* After a deal renders, scroll the clicked task's action card into view and flash it. */
function applyFocus(d){
  if(!pendingFocus||pendingFocus.deal_id!==d.id)return;
  const tid=pendingFocus.task_id;pendingFocus=null;
  setTimeout(()=>{const el=tid&&document.getElementById('acard-'+tid);if(el){el.scrollIntoView({behavior:'smooth',block:'center'});el.classList.add('focus-flash');setTimeout(()=>el.classList.remove('focus-flash'),1400);}},80);
}

/* ---------- capture helpers ---------- */
function capVal(id,iid){const s=dst(id);return s.cap[iid]!=null?s.cap[iid]:'';}
function isCap(id,iid){return capVal(id,iid)!=='';}
function stageProg(d,stage){let cap=0,tot=stage.items.length,gates=0,gmet=0;stage.items.forEach(it=>{if(isCap(d.id,it.id))cap++;if(it.gate){gates++;if(isCap(d.id,it.id))gmet++;}});return {cap,tot,gates,gmet};}
function isWon(d){return d.stage_id==='1090549670';}
function dcsBadge(d){if(isWon(d))return `<span class="dcs green"><span class="d"></span>Won</span>`;const s=d.dcs.score;return `<span class="dcs ${d.dcs.color}"><span class="d"></span>${s==null?'—':s}</span>`;}
function stageChip(s){return `<span class="chip st-${s}">${s}</span>`;}
function alertFlags(d){return (d.alerts||[]).slice(0,2).map(a=>`<div class="flag ${a.sev}">${esc(a.text)}</div>`).join('');}

/* ---------- main page ---------- */
const OPEN_ORDER=['Discovery','Demo','Quote','Verbal'];
function curStageObj(d){return D.rubric.find(s=>s.key===d.rubric_stage)||D.rubric[1];}
function dealCard(d){
  const cs=curStageObj(d);const pr=stageProg(d,cs);
  const pc=d.primary_contact.name?`${esc(d.primary_contact.name)}${d.primary_contact.title?' · '+esc(d.primary_contact.title):''}`:'';
  return `<div class="card" onclick="location.hash='#/deal/${d.id}'">
    <div class="top"><div class="co">${esc(d.company)}</div>${dcsBadge(d)}</div>
    <div class="row">${stageChip(d.stage)}<span class="amt tnum">${money(d.arr||d.amount)}</span>${d.dcs.days_in_stage!=null?`<span style="color:var(--faint);font-size:11.5px">${d.dcs.days_in_stage}d</span>`:''}</div>
    ${pc?`<div class="ctc">${pc}</div>`:''}
    <div class="prog"><div class="pmeta"><span>${esc(cs.name)} rubric</span><span>${pr.cap}/${pr.tot}${pr.gates?` · gates ${pr.gmet}/${pr.gates}`:''}</span></div><div class="pbar"><i style="width:${Math.round(pr.cap/pr.tot*100)}%"></i></div></div>
    ${alertFlags(d)?`<div class="alerts">${alertFlags(d)}</div>`:''}</div>`;
}
let filterStage=null;
const stColor=l=>({Won:'won',Lost:'lost',Booked:'booked',Discovery:'disc',Demo:'demo',Quote:'quote',Verbal:'verbal'}[l]||'demo');
function dealStageColor(d){if(!d)return 'demo';if(d.is_open&&d.rubric_stage==='disc'&&((d.dcs&&d.dcs.n_calls)||0)===0)return 'booked';return stColor(d.stage);}
/* Funnel model: prepend a synthetic "Discovery Booked" (pre-qualified) tile — open deals
   sitting in the Discovery stage that haven't had a Discovery call yet (no Gong call matched).
   That's the pre-qualified intake where the pre-Discovery prep sheet drops. Those deals are
   pulled OUT of Discovery Complete so counts don't double. Each tile rolls up where the system
   is on entry-gates + required artifacts across the deals in that stage. */
function funnelModel(){
  const booked=D.deals.filter(d=>d.is_open&&d.rubric_stage==='disc'&&((d.dcs&&d.dcs.n_calls)||0)===0);
  const bset=new Set(booked.map(d=>d.id));
  const sum=ds=>ds.reduce((s,d)=>s+(d.arr||d.amount||0),0);
  const out=[{stage_id:'__booked',label:'Booked',full:'Discovery Booked',synthetic:true,deals:booked,n:booked.length,arr:sum(booked)}];
  D.funnel.forEach(f=>{const ds=D.deals.filter(d=>d.stage_id===f.stage_id&&!bset.has(d.id));out.push(Object.assign({},f,{deals:ds,n:ds.length,arr:sum(ds)}));});
  return out;
}
function gateProg(d){const cs=curStageObj(d);let g=0,a=0;(cs.items||[]).forEach(it=>{if(it.gate){g++;if(isCap(d.id,it.id)||((d.ai_fields||{})[it.id]&&d.ai_fields[it.id].value))a++;}});return {g,a};}
function dealGatesDone(d){const p=gateProg(d);return p.g>0&&p.a>=p.g;}
function dealArtifactsOnTrack(d){return !dealTasks(d.id).some(t=>!tStatus(d.id,t.id)&&t.urgency==='overdue');}
function fRollup(f){
  const CLOSED=['1090549670','1090549671'];
  if(CLOSED.includes(f.stage_id)||!f.deals.length)return '';
  const n=f.deals.length,parts=[];
  if(f.stage_id!=='__booked'){const gd=f.deals.filter(dealGatesDone).length;parts.push(fRl('Gates',gd,n));}
  const ad=f.deals.filter(dealArtifactsOnTrack).length;parts.push(fRl('Artifacts',ad,n));
  return `<div class="frollup">${parts.join('')}</div>`;
}
function fRl(label,x,n){const st=x>=n?'ok':(x>0?'warn':'bad');return `<div class="frl ${st}"><span class="fk">${label}</span><span class="fv">${x}/${n}</span></div>`;}
function funnelTiles(){return funnelModel().map(f=>`<div class="fstage ${f.synthetic?'synthetic':''} ${filterStage===f.stage_id?'sel':''}" onclick="toggleFunnel('${f.stage_id}')"><div class="fb" style="background:var(--${stColor(f.label)})"></div><div class="lab">${esc(f.full)}</div><div class="n tnum">${f.n}</div><div class="arr tnum">${money(f.arr)}</div></div>`).join('');}
function toggleFunnel(sid){filterStage=(filterStage===sid?null:sid);renderMain();}
function renderMain(){
  const v=$('#view');const ods=openDeals();const closed=D.deals.filter(d=>!d.is_open);
  const up=D.upcoming.length?D.upcoming.map(u=>{const dd=u.deal_id?dealById(u.deal_id):null;const col=dealStageColor(dd);return `<div class="up" style="border-left:4px solid var(--${col});background:var(--${col}-bg)" onclick="${u.deal_id?`location.hash='#/deal/${u.deal_id}'`:''}"><div class="when">${esc(fmtDT(u.start))}</div><div class="ti">${esc(u.company||u.title||'Meeting')}</div><div class="who">${dd?esc(dd.stage):'New'}</div></div>`;}).join(''):'';
  let body='';
  if(filterStage){
    const f=funnelModel().find(x=>x.stage_id===filterStage)||{full:'',deals:[]};const ds=f.deals;
    const note=f.synthetic?'<div class="empty" style="text-align:left;border:none;padding:4px 0 12px;color:var(--faint)">Pre-qualified — Discovery booked, call not yet held. The agent drops the pre-Discovery prep sheet here.</div>':'';
    body=`<div class="grp"><div class="grp-h"><span class="nm">${esc(f.full)}</span><span class="ct">${ds.length} · ${money(ds.reduce((s,d)=>s+(d.arr||d.amount||0),0))}</span></div>${note}<div class="grid">${ds.map(dealCard).join('')||'<div class="empty">No deals in this stage.</div>'}</div></div>`;
  }else{
    // No stage selected (or just deselected): show NO deal cards. The funnel is the
    // navigator — click a stage box to reveal its deals. (Won/Lost are funnel tiles too.)
    body=`<div class="empty" style="margin-top:18px">Click a stage above to see its deals.</div>`;
  }
  v.innerHTML=`<div class="h1">Pipeline</div><div class="sub">${ods.length} open deals · ${money(ods.reduce((s,d)=>s+(d.arr||d.amount||0),0))} open pipeline</div>
    ${up?`<div class="grp"><div class="grp-h"><span class="nm">Upcoming Meetings</span></div><div class="up-row">${up}</div></div>`:''}
    <div class="grp"><div class="grp-h"><span class="nm">Funnel</span><span class="ct">${filterStage?'<a class="lk" onclick="toggleFunnel(null)">Clear filter</a>':'Click a stage to filter'}</span></div><div class="funnel">${funnelTiles()}</div></div>
    ${body}`;
}

/* ---------- deal view ---------- */
let openStages={};
function renderDeal(id){
  const d=dealById(id);const v=$('#view');if(!d){v.innerHTML='<div class="empty">Deal not found.</div>';return;}
  const all=dealTasks(id);
  const open=all.filter(t=>!tStatus(id,t.id));
  const resolved=all.filter(t=>tStatus(id,t.id));
  v.innerHTML=`<a class="back" onclick="location.hash='#/'">← All deals</a>
   <div class="dhead"><div><div class="co">${esc(d.company)}</div>
     <div class="meta">${stageChip(d.stage)} <span class="sep">·</span> <b class="tnum">${money(d.arr||d.amount)}</b>
       <span class="sep">·</span> ${esc(d.dealtype==='newbusiness'?'New business':d.dealtype||'—')}${d.industry?`<span class="sep">·</span> ${esc(d.industry)}`:''}${d.employees?`<span class="sep">·</span> ${d.employees} employees`:''}
       <span class="sep">·</span> via ${esc(d.source)}${/orum/i.test(d.source)?' ☎':''}<span class="sep">·</span> <a class="lk" href="${d.hubspot_url}" target="_blank">HubSpot ↗</a></div></div>
     ${dcsBig(d)}</div>
   ${d.loss?`<div style="margin-top:14px">${lossPanel(d)}</div>`:''}
   ${statusBar(d,open)}
   ${keyFactsCard(d)}
   <div class="sec-h"><span class="nm">What needs you</span><span class="ct">${open.length} open${resolved.length?` · ${resolved.length} resolved`:''}</span></div>
   ${open.length?`<div class="aq">${open.map(t=>actionCard(d,t)).join('')}</div>`:`<div class="allclear"><div class="big">✓ All clear</div>Nothing needs you on this deal right now. The agent is watching it and will surface the next step.</div>`}
   ${resolved.length?`<div class="resolved">${resolved.map(t=>resolvedRow(d,t)).join('')}</div>`:''}
   ${factsSection(d)}
   ${askDock(d)}`;
  applyFocus(d);
}

/* ===== Task-centric workspace engine (Phase 1) =====
   The right pane is no longer a call teleprompter. It's the AE's command center:
   the agent's proposed work for THIS deal, each item showing what the agent did
   + an editable artifact + dispose/approve. The agent never sends — the human does. */
function dealTasks(id){const ib=inboxData();const out=[];['overdue','today','upcoming'].forEach(b=>((ib.buckets||{})[b]||[]).forEach(t=>{if(t.deal_id===id)out.push(t);}));return out;}
function tStatus(id,tid){return (dst(id).tdis||{})[tid];}
function setTStatus(id,tid,st){const s=dst(id);s.tdis=s.tdis||{};if(st)s.tdis[tid]=st;else delete s.tdis[tid];save(id,s);renderDeal(id);}

/* ---- status bar + the four guarantees ---- */
function statusBar(d,open){
  const next=open[0];
  const nextTxt=next?`<span class="lab">Next</span> ${esc(next.title)} — <span style="color:var(--muted);font-weight:500">${esc(next.why)}</span>`
    :`<span class="lab">Status</span> No open actions — deal is on track.`;
  return `<div class="statusbar"><div class="next">${nextTxt}</div><div class="grts">${guaranteeChips(d,open)}</div></div>`;
}
function guaranteeChips(d,open){
  const worst=ts=>ts.some(t=>t.urgency==='overdue')?'bad':ts.length?'warn':'ok';
  const ic=st=>st==='ok'?'✓':st==='bad'?'!':'⚠';
  const chip=(label,types)=>{const ts=open.filter(x=>types.includes(x.type));const st=worst(ts);return `<span class="grt ${st}"><span class="gi">${ic(st)}</span>${label}</span>`;};
  const b=bantScore(d.id);let gSt,gLab;
  if(b.filled){gLab=`Gate · BANT ${b.total}`;gSt=b.total>=50?'ok':'bad';}
  else{gSt=open.some(t=>t.type==='Gate-Capture')?'warn':'ok';gLab='Gate';}
  return [chip('Routing',['Routing-Check']),chip('Prep',['Call Prep']),chip('Follow-up',['Draft Follow-up','Multi-thread','Watch']),
    `<span class="grt ${gSt}"><span class="gi">${ic(gSt)}</span>${gLab}</span>`].join('');
}

/* ---- action cards ---- */
function actionCard(d,t){
  const u=t.urgency;const cls=u==='overdue'?'urgent':u==='today'?'soon':'';
  const tb=TBADGE[t.type]||['watch',t.type];
  return `<div class="acard ${cls}" id="acard-${esc(t.id)}">
    <div class="acard-h"><span class="tbadge ${tb[0]}">${esc(tb[1])}</span><span class="ti">${esc(t.title)}</span><span class="u ${u}">${u}</span></div>
    <div class="why">${esc(t.why)}</div>
    <div class="did"><b>Agent</b><span>${agentDid(d,t)}</span></div>
    ${artifactFor(d,t)}</div>`;
}
function agentDid(d,t){const hasAI=d.ai_fields&&Object.keys(d.ai_fields).length;return ({
  'Call Prep':'Assembled a prep sheet from HubSpot + the latest Gong call. Skim it and you can walk in cold-proofed.',
  'Draft Follow-up':'Drafted the note below from the deal context. Edit anything, then send it from your own inbox.',
  'Gate-Capture':hasAI?'Pulled the gate values from the transcript with the supporting quote. Accept or correct each.':'Will extract these from the latest Gong transcript on the next pass — confirm what to capture.',
  'Routing-Check':'Ran this deal through the routing rules and flagged it so a mis-routed lead can’t slip through.',
  'Multi-thread':'Drafted an intro to a second stakeholder so the deal stops being single-threaded.',
  'Watch':'Noticed this deal went quiet past the inactivity line and drafted a re-engagement nudge.'
}[t.type]||'Surfaced this for your review.');}
function artifactFor(d,t){switch(t.type){
  case 'Call Prep':return prepArtifact(d,t);
  case 'Draft Follow-up':return draftArtifact(d,t);
  case 'Gate-Capture':return gateArtifact(d,t);
  case 'Routing-Check':return routingArtifact(d,t);
  case 'Multi-thread':return emailArtifact(d,t,multiText(d),'Second-stakeholder intro');
  case 'Watch':return emailArtifact(d,t,watchText(d),'Re-engagement nudge');
  default:return actsBar(d,t,[['Mark done','done','primary']]);}}

/* generic actions row; every card can hand off to the AI dock */
function actsBar(d,t,btns){
  const b=btns.map(x=>`<button class="btn ${x[2]||''}" onclick="taskAct('${d.id}','${esc(t.id)}','${x[1]}')">${esc(x[0])}</button>`).join('');
  return `<div class="aq-acts">${b}<span class="spacer"></span><button class="btn ai" onclick="askTask('${d.id}','${esc(t.id)}')">Ask AI to revise</button></div>`;
}
function taskAct(id,tid,act){
  if(act==='copydraft')return copyDraft(tid);
  if(act==='copyprep')return copyPrep(tid);
  if(act==='done'){setTStatus(id,tid,'done');toast('Done — logged. (Phase 2 syncs this to HubSpot.)');return;}
  if(act==='disposed'){setTStatus(id,tid,'disposed');toast('Dismissed — the agent won’t resurface this.');return;}
}
function resolvedRow(d,t){const st=tStatus(d.id,t.id);
  return `<div class="rsv-row"><span class="tick">${st==='disposed'?'✕':'✓'}</span><span>${esc(t.title)}</span><span style="color:var(--faint)">· ${st==='disposed'?'dismissed':'done'}</span><a class="lk undo" onclick="setTStatus('${d.id}','${esc(t.id)}',null)">undo</a></div>`;}

/* ---- artifacts ---- */
function firstName(d){const n=(d.primary_contact&&d.primary_contact.name)||'';return n?n.split(' ')[0]:'there';}
function nextStepLine(d){return d.stage==='Discovery'?'a tailored demo built from your onboarding materials':d.stage==='Demo'?'the ROI walkthrough + pricing':d.stage==='Quote'||d.stage==='Verbal'?'finalizing the proposal and timeline':'the next working session';}
function followupText(d){const f=firstName(d);
  return `Subject: Following up — Quinn x ${d.company}\n\nHi ${f},\n\nThanks again for the time. Quick recap of where we landed:\n\n• The challenge you flagged: getting new field hires productive faster without pulling your best people off the job to train them\n• How Quinn maps to it: courses built from your own materials that your team can ship in days\n• Next step: ${nextStepLine(d)}\n\nAnything useful I can get in front of you before then? Happy to loop in whoever else should be in the room.\n\nBest,\n${D.rep}`;}
function multiText(d){const f=firstName(d);
  return `Subject: Quick intro — Quinn x ${d.company}\n\nHi [second stakeholder],\n\n${f} and I have been working through how ${d.company} ramps and retains field staff. Given your role, your read would be valuable before we go further.\n\nWould 20 minutes next week work? I’ll tailor it to what matters most to you.\n\nBest,\n${D.rep}`;}
function watchText(d){const f=firstName(d);
  return `Subject: Still the right time, ${f}?\n\nHi ${f},\n\nWanted to gently re-surface this — I know priorities shift. If onboarding/retention is still on the list this quarter, I can send a 2-minute example built from your world. If the timing’s off, just say so and I’ll circle back later.\n\nBest,\n${D.rep}`;}

function emailArtifact(d,t,gen,kind){
  const saved=(dst(d.id).drafts||{})[t.id];const txt=saved!=null?saved:gen;
  return `<div class="artifact"><div class="f-meta"><span class="pill">${esc(kind)}</span><span class="pill">Editable · sends from your inbox, never auto-sent</span></div>
    <textarea class="draftbox" id="draft-${esc(t.id)}" oninput="onDraft('${d.id}','${esc(t.id)}',this.value)">${esc(txt)}</textarea></div>`
    +actsBar(d,t,[['Copy draft','copydraft','primary'],['Mark sent','done',''],['Dismiss','disposed','ghost']]);
}
function draftArtifact(d,t){return emailArtifact(d,t,followupText(d),'Follow-up email');}
function onDraft(id,tid,v){const s=dst(id);s.drafts=s.drafts||{};s.drafts[tid]=v;save(id,s);}
function copyDraft(tid){const el=document.getElementById('draft-'+tid);if(el){navigator.clipboard&&navigator.clipboard.writeText(el.value);toast('Draft copied — paste into your email');}}
function copyPrep(tid){const el=document.getElementById('prep-'+tid);if(el){navigator.clipboard&&navigator.clipboard.writeText(el.innerText);toast('Prep sheet copied');}}

function prepArtifact(d,t){
  const cs=curStageObj(d);
  const qs=(cs.items||[]).filter(it=>it.prompt).slice(0,5).map(it=>`<li>${esc(it.prompt)}</li>`).join('');
  const stk=(d.stakeholders||[]).map(s=>`${esc(s.name)}${s.title?' ('+esc(s.title)+')':''}`).join(', ')||'Single-threaded — no 2nd contact yet (add one)';
  const facts=[`${esc(d.industry||'Industry n/a')} · ${d.employees||'?'} employees`,`Stage: ${esc(d.stage)}${d.dcs&&d.dcs.days_in_stage!=null?' · '+d.dcs.days_in_stage+'d in stage':''}`,`Source: ${esc(d.source||'—')}`];
  const html=`<div class="prepsheet" id="prep-${esc(t.id)}">
    <div class="blk"><div class="bh">Key facts</div><ul>${facts.map(f=>`<li>${f}</li>`).join('')}</ul></div>
    <div class="blk"><div class="bh">Who’s in the room</div><div>${stk}</div></div>
    ${qs?`<div class="blk"><div class="bh">Questions to ask</div><ul class="qlist">${qs}</ul></div>`:''}
    <div class="blk"><div class="bh">Bring</div><ul><li>A Quinn customer in ${esc(d.industry||'their space')} to reference</li><li>The tailored example built from their materials</li></ul></div></div>`;
  return `<div class="artifact">${html}</div>`+actsBar(d,t,[['Copy prep sheet','copyprep','primary'],['Mark ready','done','']]);
}
function routingArtifact(d,t){
  const amount=d.arr||d.amount||0;const emp=d.employees||0;
  let rec='Within standard AE thresholds — confirm it’s yours and you’re clear to work it.';
  if(amount>40000)rec=`$${Math.round(amount).toLocaleString()} is above the ~$40k large-deal line → recommend looping in Arlen before advancing.`;
  else if(emp>=1000)rec=`${emp.toLocaleString()} employees → strategic size; confirm ownership vs. Arlen.`;
  else if(!(d.stakeholders||[]).length)rec='No contact on file — confirm this lead is correctly routed to you before working it.';
  return `<div class="artifact"><div class="prepsheet"><div class="blk"><div class="bh">Routing check</div><div>${esc(rec)}</div></div></div></div>`
    +actsBar(d,t,[['Confirm — it’s mine','done','primary'],['Send to Arlen','done',''],['Dismiss','disposed','ghost']]);
}
function gateArtifact(d,t){
  const cs=curStageObj(d);const gates=(cs.items||[]).filter(it=>it.gate);const af=d.ai_fields||{};
  const rows=gates.map(it=>{
    const ai=af[it.id];let body;
    if(isCap(d.id,it.id)){body=`<div class="gv">✓ ${esc(capVal(d.id,it.id))}</div>`;}
    else if(ai){body=`<div class="gv">${esc(ai.value)}</div>${ai.evidence?`<div class="gev">${esc(ai.evidence)}</div>`:''}
      <div class="gacts"><button class="btn sm primary" onclick="acceptField('${d.id}','${it.id}')">Accept</button><button class="btn sm ghost" onclick="dismissField('${d.id}','${it.id}')">Dispose</button>${ai.cite&&ai.cite.gid?`<a class="lk" style="margin-left:4px;align-self:center" onclick="showCall('${d.id}','${ai.cite.gid}',event)">${esc(ai.cite.label||'source')}</a>`:''}</div>`;}
    else{body=`<div class="gev">Pending — the agent extracts this from the latest Gong transcript on the next pass.</div>`;}
    return `<div class="gaterow"><div class="gl"><span class="g"></span>${esc(it.label)}</div>${body}</div>`;
  }).join('');
  return `<div class="artifact"><div class="gateprop">${rows||'<div class="gaterow">No gate fields on this stage.</div>'}</div>${bantPanel(d)}</div>`
    +actsBar(d,t,[['Mark captured','done','primary']]);
}

/* ---- Key facts: the live deal record, kept current (Johnny's pre-Discovery key facts) ----
   Value precedence: AE-confirmed (localStorage kf) > agent-extracted from Gong (ai_fields) > HubSpot.
   Editing saves to the deal record now; HubSpot write-back turns on in Phase 3 (gated on Johnny's go). */
const KEYFACTS=[
  {k:'vertical',label:'Vertical',get:d=>d.industry,hint:'HubSpot industry_category — our live verticals'},
  {k:'pd_field',label:'Field workers',ai:'pd_field',hint:'# frontline/deskless techs — drives the routing band'},
  {k:'pd_size',label:'Company size',ai:'pd_size',get:d=>d.employees?d.employees+' employees':'',hint:'total headcount'},
  {k:'pd_lms',label:'Current LMS',ai:'pd_lms',ai2:'d_tools',hint:'none / replacing / keeping (+ name)'},
  {k:'contact',label:'Primary contact',get:d=>{const c=d.primary_contact||{};return c.name?c.name+(c.title?' · '+c.title:''):'';},hint:'champion + title'},
  {k:'pd_whynow',label:'Why-now',ai:'pd_whynow',hint:'trigger driving the evaluation'},
];
function kfStore(id){return dst(id).kf||{};}
function httpify(u){return /^https?:\/\//i.test(u)?u:'https://'+u;}
function kfResolve(d,f){
  const ov=kfStore(d.id)[f.k];
  if(ov!=null&&ov!=='')return {val:ov,src:'you'};
  const af=d.ai_fields||{};
  if(f.ai&&af[f.ai]&&af[f.ai].value)return {val:af[f.ai].value,src:'gong',cite:af[f.ai].cite};
  if(f.ai2&&af[f.ai2]&&af[f.ai2].value)return {val:af[f.ai2].value,src:'gong',cite:af[f.ai2].cite};
  if(f.get){const g=f.get(d);if(g)return {val:g,src:'hubspot'};}
  return {val:'',src:'none'};
}
function keyFactsCard(d){
  const rows=KEYFACTS.map(f=>{
    const r=kfResolve(d,f);
    const tag={you:'<span class="kf-src you">✎ confirmed</span>',gong:'<span class="kf-src gong">from Gong</span>',hubspot:'<span class="kf-src hs">HubSpot</span>',none:''}[r.src]||'';
    const link=f.k==='vertical'&&d.website?` <a class="lk" href="${esc(httpify(d.website))}" target="_blank">site ↗</a>`:'';
    const cite=r.cite&&r.cite.gid?` <a class="lk" onclick="showCall('${d.id}','${r.cite.gid}',event)">${esc(r.cite.label||'source')}</a>`:'';
    const val=r.val?esc(r.val):'<span class="kf-empty">not captured yet</span>';
    return `<div class="kf-row" id="kf-${d.id}-${f.k}">
      <div class="kf-l" title="${esc(f.hint)}">${f.label}</div>
      <div class="kf-v">${val} ${tag}${link}${cite}</div>
      <button class="kf-edit" title="Update — saves to the deal record" onclick="editKF('${d.id}','${f.k}')">✎</button></div>`;
  }).join('');
  const desc=d.company_desc?`<div class="kf-desc">${esc(d.company_desc.slice(0,280))}${d.company_desc.length>280?'…':''}</div>`:'';
  return `<div class="keyfacts"><div class="kf-h"><b>Key facts</b><span class="kf-note">the live deal record · confirm a value to keep HubSpot current</span></div>
    <div class="kf-grid">${rows}</div>${desc}</div>`;
}
function editKF(id,k){
  const f=KEYFACTS.find(x=>x.k===k);const d=dealById(id);const r=kfResolve(d,f);
  const row=document.getElementById('kf-'+id+'-'+k);if(!row)return;
  const vc=row.querySelector('.kf-v');
  vc.innerHTML=`<input class="kf-in" id="kfin-${id}-${k}" value="${esc(r.val||'')}"> <button class="btn sm primary" onclick="saveKF('${id}','${k}')">Save</button> <button class="btn sm ghost" onclick="renderDeal('${id}')">Cancel</button>`;
  const inp=document.getElementById('kfin-'+id+'-'+k);if(inp){inp.focus();inp.onkeydown=e=>{if(e.key==='Enter')saveKF(id,k);if(e.key==='Escape')renderDeal(id);};}
}
function saveKF(id,k){
  const inp=document.getElementById('kfin-'+id+'-'+k);if(!inp)return;
  const s=dst(id);s.kf=s.kf||{};s.kf[k]=inp.value.trim();save(id,s);
  toast('Saved to the deal record · HubSpot write-back turns on in Phase 3');renderDeal(id);
}

/* ---- collapsed facts & evidence ---- */
function factsSection(d){
  return `<div class="facts-wrap">
    <div class="facts-toggle" onclick="this.nextElementSibling.classList.toggle('hide');this.querySelector('.cv').textContent=this.nextElementSibling.classList.contains('hide')?'▸':'▾'"><span class="cv">▸</span> Deal facts &amp; evidence — the data behind these actions</div>
    <div class="facts-grid hide">
      <div>${factsBox(d)}${bantPanel(d)}${roiCalc(d)}</div>
      <div>${dcsPanel(d)}${stakePanel(d)}${activityPanel(d)}</div>
    </div></div>`;
}
function factsBox(d){const c=d.primary_contact||{};
  const rows=[['Stage',esc(d.stage)],['Value',money(d.arr||d.amount)],['Industry',esc(d.industry||'—')],['Employees',d.employees||'—'],['Source',esc(d.source||'—')],['Days in stage',(d.dcs&&d.dcs.days_in_stage!=null)?d.dcs.days_in_stage+'d':'—'],['Primary contact',c.name?esc(c.name+(c.title?' · '+c.title:'')):'—']];
  return `<div class="factbox"><h3>Key facts</h3><div class="kv">${rows.map(r=>`<div class="k">${r[0]}</div><div class="v">${r[1]}</div>`).join('')}</div></div>`;
}

/* ---- Ask the agent dock ---- */
function askDock(d){
  return `<div class="askdock" id="askdock">
    <div class="askdock-h"><span class="ic"></span><b>Ask the agent</b><span>· about ${esc(d.company)}</span></div>
    <div class="asklog" id="askLog"><div class="askmsg agent"><span class="b">I’m watching this deal. Ask me to draft something, explain why it isn’t qualified, or tell you what’s blocking it — or tap a shortcut.</span></div></div>
    <div class="askchips">
      <span class="askchip" onclick="askQuick('${d.id}','draft')">Draft the follow-up</span>
      <span class="askchip" onclick="askQuick('${d.id}','gate')">Why isn’t this qualified?</span>
      <span class="askchip" onclick="askQuick('${d.id}','blocking')">What’s blocking this?</span>
      <span class="askchip" onclick="askQuick('${d.id}','prep')">Build a prep sheet</span></div>
    <div class="askin"><input id="askInput" placeholder="Ask about ${esc(d.company)}…" onkeydown="if(event.key==='Enter')askSend('${d.id}')"><button onclick="askSend('${d.id}')">Send</button></div></div>`;
}
function askAppend(role,html){const log=$('#askLog');if(!log)return;log.insertAdjacentHTML('beforeend',`<div class="askmsg ${role}"><span class="b">${html}</span></div>`);log.scrollTop=log.scrollHeight;}
function askSend(id){const inp=$('#askInput');if(!inp)return;const q=inp.value.trim();if(!q)return;inp.value='';askAppend('you',esc(q));const d=dealById(id);setTimeout(()=>askAppend('agent',askReply(d,q)),260);}
function askQuick(id,kind){const d=dealById(id);const label={draft:'Draft the follow-up',gate:'Why isn’t this qualified yet?',blocking:'What’s blocking this deal?',prep:'Build a prep sheet'}[kind]||kind;askAppend('you',esc(label));setTimeout(()=>askAppend('agent',askReply(d,label)),260);}
function askTask(id,tid){const t=findTask(tid);const inp=$('#askInput');if(inp){inp.value=t?('Revise the '+t.title.toLowerCase()):'Revise this';inp.focus();}const dk=$('#askdock');if(dk)dk.scrollIntoView({behavior:'smooth',block:'center'});}
function askReply(d,q){
  const ql=q.toLowerCase();const open=dealTasks(d.id).filter(t=>!tStatus(d.id,t.id));const note=' <span style="color:var(--faint)">· Phase-1 preview — the live agent answers here in Phase 2.</span>';
  let core;
  if(/block|stuck|stall|left|holding|next/.test(ql)){core=open.length?('Right now: '+open.map(t=>esc(t.title)+' — '+esc(t.why)).join('<br>')):'Nothing’s blocking it — no open actions on this deal.';}
  else if(/qualif|bant|gate|score|why is.*not/.test(ql)){const b=bantScore(d.id);core=b.filled?('BANT is '+b.total+'/100 (need 50). '+(b.total>=50?'Qualified.':'Below threshold — strengthen the weak components in the Gate card above.')):'BANT isn’t scored yet. Open the Gate card and accept the extracted values, or score the components.';}
  else if(/draft|follow|recap|email|write|revise/.test(ql)){const ft=open.find(t=>t.type==='Draft Follow-up');core=ft?'There’s a follow-up draft in your action queue above — edit it and send from your inbox.':'No follow-up is due, but I can draft one. Say the word and I’ll add it to your queue.';}
  else if(/prep|prepare|meeting|call/.test(ql)){const pt=open.find(t=>t.type==='Call Prep');core=pt?'Your prep sheet is in the action queue above — key facts, who’s in the room, and questions to ask.':'No call is scheduled, so no prep sheet yet. I’ll build one the moment a meeting books.';}
  else{core='This deal: '+esc(d.stage)+' · '+money(d.arr||d.amount)+' · '+esc(d.industry||'industry n/a')+' · '+((d.stakeholders||[]).length)+' contact(s). '+(open.length?open.length+' open action(s) in your queue above.':'No open actions.');}
  return core+note;
}
function dcsBig(d){const c=d.dcs.color,s=d.dcs.score;const col=c==='green'?'var(--green)':c==='yellow'?'var(--amber)':c==='red'?'var(--red)':'var(--faint)';const bg=c==='green'?'var(--green-bg)':c==='yellow'?'var(--amber-bg)':c==='red'?'var(--red-bg)':'var(--panel2)';
  if(isWon(d))return `<div style="text-align:center"><div class="ring" style="background:var(--green-bg);color:var(--green);font-size:18px">Won</div><div style="font-size:10px;font-weight:600;color:var(--muted);margin-top:4px;text-transform:uppercase;letter-spacing:.03em">Closed</div></div>`;
  return `<div style="text-align:center"><div class="ring" style="background:${bg};color:${col}">${s==null?'—':s}</div><div style="font-size:10px;font-weight:600;color:var(--muted);margin-top:4px;text-transform:uppercase;letter-spacing:.03em">Confidence</div></div>`;}
function stageSection(d,s,i){
  const open=!!openStages[d.id][s.key];const cur=s.key===d.rubric_stage;const pr=stageProg(d,s);
  const done=pr.gates>0&&pr.gmet===pr.gates;
  const items=s.items.map(it=>ritem(d,it)).join('');
  const bant=s.key==='disc'?bantPanel(d):'';
  const roi=s.key==='roi'?roiCalc(d):'';
  const notes=`<div class="snotes"><label>Notes — ${esc(s.name)}</label><textarea placeholder="Capture anything for this stage…" oninput="setNote('${d.id}','${s.key}',this.value)">${esc(dst(d.id).notes[s.key]||'')}</textarea></div>`;
  return `<div class="stage ${open?'open':''} ${cur?'cur':''} ${done?'done':''}" id="stage-${s.key}">
    <div class="stage-head" onclick="toggleStage('${d.id}','${s.key}')">
      <div class="stage-num">${done?'✓':i+1}</div>
      <div class="stage-tt"><div class="nm">${esc(s.name)}${cur?' <span class="cur-tag">Current</span>':''}</div><div class="bl">${esc(s.blurb)}</div></div>
      <div class="stage-prog"><div class="n">${pr.cap}/${pr.tot} captured${pr.gates?` · gates ${pr.gmet}/${pr.gates}`:''}</div><div class="pbar"><i style="width:${Math.round(pr.cap/pr.tot*100)}%"></i></div></div>
      <div class="caret">▸</div></div>
    <div class="stage-body">${items}${bant}${roi}${notes}</div></div>`;
}
function ritem(d,it){
  const val=capVal(d.id,it.id);const cap=val!=='';const src=dst(d.id).src[it.id];
  const ai=d.ai_fields[it.id];const dis=dst(d.id).dis[it.id];
  let input='';
  if(it.type==='yesno'){input=`<div class="yn"><button class="${val==='yes'?'on':''}" onclick="setCap('${d.id}','${it.id}','yes')">Yes</button><button class="${val==='no'?'on no':''}" onclick="setCap('${d.id}','${it.id}','no')">No</button></div>`;}
  else if(it.type==='enum'){input=`<select onchange="setCap('${d.id}','${it.id}',this.value)"><option value="">—</option>${it.options.map(o=>`<option ${val===o?'selected':''}>${esc(o)}</option>`).join('')}</select>`;}
  else if(it.type==='text'){input=`<textarea rows="2" placeholder="Capture…" oninput="setCapDebounced('${d.id}','${it.id}',this.value)">${esc(val)}</textarea>`;}
  else{input=`<input type="number" placeholder="${it.type==='money'?'$ amount':'number'}" value="${esc(val)}" oninput="setCapDebounced('${d.id}','${it.id}',this.value)">`;}
  const promptHTML=it.prompt?`<div class="prompt" onclick="copyPrompt(this)" title="Click to copy">"${esc(it.prompt)}"</div>`:'';
  let aiB='';
  if(ai&&!cap&&!dis){aiB=`<div class="ai-sug"><div class="hd">AI suggestion</div><div class="vv">${esc(ai.value)}</div>${ai.evidence?`<div class="ev">${esc(ai.evidence)}</div>`:''}
    <div class="acts"><button class="ok" onclick="acceptField('${d.id}','${it.id}')">Accept</button><button class="no" onclick="dismissField('${d.id}','${it.id}')">Dismiss</button>${ai.cite&&ai.cite.gid?`<a class="lk cite" onclick="showCall('${d.id}','${ai.cite.gid}',event)">${esc(ai.cite.label)}</a>`:''}</div></div>`;}
  return `<div class="ritem ${cap?'cap':''}"><div class="rl">${it.gate?'<span class="gate"></span>':''}${esc(it.label)}${cap&&src==='ai'?' <span class="ai-src">AI</span>':''}</div>
    <div class="rh">${esc(it.hint)}</div>${promptHTML}<div class="rin">${input}</div>${aiB}</div>`;
}
function copyPrompt(el){navigator.clipboard&&navigator.clipboard.writeText(el.textContent.replace(/^"|"$/g,''));toast('Question copied');}
function toggleStage(id,k){openStages[id][k]=!openStages[id][k];renderDeal(id);}
const _t={};
function setCapDebounced(id,iid,v){clearTimeout(_t[iid]);_t[iid]=setTimeout(()=>{const s=dst(id);s.cap[iid]=v;s.src[iid]='ae';save(id,s);updateBant(id);},400);}
function setCap(id,iid,v){const s=dst(id);if(it_isyn(iid)&&s.cap[iid]===v)v='';s.cap[iid]=v;s.src[iid]='ae';save(id,s);renderDeal(id);}
function it_isyn(iid){return (rubricById[iid]||{}).type==='yesno';}
function acceptField(id,iid){const s=dst(id);s.cap[iid]=dealById(id).ai_fields[iid].value;s.src[iid]='ai';save(id,s);renderDeal(id);}
function dismissField(id,iid){const s=dst(id);s.dis[iid]=true;save(id,s);renderDeal(id);}
function setNote(id,k,v){const s=dst(id);s.notes[k]=v;save(id,s);}

/* ---------- BANT Qualification Score ---------- */
const BANT_FIELDS=[{id:'d_bant_b',label:'Budget',max:20},{id:'d_bant_a',label:'Authority',max:20},{id:'d_bant_n',label:'Need',max:40},{id:'d_bant_t',label:'Timeline',max:20}];
/* Precedence: AE-confirmed (capVal) > agent-extracted from Gong (ai_fields) > unset. */
function bantRaw(id,iid){
  const c=capVal(id,iid);if(c!==''){const v=parseFloat(c);if(!isNaN(v))return {v,src:'you'};}
  const d=dealById(id);const af=d&&d.ai_fields&&d.ai_fields[iid];
  if(af&&af.value!=null&&af.value!==''){const v=parseFloat(af.value);if(!isNaN(v))return {v,src:'gong'};}
  return {v:NaN,src:null};
}
function bantScore(id){let total=0,filled=0,ai=false;BANT_FIELDS.forEach(f=>{const r=bantRaw(id,f.id);if(!isNaN(r.v)&&r.v>0){total+=r.v;filled++;if(r.src==='gong')ai=true;}});return {total,filled,max:100,ai};}
function updateBant(id){const el=document.getElementById('bant-'+id);if(el){const d=dealById(id);if(d)el.outerHTML=bantPanel(d);}}
function bantPanel(d){
  const bs=bantScore(d.id);
  const rows=BANT_FIELDS.map(f=>{const r=bantRaw(d.id,f.id);const v=!isNaN(r.v)?r.v:0;const pct=Math.round(v/f.max*100);
    const tag=r.src==='gong'?'<span class="kf-src gong" style="margin-left:6px">Gong</span>':'';
    return `<div class="bant-row"><div class="lab">${f.label}${tag}</div><div class="track"><i style="width:${pct}%"></i></div><div class="bv">${v}/${f.max}</div></div>`;}).join('');
  const pass=bs.total>=50;const statusCls=bs.filled===0?'':'status '+(pass?'pass':'fail');const statusTxt=bs.filled===0?'No BANT signal extracted yet':pass?'QUALIFIED':'BELOW THRESHOLD';
  const src=bs.ai?'<span class="kf-note" style="display:block;margin-top:6px">Agent-extracted from Gong — accept the values in the Gate card to confirm.</span>':'';
  return `<div class="bant" id="bant-${d.id}"><h4>BANT Qualification<span class="score">${bs.filled?bs.total+'/100':'—'}</span></h4>${rows}
    <div class="threshold"><span>Threshold: 50/100</span><span class="${statusCls}">${statusTxt}</span></div>${src}</div>`;
}

/* ---------- ROI Calculator ---------- */
const ROI_IN=[
  ['techs','Field techs in scope','How many techs will use Quinn?'],
  ['hourly','Avg hourly cost ($)','Fully loaded cost per tech hour'],
  ['ramp_curr','Current ramp (weeks)','Weeks to full productivity today'],
  ['ramp_new','New ramp w/ Quinn (weeks)','Target ramp with Quinn training'],
  ['hires','New hires per year','Annual hiring volume'],
  ['callback','Callback/rework rate (%)','% of jobs requiring callbacks today'],
  ['callback_cost','Cost per callback ($)','Avg cost of each callback/rework'],
  ['turnover','Annual turnover (%)','% of field team leaving per year'],
  ['replace_cost','Cost to replace ($)','Hiring + ramp cost per replacement'],
];
function roiDefaults(d){return {techs:d.employees||'',hourly:45,ramp_curr:4,ramp_new:2,hires:'',callback:15,callback_cost:350,turnover:25,replace_cost:8000};}
function roiVal(d,k){const s=dst(d.id);const dv=roiDefaults(d);return s.roi[k]!=null&&s.roi[k]!==''?s.roi[k]:(dv[k]!==''?dv[k]:'');}
function setRoi(d,k,v){const s=dst(d.id);s.roi[k]=v;save(d.id,s);roiRender(d);}
function roiCompute(d){const g=k=>parseFloat(roiVal(d,k))||0;
  const rampSaved=(g('ramp_curr')-g('ramp_new'))*40*g('hourly')*g('hires');
  const callbackSaved=g('techs')*(g('callback')/100)*g('callback_cost')*12*0.3;
  const turnoverSaved=g('techs')*(g('turnover')/100)*g('replace_cost')*0.2;
  const tot=rampSaved+callbackSaved+turnoverSaved;const price=d.amount||0;const mult=price?tot/price:0;const pay=tot?price/(tot/12):0;
  return {rampSaved,callbackSaved,turnoverSaved,tot,mult,pay,price};}
function roiCalc(d){const ins=ROI_IN.map(([k,l,h])=>`<div class="roi-in"><label title="${esc(h)}">${l}</label><input type="number" value="${esc(roiVal(d,k))}" placeholder="${h}" oninput="setRoiDeb('${d.id}','${k}',this.value)"></div>`).join('');
  return `<div class="roi"><h4><span class="live"></span> ROI Calculator</h4><div class="rsub">Quinn's 3-lever value model: onboarding productivity, quality/callbacks, retention. Updates live as you fill in prospect answers.</div>
    <div class="roi-grid">${ins}</div><div id="roiout-${d.id}">${roiOut(d)}</div></div>`;}
function roiOut(d){const c=roiCompute(d);
  return `<div class="roi-out"><div class="o"><div class="v">${money(c.rampSaved)}</div><div class="l">Onboarding productivity / yr</div></div>
    <div class="o"><div class="v">${money(c.callbackSaved)}</div><div class="l">Callbacks reduced / yr</div></div>
    <div class="o"><div class="v">${money(c.turnoverSaved)}</div><div class="l">Turnover savings / yr</div></div></div>
    <div class="roi-tot"><span class="big">${money(c.tot)}/yr</span>${c.price?`<span class="x">vs ${money(c.price)} price · <b>${c.mult.toFixed(1)}× ROI</b> · ${c.pay<1?'<1':Math.round(c.pay)} mo payback</span>`:''}</div>
    <button class="roi-cp" onclick="copyRoi('${d.id}')">Copy ROI summary</button>`;
}
const _rt={};function setRoiDeb(id,k,v){clearTimeout(_rt[k]);_rt[k]=setTimeout(()=>{const d=dealById(id);const s=dst(id);s.roi[k]=v;save(id,s);const el=$('#roiout-'+id);if(el)el.innerHTML=roiOut(d);},300);}
function roiRender(d){const el=$('#roiout-'+d.id);if(el)el.innerHTML=roiOut(d);}
function copyRoi(id){const d=dealById(id);const c=roiCompute(d);const t=`${d.company} — Quinn ROI Summary\n\nOnboarding productivity: ${money(c.rampSaved)}/yr\nCallback reduction: ${money(c.callbackSaved)}/yr\nTurnover savings: ${money(c.turnoverSaved)}/yr\n\nTotal annual value: ${money(c.tot)}/yr\nQuinn investment: ${money(c.price)}/yr\nROI: ${c.mult.toFixed(1)}× · Payback: ${Math.round(c.pay)} months`;
  navigator.clipboard&&navigator.clipboard.writeText(t);toast('ROI summary copied');}

/* ---------- side panels ---------- */
function dcsPanel(d){const sc=d.dcs.scores||{};const dims=[['pain','Pain'],['champion','Champion'],['multi_threading','Multi-thread'],['buying_language','Buying lang.'],['objection_status','Objections']];
  const bars=dims.filter(x=>sc[x[0]]!=null).map(x=>`<div class="barrow"><div class="bl">${x[1]}</div><div class="track"><i style="width:${sc[x[0]]*10}%;background:${sc[x[0]]>=7?'var(--green)':sc[x[0]]>=4?'var(--amber)':'var(--red)'}"></i></div><div class="bv">${sc[x[0]]}</div></div>`).join('');
  const alerts=(d.alerts||[]).map(a=>`<div class="flag ${a.sev}" style="margin-top:6px">${esc(a.text)}</div>`).join('');
  const tag=d.ai_engine?`<span class="engtag ${d.ai_engine}">${d.ai_engine==='claude'?'Claude':'Heuristic'}</span>`:'';
  return `<div class="panel"><h3>Deal Confidence ${tag}<span class="ct">${d.dcs.score==null?'—':d.dcs.score}</span></h3>${bars?`<div class="bars">${bars}</div>`:'<div class="empty" style="padding:4px 0">No scored calls yet.</div>'}${alerts}${d.dcs.rationale?`<div class="rationale">${esc(d.dcs.rationale)}</div>`:''}</div>`;}
function stakePanel(d){if(!d.stakeholders.length)return `<div class="panel" id="panel-stakeholders"><h3>Stakeholders <span class="ct">0</span></h3><div class="empty" style="padding:4px 0">No stakeholder on file — single-threaded. Add a 2nd contact / confirm routing.</div></div>`;const ps=d.stakeholders.map(s=>{const dm=/\b(vp|chief|coo|ceo|cfo|president|owner|founder|head|director|vice)\b/i.test(s.title||'');return `<div class="p ${dm?'dm':''}"><b>${esc(s.name)}</b>${s.title?` <span>· ${esc(s.title)}</span>`:''}</div>`;}).join('');
  return `<div class="panel" id="panel-stakeholders"><h3>Stakeholders <span class="ct">${d.stakeholders.length}</span></h3><div class="stk">${ps}</div></div>`;}
function lossPanel(d){const l=d.loss;if(!l)return'';return `<div class="panel loss"><h3 style="color:var(--lost)">Loss post-mortem</h3>${l.reason?`<div style="font-size:13px;color:var(--muted);line-height:1.5"><b style="color:var(--lost)">Why:</b> ${esc(l.reason)}</div>`:''}${l.lessons?`<div style="font-size:13px;color:var(--muted);line-height:1.5;margin-top:8px"><b style="color:var(--lost)">Lesson:</b> ${esc(l.lessons)}</div>`:''}</div>`;}
function activityPanel(d){const items=(d.timeline||[]).slice(0,40);const lbl={call:'Call',email:'Email',meeting:'Meeting',note:'Note',stage:'Stage'};
  const body=items.map(it=>{const btn=it.kind==='call'?` · <a class="lk" onclick="showCall('${d.id}','${it.ref}',event)">summary</a>`:'';
    return `<div class="it"><span class="ktag">${lbl[it.kind]||'—'}</span><div><div class="ti">${esc(it.title)}</div><div class="mt">${esc(it.sub||'')}${it.sub?' · ':''}${esc(fmtDate(it.ts))}${btn}</div></div></div>`;}).join('');
  return `<div class="panel" id="panel-activity"><h3 style="cursor:pointer" onclick="this.parentNode.querySelector('.act').classList.toggle('hide');this.querySelector('.tg').textContent=this.querySelector('.tg').textContent==='+'?'–':'+'">Activity <span class="ct"><span class="tg">+</span> ${d.calls.length} calls · ${d.emails.length} emails</span></h3><div class="act hide">${body||'<div class="empty">No activity.</div>'}</div></div>`;}

/* ---------- call popover + KB ---------- */
function showCall(did,gid,e){e.stopPropagation();const d=dealById(did);const c=d.calls.find(x=>x.gid===gid);const p=$('#pop');if(!c)return;
  p.innerHTML=`<div class="pt">${esc(c.title)}</div><div class="pm">${esc(fmtDate(c.date))}${c.duration_min?' · '+c.duration_min+' min':''} · <a class="lk" href="${c.url}" target="_blank">Open in Gong ↗</a></div>
    ${c.who?`<div class="lab">Who</div><div class="who">${esc(c.who)}</div>`:''}${c.discussed&&c.discussed.length?`<div class="lab">Discussed</div><ul>${c.discussed.slice(0,6).map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`:''}${c.sentiment?`<div class="lab">Sentiment</div><div class="sent">${esc(c.sentiment)}</div>`:''}${c.next_steps&&c.next_steps.length?`<div class="lab">Next steps</div><ul>${c.next_steps.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`:''}${!c.who&&!(c.discussed||[]).length?'<div class="who" style="margin-top:10px;color:var(--faint)">No AI summary yet — open in Gong, or Full sync with Claude credits.</div>':''}`;
  p.classList.add('open');const r=e.target.getBoundingClientRect?e.target.getBoundingClientRect():{left:200,bottom:200};let x=Math.min(r.left,window.innerWidth-390),y=r.bottom+8;if(y+p.offsetHeight>window.innerHeight-10)y=Math.max(10,window.innerHeight-p.offsetHeight-10);p.style.left=Math.max(10,x)+'px';p.style.top=y+'px';}
document.addEventListener('click',e=>{const p=$('#pop');if(p.classList.contains('open')&&!p.contains(e.target)&&!e.target.closest('.lk'))p.classList.remove('open');});
let kbTab=0;
function md(t){return esc(t).replace(/^### (.*)$/gm,'<h3>$1</h3>').replace(/^## (.*)$/gm,'<h2>$1</h2>').replace(/^# (.*)$/gm,'<h1>$1</h1>').replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>').replace(/`(.+?)`/g,'<code>$1</code>').replace(/^[\-\*] (.*)$/gm,'<li>$1</li>').replace(/(<li>[\s\S]*?<\/li>)/g,'<ul>$1</ul>').split(/\n\n+/).map(b=>b.match(/^<(h|ul)/)?b:('<p>'+b.replace(/\n/g,' ')+'</p>')).join('');}
function openKB(){$('#scrim').classList.add('on');$('#drawer').classList.add('on');renderKB();}
function closeKB(){$('#scrim').classList.remove('on');$('#drawer').classList.remove('on');}
function renderKB(){if(!D)return;$('#kbTabs').innerHTML=D.kb.map((s,i)=>`<button class="${i===kbTab?'on':''}" onclick="kbTab=${i};renderKB()">${esc(s.title)}</button>`).join('');$('#kbBody').innerHTML=D.kb.length?md(D.kb[kbTab].md):'<div class="empty">No KB.</div>';}
load();
setInterval(()=>{if(!document.hidden)refresh(false,true);},300000);
</script>
</body></html>
"""
