"""Bulk CSV import with row-by-row error reporting."""
from __future__ import annotations

import csv
import io

from . import calculator, validation
from .models import ACTIVITIES

MAX_ROWS = 5000
REQUIRED_COLUMNS = ("date", "people")


def import_csv_text(text: str, settings: dict | None = None) -> tuple[list[dict], list[dict]]:
    """Parse CSV text. Returns (valid_records, errors); errors are {"row", "errors"} dicts.

    Blank activity cells count as 0. Required columns: date, people.
    Optional: label, notes and one column per activity key.
    """
    valid: list[dict] = []
    errors: list[dict] = []
    try:
        reader = csv.DictReader(io.StringIO(text))
        fields = reader.fieldnames
    except csv.Error as exc:
        return [], [{"row": 0, "errors": f"Not a readable CSV file: {exc}"}]
    if not fields:
        return [], [{"row": 0, "errors": "File is empty or has no header row."}]

    headers = {h.strip().lower() for h in fields if h}
    missing = [c for c in REQUIRED_COLUMNS if c not in headers]
    if missing:
        return [], [{"row": 1, "errors": f"Missing required column(s): {', '.join(missing)}."}]

    try:
        for count, row in enumerate(reader, start=1):
            if count > MAX_ROWS:
                errors.append({"row": reader.line_num, "errors": f"Row limit of {MAX_ROWS} exceeded; remaining rows skipped."})
                break
            cells = {k.strip().lower(): ("" if v is None else str(v))
                     for k, v in row.items() if k is not None}
            raw = {
                "date": cells.get("date"),
                "label": cells.get("label"),
                "people": cells.get("people"),
                "notes": cells.get("notes"),
                "activities": {k: cells.get(k, "").strip() or "0" for k in ACTIVITIES},
            }
            clean, errs = validation.validate_entry(raw)
            if errs:
                errors.append({"row": reader.line_num, "errors": "; ".join(errs)})
            else:
                valid.append(calculator.build_record(clean, settings))
    except csv.Error as exc:
        errors.append({"row": reader.line_num, "errors": f"CSV parsing stopped: {exc}"})
    return valid, errors
