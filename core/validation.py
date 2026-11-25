"""Centralised input validation. Used by the UI, the importer and the tests."""
from __future__ import annotations

import math
from datetime import date, datetime

from .models import ACTIVITIES, MAX_LABEL_LEN, MAX_NOTES_LEN, MAX_PEOPLE, MIN_PEOPLE

EARLIEST_DATE = date(2000, 1, 1)
DEFAULT_LABEL = "My household"


def parse_number(value) -> float:
    """Convert to a finite float or raise ValueError with a short reason."""
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ValueError("is blank")
    if isinstance(value, bool):
        raise ValueError("must be a number")
    try:
        num = float(value.strip() if isinstance(value, str) else value)
    except (TypeError, ValueError):
        raise ValueError("must be a number") from None
    if not math.isfinite(num):
        raise ValueError("must be a finite number")
    return num


def _parse_date(value, today: date) -> tuple[str | None, str | None]:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None, "Date is required."
    try:
        if isinstance(value, datetime):
            parsed = value.date()
        elif isinstance(value, date):
            parsed = value
        else:
            parsed = date.fromisoformat(str(value).strip())
    except ValueError:
        return None, "Date must be a real date in YYYY-MM-DD format."
    if parsed > today:
        return None, "Date cannot be in the future."
    if parsed < EARLIEST_DATE:
        return None, f"Date cannot be before {EARLIEST_DATE.isoformat()}."
    return parsed.isoformat(), None


def validate_entry(raw: dict, today: date | None = None) -> tuple[dict, list[str]]:
    """Validate and normalise one entry. Returns (clean_entry, error_messages)."""
    today = today or date.today()
    errors: list[str] = []
    clean: dict = {}

    clean["date"], err = _parse_date(raw.get("date"), today)
    if err:
        errors.append(err)

    try:
        people = parse_number(raw.get("people"))
        if people != int(people):
            raise ValueError("must be a whole number")
        if not MIN_PEOPLE <= people <= MAX_PEOPLE:
            raise ValueError(f"must be between {MIN_PEOPLE} and {MAX_PEOPLE}")
        clean["people"] = int(people)
    except ValueError as exc:
        errors.append(f"Number of people {exc}.")

    acts_raw = raw.get("activities") or {}
    clean["activities"] = {}
    for key, act in ACTIVITIES.items():
        if key not in acts_raw:
            clean["activities"][key] = 0
            continue
        try:
            qty = parse_number(acts_raw[key])
            if qty < 0:
                raise ValueError("cannot be negative")
            if qty > act.max_value:
                raise ValueError(f"cannot exceed {act.max_value:g} {act.unit} per day")
            clean["activities"][key] = int(qty) if qty == int(qty) else round(qty, 2)
        except ValueError as exc:
            errors.append(f"{act.label} ({act.unit}) {exc}.")

    label = str(raw.get("label") or "").strip() or DEFAULT_LABEL
    if len(label) > MAX_LABEL_LEN:
        errors.append(f"Household label is too long (max {MAX_LABEL_LEN} characters).")
    clean["label"] = label

    notes = str(raw.get("notes") or "").strip()
    if len(notes) > MAX_NOTES_LEN:
        errors.append(f"Notes are too long (max {MAX_NOTES_LEN} characters).")
    clean["notes"] = notes

    return clean, errors
