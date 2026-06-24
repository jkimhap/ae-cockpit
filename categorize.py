"""Website -> ICP-vertical categorizer.

When a deal has no Quinn vertical on its HubSpot contact (the "Industry (Quinn)"
property is blank for most records), this infers the vertical from the company's
public website: fetch the homepage + a few key pages, then ask Claude to slot the
company into exactly one of the 36 canonical ICP Rubric verticals, with evidence.

Pure-Python (requests + anthropic) so it runs inside the cockpit assemble pipeline
automatically. Results are CACHED locally (vertical_cache/<company_id>.json) — this
module NEVER writes back to HubSpot.
"""
import os, re, json, time, requests, anthropic

MODEL = "claude-sonnet-4-6"
_ICP_PATH = os.path.expanduser("~/code/quinn/sales-knowledge-base/derived/icp-tiers.json")
_client = None
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

def client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client

def _icp():
    d = json.load(open(_ICP_PATH))
    return d.get("tiers", {}), d.get("tier_labels", {})

TIERS, TIER_LABELS = _icp()
VERTICALS = list(TIERS.keys())

# HubSpot's "Industry (Quinn)" contact property (industry_category) stores snake_case
# option SLUGS (e.g. "hvac_service_provider"), not the canonical ICP vertical names that
# are the keys of TIERS (e.g. "HVAC Service Provider"). A raw TIERS.get(slug) misses ->
# tier=None -> the fit/qualify routing silently breaks (a T4 don't-sell can fall through
# to QUALIFY; a T1 loses its auto-pass). This map is the single source of truth that
# translates each slug to its canonical TIERS key. Mirror of the HubSpot property options.
SLUG_TO_VERTICAL = {
    "auto_repair__service": "Auto Repair & Service",
    "automation__controls": "Automation & Controls",
    "biomedical_equipment_service": "Biomedical Equipment Service",
    "car_wash": "Car Wash",
    "residential_cleaning": "Janitorial & Cleaning",
    "commercial_kitchen_equipment_service": "Commercial Kitchen Equipment",
    "distribution__wholesale": "Manufacturers & Distributors",
    "electrical_services": "Electrical",
    "hvac__energy_services": "Energy with HVAC Team",
    "facilities_maintenance": "Facilities Maintenance",
    "fire_protection_low_voltage__security": "Fire, Low Voltage & Security",
    "general_construction": "General & Residential Construction",
    "hvac_service_provider": "HVAC Service Provider",
    "industry_association": "Industry Associations",
    "landscaping_lawn__irrigation": "Landscaping, Lawn & Irrigation",
    "manufacturing__industrial": "Manufacturers & Distributors",
    "mechanical_construction": "Mechanical Construction",
    "pest_control": "Pest Control",
    "plumbing": "Plumbing",
    "refrigeration": "Refrigeration",
    "restaurants__hospitality": "Hospitality & Amusement",
    "restoration": "Restoration",
    "roofing__exteriors": "Roofing",
    "trade_school": "Trade Schools",
    "waste__recycling": "Waste & Recycling",
    "water_treatment_pool_service": "Water Treatment & Pool",
    # "other"/"unknown" intentionally omitted -> treated as empty by callers.
}

def canon_vertical(v):
    """Normalize a vertical to a canonical TIERS key. Accepts either a HubSpot
    'Industry (Quinn)' option slug (snake_case) or an already-canonical vertical name.
    Returns the canonical key when known, else the input unchanged (unknowns stay honest)."""
    if not v:
        return v
    s = str(v).strip()
    if s in TIERS:
        return s
    return SLUG_TO_VERTICAL.get(s, s)

# ---------------------------------------------------------------- scraping
_SUBPAGES = ["", "about", "about-us", "services", "what-we-do", "company", "solutions", "industries"]

def _clean_domain(domain):
    d = (domain or "").strip().lower()
    d = re.sub(r"^https?://", "", d).strip("/").split("/")[0]
    return d if d and "." in d else None

def _candidates(d):
    # Apex often refuses; www/http variants redirect to the canonical site. Try in order.
    return [f"https://{d}", f"https://www.{d}", f"http://{d}", f"http://www.{d}"]

def _get(url):
    try:
        r = requests.get(url, headers={"User-Agent": _UA}, timeout=12, allow_redirects=True)
        if r.status_code == 200 and "text/html" in r.headers.get("Content-Type", ""):
            return r
    except Exception:
        pass
    return None

def _html_to_text(html):
    html = re.sub(r"(?is)<(script|style|noscript|svg|head)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?is)<!--.*?-->", " ", html)
    txt = re.sub(r"(?s)<[^>]+>", " ", html)
    txt = re.sub(r"&[a-z]+;", " ", txt)
    txt = re.sub(r"\s+", " ", txt)
    return txt.strip()

