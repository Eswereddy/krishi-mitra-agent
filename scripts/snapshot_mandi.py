#!/usr/bin/env python3
"""Save a dated snapshot of REAL Agmarknet prices for the demo crops, so the app still shows real
(clearly labelled "saved") data if data.gov.in is slow or down during judging.

Usage (from the repo root, with your free data.gov.in key):
    DATA_GOV_API_KEY=xxxx python scripts/snapshot_mandi.py
Then commit backend/app/data/mandi_snapshot.json. Re-run the day before you record the demo.
"""
import json
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app import tools  # noqa: E402

CROPS = ["Paddy", "Groundnut", "Cotton", "Tomato", "Maize", "Chilli", "Onion", "Bengal Gram", "Jowar", "Sunflower"]
STATES = ["Andhra Pradesh"]
OUT = Path(__file__).resolve().parents[1] / "backend" / "app" / "data" / "mandi_snapshot.json"


def main() -> int:
    key = os.getenv("DATA_GOV_API_KEY", "")
    if not key:
        print("Set DATA_GOV_API_KEY first (free key from data.gov.in).")
        return 1
    tools.os.environ["CACHE_TTL_S"] = "0"
    records, seen = [], set()
    for state in STATES:
        for crop in CROPS:
            try:
                rows, _note = tools._fetch_live_uncached(key, state, "", crop)
            except Exception as e:  # keep going: one failing crop should not lose the rest
                print(f"  {crop}: failed ({type(e).__name__})")
                continue
            kept = 0
            for r in rows:
                sig = (str(tools._field(r, "market")), str(tools._field(r, "commodity")), str(tools._field(r, "arrival_date")))
                if sig in seen:
                    continue
                seen.add(sig)
                records.append(r)
                kept += 1
            print(f"  {crop}: {kept} rows")
    if not records:
        print("No rows fetched; snapshot not written.")
        return 1
    OUT.write_text(json.dumps({"fetched_at": date.today().isoformat(), "source": "data.gov.in Agmarknet",
                               "records": records}, ensure_ascii=False, indent=1))
    print(f"Wrote {len(records)} rows to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
