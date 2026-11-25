"""Aggregations, trends, anomaly detection and warning flags."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta
from statistics import mean

from .models import STATUSES

ANOMALY_FACTOR = 3.0
ANOMALY_MIN_HISTORY = 3


def category_totals(records: list[dict]) -> dict[str, float]:
    totals: dict[str, float] = defaultdict(float)
    for r in records:
        for key, litres in (r.get("breakdown") or {}).items():
            totals[key] += litres
    return dict(sorted(((k, round(v, 2)) for k, v in totals.items()), key=lambda kv: -kv[1]))


def daily_series(records: list[dict]) -> list[dict]:
    by_day: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        by_day[r["date"]].append(r)
    return [{"date": d,
             "avg_per_person": round(mean(x["per_person"] for x in rows), 2),
             "total_liters": round(sum(x["total_liters"] for x in rows), 2),
             "entries": len(rows)}
            for d, rows in sorted(by_day.items())]


def moving_average(values: list[float], window: int = 7) -> list[float]:
    out = []
    for i in range(len(values)):
        chunk = values[max(0, i - window + 1): i + 1]
        out.append(round(sum(chunk) / len(chunk), 2))
    return out


def _is_outlier(total: float, others: list[float]) -> bool:
    return len(others) >= ANOMALY_MIN_HISTORY and total > ANOMALY_FACTOR * mean(others)


def find_anomalies(records: list[dict]) -> set[str]:
    """IDs of entries whose total exceeds 3x the average of the same household's other entries."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        groups[r["label"].strip().lower()].append(r)
    flagged = set()
    for rows in groups.values():
        for r in rows:
            others = [x["total_liters"] for x in rows if x["id"] != r["id"]]
            if _is_outlier(r["total_liters"], others):
                flagged.add(r["id"])
    return flagged


def is_anomaly(candidate: dict, existing: list[dict]) -> bool:
    key = candidate["label"].strip().lower()
    others = [x["total_liters"] for x in existing if x["label"].strip().lower() == key]
    return _is_outlier(candidate["total_liters"], others)


def trend(series: list[dict]) -> str:
    vals = [s["avg_per_person"] for s in series]
    half = min(7, len(vals) // 2)
    if half < 2:
        return "Not enough data"
    recent, prev = vals[-half:], vals[-2 * half:-half]
    if not prev or mean(prev) == 0:
        return "Not enough data"
    change = (mean(recent) - mean(prev)) / mean(prev) * 100
    if change > 5:
        return f"Rising ▲ ({change:+.0f}%)"
    if change < -5:
        return f"Falling ▼ ({change:+.0f}%)"
    return f"Stable ({change:+.0f}%)"


def summarize(records: list[dict], threshold: float) -> dict:
    counts = Counter(r["status"] for r in records)
    base = {"count": len(records), "threshold": threshold,
            "status_counts": {s: counts.get(s, 0) for s in STATUSES},
            "breaches": counts.get("High", 0) + counts.get("Critical", 0)}
    if not records:
        return {**base, "total_liters": 0, "avg_total": 0, "avg_per_person": 0,
                "min_per_person": 0, "max_per_person": 0, "anomalies": 0,
                "first_date": None, "last_date": None, "trend": "Not enough data"}
    per_person = [r["per_person"] for r in records]
    totals = [r["total_liters"] for r in records]
    dates = [r["date"] for r in records]
    return {**base,
            "total_liters": round(sum(totals), 1),
            "avg_total": round(mean(totals), 1),
            "avg_per_person": round(mean(per_person), 1),
            "min_per_person": min(per_person),
            "max_per_person": max(per_person),
            "anomalies": len(find_anomalies(records)),
            "first_date": min(dates), "last_date": max(dates),
            "trend": trend(daily_series(records))}


def build_warnings(records: list[dict], threshold: float, today: date | None = None) -> list[tuple[str, str]]:
    """Console/UI warning flags as (level, message); level is error, warning or info."""
    today = today or date.today()
    cutoff = (today - timedelta(days=6)).isoformat()
    recent = [r for r in records if r["date"] >= cutoff]
    out: list[tuple[str, str]] = []

    critical = [r for r in recent if r["status"] == "Critical"]
    if critical:
        n = len(critical)
        out.append(("error", f"{n} Critical {'entry' if n == 1 else 'entries'} in the last 7 days "
                             f"(more than 130% of the {threshold:g} L/person/day limit)."))
    if recent:
        avg = mean(r["per_person"] for r in recent)
        if avg > threshold:
            out.append(("warning", f"7-day average is {avg:.0f} L/person/day, above the {threshold:g} L limit."))
    flagged = find_anomalies(records)
    if flagged:
        latest = sorted((r for r in records if r["id"] in flagged), key=lambda r: r["date"], reverse=True)[:3]
        names = ", ".join(f"{r['label']} ({r['date']})" for r in latest)
        out.append(("warning", f"{len(flagged)} anomalous {'entry' if len(flagged) == 1 else 'entries'} "
                               f"(over 3x the household's usual total). Latest: {names}."))
    return out
