"""Markdown, plain-text audit log and CSV exports."""
from __future__ import annotations

import csv
import io
from datetime import datetime

from . import analytics
from .models import ACTIVITIES, BASELINE_KEY, BASELINE_LABEL, STATUSES

LABELS = {k: a.label for k, a in ACTIVITIES.items()} | {BASELINE_KEY: BASELINE_LABEL}


def _cell(text) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def to_csv(records: list[dict]) -> str:
    """Flat CSV that can be re-imported through the Bulk Import page."""
    fields = ["id", "date", "label", "people", *ACTIVITIES, "total_liters", "per_person", "status", "notes"]
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for r in sorted(records, key=lambda r: r["date"]):
        writer.writerow({**r, **(r.get("activities") or {})})
    return out.getvalue()


def to_markdown(records: list[dict], threshold: float) -> str:
    s = analytics.summarize(records, threshold)
    lines = ["# Water Usage Report", "",
             f"_Generated {datetime.now():%Y-%m-%d %H:%M}_", ""]
    if not records:
        return "\n".join(lines + ["No records available."])
    lines += ["## Summary", "", "| Metric | Value |", "|---|---|",
              f"| Period | {s['first_date']} to {s['last_date']} |",
              f"| Entries | {s['count']} |",
              f"| Total water | {s['total_liters']:,.0f} L |",
              f"| Average per entry | {s['avg_total']:,.0f} L |",
              f"| Average per person per day | {s['avg_per_person']} L |",
              f"| Range per person | {s['min_per_person']} to {s['max_per_person']} L |",
              f"| Daily limit | {threshold:g} L/person |",
              f"| Entries above limit (High + Critical) | {s['breaches']} |",
              f"| Anomalous entries | {s['anomalies']} |",
              f"| Trend | {s['trend']} |", "",
              "## Status distribution", "", "| Status | Entries |", "|---|---|"]
    lines += [f"| {st} | {s['status_counts'][st]} |" for st in STATUSES]
    totals = analytics.category_totals(records)
    grand = sum(totals.values()) or 1
    lines += ["", "## Usage by category", "", "| Category | Litres | Share |", "|---|---|---|"]
    lines += [f"| {LABELS.get(k, k)} | {v:,.0f} | {v / grand:.0%} |" for k, v in totals.items()]
    warnings = analytics.build_warnings(records, threshold)
    if warnings:
        lines += ["", "## Warnings", ""] + [f"- **{lvl.upper()}**: {msg}" for lvl, msg in warnings]
    lines += ["", "## Latest entries", "",
              "| Date | Household | People | Total (L) | L/person | Status | Notes |", "|---|---|---|---|---|---|---|"]
    for r in sorted(records, key=lambda r: r["date"], reverse=True)[:15]:
        lines.append(f"| {r['date']} | {_cell(r['label'])} | {r['people']} | {r['total_liters']:,.0f} | "
                     f"{r['per_person']} | {r['status']} | {_cell(r.get('notes', ''))} |")
    return "\n".join(lines) + "\n"


def to_text_audit(records: list[dict], threshold: float) -> str:
    s = analytics.summarize(records, threshold)
    lines = ["WATER USAGE AUDIT LOG", f"Generated: {datetime.now():%Y-%m-%d %H:%M:%S}",
             f"Records: {s['count']}   Daily limit: {threshold:g} L/person", "=" * 78]
    if records:
        lines += [f"Period: {s['first_date']} to {s['last_date']}",
                  f"Avg per person per day: {s['avg_per_person']} L   Trend: {s['trend']}",
                  "Status counts: " + ", ".join(f"{k}={v}" for k, v in s["status_counts"].items()),
                  "-" * 78]
        for lvl, msg in analytics.build_warnings(records, threshold):
            lines.append(f"[{lvl.upper()}] {msg}")
        flagged = analytics.find_anomalies(records)
        lines += ["-" * 78, f"{'DATE':<11}{'HOUSEHOLD':<20}{'PPL':>4}{'TOTAL L':>10}{'L/PERSON':>10}  {'STATUS':<9}FLAGS"]
        for r in sorted(records, key=lambda r: r["date"]):
            flag = "ANOMALY" if r["id"] in flagged else ""
            lines.append(f"{r['date']:<11}{r['label'][:19]:<20}{r['people']:>4}{r['total_liters']:>10.1f}"
                         f"{r['per_person']:>10.1f}  {r['status']:<9}{flag}")
    return "\n".join(lines) + "\n"
