"""Seeded fake sales data for the OQ-1 chart-library prototype.

Deterministic: same seed -> same 500 rows. Stand-in for datbox-fake.
"""
import json
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 42
N = 500
REGIONS = ["West", "Central", "East", "Canada"]
REGION_W = [0.35, 0.25, 0.30, 0.10]
LINES = {"Hardware": (900, 2400), "Software": (150, 600), "Services": (400, 1600)}
LINE_W = [0.3, 0.45, 0.25]
REPS = ["A. Okafor", "B. Lindqvist", "C. Nakamura", "D. Reyes",
        "E. Marchetti", "F. Dubois", "G. Patel", "H. Kowalski"]
START = date(2025, 10, 1)
DAYS = 365


def main(out: Path) -> None:
    rng = random.Random(SEED)
    rows = []
    for i in range(1, N + 1):
        d = START + timedelta(days=rng.randrange(DAYS))
        # mild seasonality: Q4 and late fiscal year are busier
        month_boost = 1.0 + 0.25 * (d.month in (11, 12, 3, 6))
        region = rng.choices(REGIONS, REGION_W)[0]
        line = rng.choices(list(LINES), LINE_W)[0]
        lo, hi = LINES[line]
        units = max(1, int(rng.lognormvariate(1.1, 0.6)))
        unit_price = round(rng.uniform(lo, hi) * month_boost, 2)
        rows.append({
            "order_id": f"SO-{10000 + i}",
            "order_date": d.isoformat(),
            "month": d.strftime("%Y-%m"),
            "region": region,
            "product_line": line,
            "rep": rng.choice(REPS),
            "units": units,
            "unit_price": unit_price,
            "revenue": round(units * unit_price, 2),
        })
    rows.sort(key=lambda r: r["order_date"])
    out.write_text(json.dumps(rows, separators=(",", ":")))
    print(f"wrote {len(rows)} rows -> {out} ({out.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main(Path(__file__).with_name("sales.json"))
