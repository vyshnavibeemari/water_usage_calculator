"""Generate data/sample_data.csv, sample_data.json and bad_import.csv (deterministic).

Usage: python scripts/generate_sample_data.py   (dates are relative to today)
"""
import random
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import calculator, exporters, storage  # noqa: E402
from core.models import ACTIVITIES  # noqa: E402

HOUSEHOLDS = [("Sharma family", 4), ("Rao household", 2), ("Student flat", 3), ("Joint family", 7), ("Green villa", 5)]


def typical(rng, people):
    scale = rng.uniform(0.6, 1.5)
    washes = rng.choice([0, 0, 1, 1, 2]) if people < 5 else rng.choice([1, 2, 2, 3])

    def per_person(lo, hi):
        return people * rng.uniform(lo, hi) * scale

    acts = {
        "shower": per_person(2.5, 5), "toilet": per_person(3, 5), "tap": per_person(1, 3),
        "dishwasher": rng.choice([0, 0, 1, 1, 2]), "handwash": per_person(0, 3),
        "washer": washes, "garden": rng.choice([0, 0, 0, 0, 0, 10, 15]),
        "carwash": rng.choice([0] * 9 + [1]),
    }
    return {k: min(round(v), ACTIVITIES[k].max_value) for k, v in acts.items()}


def build(day, label, people, acts, notes=""):
    full = {k: acts.get(k, 0) for k in ACTIVITIES}
    return calculator.build_record({"date": day.isoformat(), "label": label, "people": people,
                                    "activities": full, "notes": notes})


def main():
    rng = random.Random(44)
    today = date.today()
    day = lambda n: today - timedelta(days=n)  # noqa: E731
    maxed = {k: a.max_value for k, a in ACTIVITIES.items()}

    records = [
        build(day(2), "Student flat", 1, {}, "Boundary: minimum usage (1 person, no activities)"),
        build(day(5), "Hostel block", 20, {"shower": 100, "toilet": 90, "tap": 80, "washer": 6}, "Boundary: maximum household size"),
        build(day(9), "Hostel block", 20, maxed, "Boundary: every activity at its daily cap"),
        build(day(12), "Sharma family", 4, {}, "Edge: away on holiday, only baseline use"),
        build(day(7), "Rao household", 2, {"shower": 14, "toilet": 10, "garden": 240, "carwash": 3}, "Edge: garden and car wash weekend"),
        build(day(3), "Sharma family", 4, {"shower": 24, "toilet": 200, "tap": 10, "washer": 1}, "Edge: suspected running toilet / leak"),
        build(day(14), "Green villa", 5, {"shower": 12, "toilet": 15, "tap": 5, "handwash": 5}, "Efficient: conscious water saving"),
        build(day(1), "Joint family", 7, {"shower": 40, "toilet": 40, "tap": 15, "dishwasher": 1, "handwash": 15, "washer": 2}, "Normal day"),
    ]
    for _ in range(34):
        label, people = rng.choice(HOUSEHOLDS)
        records.append(build(day(rng.randint(0, 29)), label, people, typical(rng, people)))
    for i, rec in enumerate(sorted(records, key=lambda r: r["date"]), start=1):
        rec["id"] = f"s{i:03d}"
    records.sort(key=lambda r: r["id"])

    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "sample_data.csv").write_text(exporters.to_csv(records), encoding="utf-8")
    storage.save_records(records, ROOT / "data" / "sample_data.json")

    d = lambda n: (today - timedelta(days=n)).isoformat()  # noqa: E731
    header = "date,label,people," + ",".join(ACTIVITIES) + ",notes"
    rows = [
        f"{d(1)},Sharma family,4,20,16,10,1,5,1,0,0,Valid row",
        f"{d(2)},Rao household,2,-5,8,4,0,3,1,0,0,Negative shower minutes",
        f"{d(3)},Student flat,,10,8,4,0,3,1,0,0,Blank people",
        f"{(today + timedelta(days=5)).isoformat()},Green villa,5,30,25,12,1,10,2,0,0,Future date",
        "2026-13-45,Rao household,2,10,8,4,0,3,1,0,0,Impossible date",
        f"{d(4)},Joint family,25,50,40,20,1,10,2,0,0,People above maximum",
        f"{d(5)},Green villa,5,abc,25,12,1,10,2,0,0,Non-numeric shower",
        f"{d(6)},Rao household,2,9999,8,4,0,3,1,0,0,Shower above daily cap",
        f"{d(7)},Rao household,2.5,10,8,4,0,3,1,0,0,Fractional people",
        f"{d(8)},Student flat,3,12,9,5,0,4,1,0,0,Valid row",
        f"{d(9)},Green villa,5,30,25,12,1,10,2,15,0,Valid row",
    ]
    (ROOT / "data" / "bad_import.csv").write_text("\n".join([header] + rows) + "\n", encoding="utf-8")
    print(f"Wrote {len(records)} sample records and {len(rows)} import test rows to {ROOT / 'data'}")


if __name__ == "__main__":
    main()
