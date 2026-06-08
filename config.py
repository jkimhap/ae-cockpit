"""Config + env loading for the AE Cockpit (standalone, source-of-truth from HubSpot).

Loads ae-cockpit/.env if present, else falls back to the existing quinn-os/.env
so we reuse the same HUBSPOT_API_KEY / GONG_ACCESS_KEY / GONG_SECRET / ANTHROPIC_API_KEY
without duplicating secrets. This project does NOT read quinn-os/data/*.
"""
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE_DIR = HERE / "cache"

# Rep roster — email is the source of truth for ownership (matched to HubSpot owner).
REPS = {
    "grant": os.getenv("GRANT_EMAIL", "grant@meetquinn.ai"),
    "derek": os.getenv("DEREK_EMAIL", "derek@meetquinn.ai"),
    "arlen": os.getenv("ARLEN_EMAIL", "arlen@meetquinn.ai"),
    "luke":  os.getenv("LUKE_EMAIL",  "luke@meetquinn.ai"),
    "ian":   os.getenv("IAN_EMAIL",   "ian@meetquinn.ai"),
}

def load_env():
    for p in [HERE / ".env", HERE.parent / "quinn-os" / ".env"]:
        if p.exists():
            for line in p.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
            return p
    return None
