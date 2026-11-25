"""JSON persistence with atomic writes and corruption recovery."""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

from .models import DEFAULT_THRESHOLD, SCHEMA_VERSION

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RECORDS_PATH = DATA_DIR / "records.json"
SETTINGS_PATH = DATA_DIR / "settings.json"
SAMPLE_PATH = DATA_DIR / "sample_data.json"
REQUIRED_KEYS = {"id", "date", "label", "people", "activities",
                 "total_liters", "per_person", "breakdown", "status"}


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def save_records(records: list[dict], path: Path | str = RECORDS_PATH) -> None:
    payload = {"schema_version": SCHEMA_VERSION,
               "saved_at": datetime.now().isoformat(timespec="seconds"),
               "records": records}
    _atomic_write(Path(path), json.dumps(payload, indent=2, ensure_ascii=False))


def _quarantine(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(f"{path.stem}.corrupt.{stamp}{path.suffix}")
    os.replace(path, backup)
    return backup


def _extract(payload) -> list | None:
    if isinstance(payload, dict):
        payload = payload.get("records")
    return payload if isinstance(payload, list) else None


def load_records(path: Path | str = RECORDS_PATH) -> tuple[list[dict], str | None]:
    """Load records. Never raises for missing or corrupt files.

    Returns (records, warning). A corrupt file is moved aside and replaced by a clean template.
    """
    path = Path(path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        save_records([], path)
        return [], None
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return _recover(path, "could not be read")

    items = _extract(payload)
    if items is None:
        return _recover(path, "had an unexpected structure")
    good = [r for r in items if isinstance(r, dict) and REQUIRED_KEYS <= r.keys()]
    dropped = len(items) - len(good)
    warning = f"Skipped {dropped} malformed record(s) while loading." if dropped else None
    return good, warning


def _recover(path: Path, reason: str) -> tuple[list[dict], str]:
    try:
        backup = _quarantine(path)
        note = f"Backed up as {backup.name}."
    except OSError:
        note = "The original could not be backed up."
    save_records([], path)
    return [], f"The data file {reason}. {note} A clean data file was created."


def load_sample(path: Path | str = SAMPLE_PATH) -> list[dict]:
    """Read-only load of the bundled sample dataset ([] if unavailable)."""
    try:
        items = _extract(json.loads(Path(path).read_text(encoding="utf-8"))) or []
    except (OSError, ValueError):
        return []
    return [r for r in items if isinstance(r, dict) and REQUIRED_KEYS <= r.keys()]


def default_settings() -> dict:
    return {"threshold": DEFAULT_THRESHOLD, "coefficients": {}}


def load_settings(path: Path | str = SETTINGS_PATH) -> dict:
    settings = default_settings()
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return settings
    if isinstance(data, dict):
        thr = data.get("threshold")
        if isinstance(thr, (int, float)) and not isinstance(thr, bool) and thr > 0:
            settings["threshold"] = float(thr)
        if isinstance(data.get("coefficients"), dict):
            settings["coefficients"] = data["coefficients"]
    return settings


def save_settings(settings: dict, path: Path | str = SETTINGS_PATH) -> None:
    _atomic_write(Path(path), json.dumps(settings, indent=2))
