# Quinn AE Deal Cockpit

A per-rep sales cockpit that reads **HubSpot as the source of truth, live** — built to *not*
inherit QuinnOS's snapshot drift/latency. Deals, stages, amounts, contacts, and the
engagement timeline come straight from `api.hubapi.com` at request time; calls + transcripts
come fresh from Gong; the deal intelligence (confidence score, gate suggestions, summaries,
next steps) is our own Claude pass.

## Quick start

```bash
./run                      # Grant, http://localhost:8787
COCKPIT_REP=derek ./run    # any rep (grant | derek | arlen | luke | ian)
```

Then open the printed URL. **Refresh** (top right) re-pulls HubSpot in ~3s; **Full sync**
re-pulls Gong + regenerates AI (~10–15s). The page auto-refreshes HubSpot every 5 min.

## Setup (standalone clone)
Inside `~/code/quinn` it just works (reuses `../quinn-os/.env` + `.venv`). Cloned elsewhere:

```bash
cp .env.example .env          # fill in HubSpot / Gong / Anthropic tokens
python3 -m venv .venv && ./.venv/bin/pip install requests anthropic
./run
```

The Playbook panel reads `../sales-knowledge-base` if present (optional; it degrades gracefully).

## How it stays true & fresh

- **HubSpot = truth.** Every load/refresh hits HubSpot directly — no mirror, no 15-min lag.
  A fast Refresh updates stages/amounts/contacts/timeline; the AI/Gong layer is reused from
  cache until you Full sync.
- **Gong fresh.** Calls are matched to a deal by the prospect's email domain (Quinn's own
  domains are excluded), transcripts pulled per call.
- **Our own AI.** `ai.py` runs one Claude (`claude-sonnet-4-6`) call per deal → 0–100 Deal
  Confidence + components, per-call summaries, proposed gate check-offs with citations,
  next steps, and a draft note. Cached per deal by content signature.

### AI engine badge
The top bar shows **✦ Claude AI** or **⚠ Heuristic AI**. Heuristic = the Anthropic key is
out of credits, so a transparent keyword/stakeholder fallback is used (clearly labeled).
Add credits to `ANTHROPIC_API_KEY`, hit **Full sync**, and every deal upgrades to Claude.

## The deal view = a stage rubric (source of truth)
One main page (deals grouped by stage). Click a deal → a **stage-by-stage rubric**, defined
in `rubric.py`:

**Pre-Discovery → Discovery → ROI/Demo → Proposal.** Each stage is an accordion of the key
Quinn-Shape vectors to **capture** (pain layers, frontline headcount, LMS + satisfaction,
operational owner / economic buyer / 2nd stakeholder, compelling event, scope, objections,
commit…) plus a **notes** box. Hard "gates" are dotted. AI auto-fills fields it can from the
calls — you **Accept / Dismiss / edit**. Completeness (`x/y · gates m/n`) shows per stage.

The **ROI/Demo stage embeds the ROI artifact** — Sonny's 3-lever model (productivity
recovered + revenue protected + account growth → total $/yr vs price → ROI× and payback),
live as you type, with "Copy ROI summary."

Everything you capture persists in the browser (localStorage) and survives refreshes. The
old call/email timeline is demoted to a collapsed **Activity** panel. (HubSpot write-back = v2.)

## Files
| File | Role |
|---|---|
| `serve.py` | Local server: `/`, `/api/data`, `/api/refresh?full=0\|1` |
| `ui.py` | The SPA (fetches `/api/data`; Refresh/Full sync; deal workspace; KB drawer) |
| `assemble.py` | Merges HubSpot + Gong + AI into the payload (tiered fast/full) |
| `hubspot.py` | HubSpot CRM client (source of truth) |
| `gong.py` | Gong calls + transcripts |
| `ai.py` | Claude deal-intelligence pass (+ heuristic fallback) |
| `config.py` | Env loading (reuses `../quinn-os/.env` tokens) |
| `cache/` | AI results + last payload (gitignored) |

## Decoupling from QuinnOS
This project does **not** read `quinn-os/data/*`. It only borrows the `.env` tokens and the
`.venv` interpreter (which already has `requests` + `anthropic`). Give it its own `.env` and
venv to make it fully standalone.

## Notes / next
- Orum cold-call recordings aren't in HubSpot or Gong; `deal.source` shows the channel and
  flags ☎ when applicable, but Orum transcript ingest would be a separate add.
- The days-in-stage baseline is a generic win/loss-derived heuristic (30-day stale rule),
  not per-stage percentiles — refine later if useful.
