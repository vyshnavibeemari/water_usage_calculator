"""Water-use estimation engine: total = sum(quantity x coefficient) + baseline."""
from __future__ import annotations

import uuid

from .models import (ACTIVITIES, BASELINE_KEY, BASELINE_L_PER_PERSON, DEFAULT_THRESHOLD,
                     STATUS_BANDS, UsageRecord)


def coefficients(settings: dict | None = None) -> dict[str, float]:
    """Default litres-per-unit table, with any valid overrides from settings applied."""
    coeffs = {k: a.coefficient for k, a in ACTIVITIES.items()}
    for key, val in ((settings or {}).get("coefficients") or {}).items():
        if key in coeffs and isinstance(val, (int, float)) and not isinstance(val, bool) and val >= 0:
            coeffs[key] = float(val)
    return coeffs


def threshold_from(settings: dict | None = None) -> float:
    val = (settings or {}).get("threshold", DEFAULT_THRESHOLD)
    return float(val) if isinstance(val, (int, float)) and val > 0 else DEFAULT_THRESHOLD


def classify(per_person: float, threshold: float = DEFAULT_THRESHOLD) -> str:
    ratio = per_person / threshold
    low, mid, high = STATUS_BANDS
    if ratio < low:
        return "Efficient"
    if ratio <= mid:
        return "Normal"
    if ratio <= high:
        return "High"
    return "Critical"


def estimate(people: int, activities: dict, settings: dict | None = None) -> dict:
    """Return litres per category, household total and per-person figure."""
    coeffs = coefficients(settings)
    breakdown = {k: round(float(activities.get(k, 0) or 0) * coeffs[k], 2) for k in ACTIVITIES}
    breakdown[BASELINE_KEY] = round(people * BASELINE_L_PER_PERSON, 2)
    total = round(sum(breakdown.values()), 2)
    return {"breakdown": breakdown, "total_liters": total, "per_person": round(total / people, 2)}


def build_record(clean: dict, settings: dict | None = None, record_id: str | None = None) -> dict:
    """Turn a validated entry into a storable record dict."""
    people = int(clean["people"])
    acts = {k: (clean.get("activities") or {}).get(k, 0) for k in ACTIVITIES}
    est = estimate(people, acts, settings)
    return UsageRecord(
        id=record_id or uuid.uuid4().hex[:8],
        date=clean["date"],
        label=clean.get("label") or "My household",
        people=people,
        activities=acts,
        total_liters=est["total_liters"],
        per_person=est["per_person"],
        breakdown=est["breakdown"],
        status=classify(est["per_person"], threshold_from(settings)),
        notes=clean.get("notes", "") or "",
    ).to_dict()


def recompute(record: dict, settings: dict | None = None) -> dict:
    """Recalculate a stored record (e.g. after coefficients or threshold change)."""
    return build_record(record, settings, record_id=record["id"])