def fetch_text(domain, max_chars=7000, max_pages=4):
    """Resolve the live site (trying www/http fallbacks), then fetch homepage + key pages."""
    d = _clean_domain(domain)
    if not d:
        return ""
    # Resolve homepage: first candidate that returns real HTML wins; redirects give canonical host.
    home = None
    for cand in _candidates(d):
        home = _get(cand)
        if home is not None:
            break
    if home is None:
        return ""
    from urllib.parse import urlparse
    pu = urlparse(home.url)
    base = f"{pu.scheme}://{pu.netloc}"
    out, pages, seen = [], 0, set()
    ht = _html_to_text(home.text)
    if len(ht) > 120:
        out.append(f"[{home.url}] {ht[:2500]}"); pages += 1
    seen.add(home.url.rstrip("/"))
    for sub in _SUBPAGES[1:]:
        if pages >= max_pages:
            break
        url = base + "/" + sub
        if url.rstrip("/") in seen:
            continue
        seen.add(url.rstrip("/"))
        r = _get(url)
        if r is None:
            continue
        t = _html_to_text(r.text)
        if len(t) > 120:
            out.append(f"[{url}] {t[:2500]}"); pages += 1
    return (" \n".join(out))[:max_chars]

# ---------------------------------------------------------------- classify
TOOL = {
    "name": "classify_vertical",
    "description": "Assign the company to exactly one canonical ICP vertical.",
    "input_schema": {
        "type": "object",
        "properties": {
            "vertical": {"type": "string", "enum": VERTICALS + ["Unknown"],
                         "description": "The single best-matching ICP vertical, or Unknown if the site gives no usable signal."},
            "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
            "evidence": {"type": "string", "description": "One short phrase from the site that justifies the pick."},
        },
        "required": ["vertical", "confidence", "evidence"],
    },
}

def _vert_menu():
    by_tier = {}
    for v, t in TIERS.items():
        by_tier.setdefault(t, []).append(v)
    lines = []
    for t in sorted(by_tier):
        lines.append(f"  Tier {t} ({TIER_LABELS.get(str(t), '')}): " + ", ".join(by_tier[t]))
    return "\n".join(lines)

def classify(company, domain, text):
    thin = len(text or "") < 400
    if thin:
        body = (f"The website could not be read (blank or JavaScript-only). Use ONLY what you "
                f"reliably know about this specific company from its name and domain. If you are "
                f"not confident which company this is, return Unknown — do NOT guess.\n"
                f"What little text was retrieved (may be empty):\n{text or '(none)'}")
        src = "name+domain"
    else:
        body = f"WEBSITE TEXT:\n{text}"
        src = "website"
    prompt = f"""You categorize a company into Quinn's ICP verticals for a frontline-training sales team.
Quinn sells to companies with deskless / field / frontline workforces (technicians, installers, crews, plant/warehouse staff).

Pick the SINGLE vertical that best describes what this company PRIMARILY does (its core trade or service).
If the company is clearly outside the field-service world (pure software, healthcare provider, hotel, etc.), pick the closest Tier-4 vertical. If you genuinely cannot tell, return Unknown.

CANONICAL VERTICALS (choose the name EXACTLY as written):
{_vert_menu()}

Company: {company}   Domain: {domain or '?'}

{body}

Call classify_vertical with your single best pick, a confidence, and one short evidence phrase."""
    try:
        msg = client().messages.create(model=MODEL, max_tokens=400,
            tools=[TOOL], tool_choice={"type": "tool", "name": "classify_vertical"},
            messages=[{"role": "user", "content": prompt}])
        res = {}
        for b in msg.content:
            if b.type == "tool_use":
                res = b.input; break
        v = (res.get("vertical") or "").strip()
        if v == "Unknown" or v not in TIERS:
            v = None
        return {"vertical": v, "tier": TIERS.get(v) if v else None,
                "confidence": res.get("confidence", "low"),
                "evidence": (res.get("evidence") or "")[:200], "source": src}
    except Exception as e:
        return {"vertical": None, "tier": None, "confidence": "low",
                "evidence": f"classify error: {str(e)[:120]}", "source": src}

# ---------------------------------------------------------------- cache + entrypoint
def _cache_path(cache_dir, cid):
    d = os.path.join(cache_dir, "vertical_cache")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"{cid}.json")

def _safe_key(s):
    return re.sub(r"[^a-z0-9.]+", "_", (s or "").lower()).strip("_")

def categorize(cid, company, domain, cache_dir, force=False):
    """Return {vertical, tier, confidence, evidence, source}. Cached by domain (falls back to id)
    so deals sharing a company — and the same company across reps — reuse one classification."""
    key = _safe_key(_clean_domain(domain) or str(cid))
    cp = _cache_path(cache_dir, key)
    if not force and os.path.exists(cp):
        try:
            return json.load(open(cp))
        except Exception:
            pass
    text = fetch_text(domain)
    res = classify(company, domain, text)
    res["company"] = company
    res["domain"] = domain
    try:
        json.dump(res, open(cp, "w"))
    except Exception:
        pass
    return res
