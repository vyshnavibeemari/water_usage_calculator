import json
from datetime import date

import pytest

from core import analytics, calculator, exporters, importer, search, storage, validation

TODAY = date(2026, 11, 25)


def make(day="2026-11-20", label="A", people=2, **acts):
    clean, errors = validation.validate_entry(
        {"date": day, "label": label, "people": people, "activities": acts}, today=TODAY)
    assert not errors, errors
    return calculator.build_record(clean)


# ---- calculator
def test_estimate_basic():
    est = calculator.estimate(2, {"shower": 10})
    assert est["total_liters"] == 105          # 10*9.5 + 2*5 baseline
    assert est["per_person"] == 52.5


def test_coefficient_override():
    est = calculator.estimate(1, {"shower": 10}, {"coefficients": {"shower": 10}})
    assert est["total_liters"] == 105


@pytest.mark.parametrize("pp,expected", [(69.9, "Efficient"), (70, "Normal"), (100, "Normal"),
                                         (130, "High"), (130.1, "Critical")])
def test_classify_bands(pp, expected):
    assert calculator.classify(pp, 100) == expected


# ---- validation
def entry(**over):
    base = {"date": "2026-11-20", "label": "Home", "people": 3, "activities": {"shower": 10}}
    base.update(over)
    return validation.validate_entry(base, today=TODAY)


def test_valid_entry():
    clean, errors = entry()
    assert not errors and clean["people"] == 3 and clean["activities"]["toilet"] == 0


@pytest.mark.parametrize("over", [
    {"date": "2026-11-26"}, {"date": "nonsense"}, {"date": ""}, {"people": 0}, {"people": 21},
    {"people": 2.5}, {"people": ""}, {"people": "abc"}, {"people": float("nan")},
    {"activities": {"shower": -1}}, {"activities": {"shower": 9999}}, {"activities": {"shower": ""}},
    {"activities": {"shower": None}}, {"activities": {"shower": "x"}}, {"activities": {"shower": True}},
    {"label": "x" * 61}, {"notes": "x" * 201},
])
def test_invalid_entries_rejected(over):
    _, errors = entry(**over)
    assert errors


def test_multiple_errors_reported_together():
    _, errors = entry(date="2027-01-01", people=-1, activities={"shower": -5})
    assert len(errors) == 3


# ---- storage
def test_missing_file_creates_template(tmp_path):
    path = tmp_path / "records.json"
    records, warning = storage.load_records(path)
    assert records == [] and warning is None and path.exists()


def test_corrupt_file_is_backed_up(tmp_path):
    path = tmp_path / "records.json"
    path.write_text("{not json", encoding="utf-8")
    records, warning = storage.load_records(path)
    assert records == [] and "Backed up" in warning
    assert list(tmp_path.glob("records.corrupt.*.json"))
    assert json.loads(path.read_text())["records"] == []


def test_wrong_structure_recovers(tmp_path):
    path = tmp_path / "records.json"
    path.write_text('{"records": "oops"}', encoding="utf-8")
    assert storage.load_records(path)[0] == []


def test_roundtrip_and_malformed_rows_dropped(tmp_path):
    path = tmp_path / "records.json"
    rec = make()
    storage.save_records([rec], path)
    assert storage.load_records(path) == ([rec], None)
    payload = json.loads(path.read_text())
    payload["records"].append({"junk": 1})
    path.write_text(json.dumps(payload))
    records, warning = storage.load_records(path)
    assert len(records) == 1 and "1 malformed" in warning
    assert not list(tmp_path.glob("*.tmp"))


def test_settings_defaults_on_garbage(tmp_path):
    path = tmp_path / "s.json"
    path.write_text("???")
    assert storage.load_settings(path) == storage.default_settings()


# ---- importer
def test_import_reports_each_bad_row():
    text = ("date,label,people,shower,notes\n"
            "2026-01-05,Ok,2,10,fine\n"
            "2026-01-06,Neg,2,-1,\n"
            "2099-01-01,Future,2,5,\n"
            "2026-01-07,Blank,,5,\n")
    valid, errors = importer.import_csv_text(text)
    assert len(valid) == 1 and len(errors) == 3
    assert [e["row"] for e in errors] == [3, 4, 5]


def test_import_missing_required_column_and_empty():
    assert importer.import_csv_text("label,shower\nA,1\n")[0] == []
    assert importer.import_csv_text("")[1][0]["row"] == 0


def test_export_then_reimport_roundtrip():
    records = [make(day="2026-11-01", shower=10), make(day="2026-11-02", label="B", people=3, toilet=12)]
    valid, errors = importer.import_csv_text(exporters.to_csv(records))
    assert not errors and [r["total_liters"] for r in valid] == [r["total_liters"] for r in records]


# ---- analytics and search
def test_summary_and_trend():
    records = [make(day=f"2026-11-{d:02d}", shower=d) for d in range(1, 15)]
    s = analytics.summarize(records, 135)
    assert s["count"] == 14 and s["max_per_person"] > s["min_per_person"]
    assert s["trend"].startswith("Rising")
    assert analytics.summarize([], 135)["count"] == 0


def test_anomaly_detection():
    records = [make(day=f"2026-11-{d:02d}", shower=10) for d in range(1, 6)]
    spike = make(day="2026-11-10", shower=500)
    assert spike["id"] in analytics.find_anomalies(records + [spike])
    assert analytics.is_anomaly(spike, records)
    assert not analytics.is_anomaly(make(shower=10), records)


def test_moving_average_and_warnings():
    assert analytics.moving_average([1, 2, 3], 2) == [1, 1.5, 2.5]
    crit = make(day="2026-11-24", people=1, shower=200)
    kinds = [lvl for lvl, _ in analytics.build_warnings([crit], 135, today=TODAY)]
    assert "error" in kinds


def test_search_filters():
    records = [make(label="Sharma", shower=5, day="2026-11-01"),
               make(label="Rao", garden=30, day="2026-11-10")]
    assert len(search.filter_records(records, "sharma")) == 1
    assert len(search.filter_records(records, "garden")) == 1
    assert len(search.filter_records(records, activity="garden")) == 1
    assert len(search.filter_records(records, start=date(2026, 11, 5))) == 1
    assert search.filter_records(records, statuses=[]) == []
    assert search.sort_records(records)[0]["label"] == "Rao"


def test_exports_render():
    records = [make(shower=10)]
    assert "# Water Usage Report" in exporters.to_markdown(records, 135)
    assert "WATER USAGE AUDIT LOG" in exporters.to_text_audit(records, 135)
    assert "No records" in exporters.to_markdown([], 135)
