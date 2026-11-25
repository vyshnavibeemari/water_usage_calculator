"""Keyword / category filtering and sorting of stored records."""
from __future__ import annotations

from datetime import date

from .models import ACTIVITIES

SORT_MODES = ("Newest first", "Oldest first", "Highest L/person", "Lowest L/person")


def filter_records(records: list[dict], query: str = "", statuses=None,
                   activity: str | None = None, start: date | None = None,
                   end: date | None = None) -> list[dict]:
    tokens = query.lower().split()
    out = []
    for r in records:
        if statuses is not None and r["status"] not in statuses:
            continue
        if activity and (r.get("activities") or {}).get(activity, 0) <= 0:
            continue
        if start and r["date"] < start.isoformat():
            continue
        if end and r["date"] > end.isoformat():
            continue
        if tokens:
            used = " ".join(ACTIVITIES[k].label for k, v in (r.get("activities") or {}).items()
                            if k in ACTIVITIES and v > 0)
            haystack = f"{r['label']} {r.get('notes', '')} {r['date']} {r['status']} {used}".lower()
            if not all(t in haystack for t in tokens):
                continue
        out.append(r)
    return out


def sort_records(records: list[dict], mode: str = "Newest first") -> list[dict]:
    if mode == "Oldest first":
        return sorted(records, key=lambda r: r["date"])
    if mode == "Highest L/person":
        return sorted(records, key=lambda r: r["per_person"], reverse=True)
    if mode == "Lowest L/person":
        return sorted(records, key=lambda r: r["per_person"])
    return sorted(records, key=lambda r: r["date"], reverse=True)
