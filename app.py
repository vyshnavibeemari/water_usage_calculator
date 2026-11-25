"""Water Usage Calculator - Streamlit app. Run with: streamlit run app.py"""
from __future__ import annotations

import math
from datetime import date, timedelta
from statistics import mean

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from core import analytics, calculator, charts, exporters, importer, search, storage, validation
from core.models import (ACTIVITIES, BASELINE_KEY, BASELINE_LABEL, DEFAULT_THRESHOLD,
                         MAX_PEOPLE, MIN_PEOPLE, STATUSES)

st.set_page_config(page_title="Water Usage Calculator", page_icon="💧", layout="wide")

STATUS_ICON = {"Efficient": "🟢", "Normal": "🔵", "High": "🟠", "Critical": "🔴"}
CATEGORY_LABELS = {k: a.label for k, a in ACTIVITIES.items()} | {BASELINE_KEY: BASELINE_LABEL}
ACTIVITY_BY_LABEL = {a.label: k for k, a in ACTIVITIES.items()}


# ---------------------------------------------------------------- state helpers
def init_state() -> None:
    if "records" in st.session_state:
        return
    records, warning = storage.load_records()
    st.session_state.records = records
    st.session_state.load_warning = warning
    st.session_state.settings = storage.load_settings()
    st.session_state.imported_files = set()


def persist() -> None:
    storage.save_records(st.session_state.records)


def threshold() -> float:
    return calculator.threshold_from(st.session_state.settings)


def flash(message: str) -> None:
    st.session_state.flash = message


def show_fig(fig) -> None:
    st.pyplot(fig)
    plt.close(fig)


def render_warnings() -> None:
    for level, message in analytics.build_warnings(st.session_state.records, threshold()):
        {"error": st.error, "warning": st.warning}.get(level, st.info)(message, icon="⚠️")


def records_df(records: list[dict]) -> pd.DataFrame:
    return pd.DataFrame([{
        "Date": r["date"], "Household": r["label"], "People": r["people"],
        "Total (L)": r["total_liters"], "L/person": r["per_person"],
        "Status": f"{STATUS_ICON.get(r['status'], '')} {r['status']}".strip(),
        "Notes": r.get("notes", ""),
    } for r in records])


# ------------------------------------------------------------------------ pages
def page_home() -> None:
    st.title("💧 Water Usage Calculator")
    st.caption("Estimate household water use from simple daily activity inputs, track it, and spot waste.")
    if st.session_state.load_warning:
        st.warning(st.session_state.load_warning)

    records = st.session_state.records
    if not records:
        st.info("No records yet. Add an entry from the sidebar, or load the bundled sample dataset.")
        if st.button("Load sample data"):
            sample = storage.load_sample()
            if sample:
                st.session_state.records = sample
                persist()
                flash(f"Loaded {len(sample)} sample entries.")
                st.rerun()
            else:
                st.error("Sample file data/sample_data.json was not found. Run scripts/generate_sample_data.py.")
        return

    today = date.today()
    today_total = sum(r["total_liters"] for r in records if r["date"] == today.isoformat())
    last7 = [r for r in records if r["date"] >= (today - timedelta(days=6)).isoformat()]
    latest = max(records, key=lambda r: r["date"])
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Today's total", f"{today_total:,.0f} L")
    c2.metric("7-day avg / person", f"{mean(r['per_person'] for r in last7):.0f} L" if last7 else "-")
    c3.metric("Entries", len(records))
    c4.metric("Latest status", f"{STATUS_ICON.get(latest['status'], '')} {latest['status']}")

    render_warnings()
    st.subheader("Latest entries")
    st.dataframe(records_df(search.sort_records(records)[:5]), hide_index=True, use_container_width=True)


def page_add_entry() -> None:
    st.title("➕ Add Entry")
    st.caption("Enter the household's total for the day. Cooking and drinking (5 L per person) is added automatically.")
    settings, thr = st.session_state.settings, threshold()

    c1, c2, c3 = st.columns([1, 2, 1])
    entry_date = c1.date_input("Date", value=date.today(), max_value=date.today())
    label = c2.text_input("Household label", value="My household", max_chars=60)
    people = c3.number_input("People", min_value=MIN_PEOPLE, max_value=MAX_PEOPLE, value=4, step=1)

    st.subheader("Daily activities")
    cols = st.columns(2)
    activities = {}
    for i, (key, act) in enumerate(ACTIVITIES.items()):
        activities[key] = cols[i % 2].number_input(
            f"{act.label} ({act.unit})", min_value=0.0, max_value=float(act.max_value),
            value=0.0, step=1.0, key=f"act_{key}")
    notes = st.text_area("Notes (optional)", max_chars=200, height=70)

    clean, errors = validation.validate_entry(
        {"date": entry_date, "label": label, "people": people, "activities": activities, "notes": notes})

    st.subheader("Live estimate")
    if errors:
        for err in errors:
            st.error(err)
    else:
        candidate = calculator.build_record(clean, settings)
        m1, m2, m3 = st.columns(3)
        m1.metric("Household total", f"{candidate['total_liters']:,.0f} L")
        m2.metric("Per person", f"{candidate['per_person']:.0f} L", f"limit {thr:g} L", delta_color="off")
        m3.metric("Status", f"{STATUS_ICON[candidate['status']]} {candidate['status']}")
        breakdown = pd.DataFrame({"Litres": {CATEGORY_LABELS[k]: v for k, v in candidate["breakdown"].items() if v > 0}})
        st.bar_chart(breakdown)
        if candidate["status"] in ("High", "Critical"):
            st.warning(f"This is {candidate['per_person'] / thr:.0%} of the daily limit per person.")
        if analytics.is_anomaly(candidate, st.session_state.records):
            st.warning("Anomaly: this total is more than 3x this household's usual usage. Check the numbers before saving.")

    if st.button("💾 Save entry", type="primary", disabled=bool(errors)):
        st.session_state.records.append(candidate)
        persist()
        st.success(f"Saved entry for {candidate['label']} on {candidate['date']}.")


def page_records() -> None:
    st.title("📋 Records")
    records = st.session_state.records
    if not records:
        st.info("No records yet.")
        return

    query = st.text_input("Search keyword", placeholder="household, note, date, status or activity")
    c1, c2, c3 = st.columns(3)
    statuses = c1.multiselect("Status", STATUSES, default=list(STATUSES))
    activity_label = c2.selectbox("Activity used", ["Any"] + list(ACTIVITY_BY_LABEL))
    sort_mode = c3.selectbox("Sort by", search.SORT_MODES)
    all_dates = [date.fromisoformat(r["date"]) for r in records]
    picked = st.date_input("Date range", value=(min(all_dates), max(all_dates)))
    start, end = (picked[0], picked[-1]) if isinstance(picked, (tuple, list)) and picked else (None, None)

    found = search.filter_records(records, query, statuses, ACTIVITY_BY_LABEL.get(activity_label), start, end)
    found = search.sort_records(found, sort_mode)
    st.caption(f"{len(found)} of {len(records)} records match.")

    size = st.selectbox("Rows per page", [10, 25, 50], index=0)
    pages = max(1, math.ceil(len(found) / size))
    page = st.number_input("Page", min_value=1, max_value=pages, value=1, step=1) if pages > 1 else 1
    window = found[(page - 1) * size: page * size]
    st.dataframe(records_df(window), hide_index=True, use_container_width=True)
    if pages > 1:
        st.caption(f"Page {page} of {pages}")

    with st.expander("Delete a record"):
        if window:
            options = {f"{r['date']} - {r['label']} ({r['total_liters']:,.0f} L) [{r['id']}]": r["id"] for r in window}
            choice = st.selectbox("Record on this page", list(options))
            confirm = st.checkbox("I understand this cannot be undone")
            if st.button("Delete record", disabled=not confirm):
                st.session_state.records = [r for r in st.session_state.records if r["id"] != options[choice]]
                persist()
                flash("Record deleted.")
                st.rerun()
        else:
            st.write("Nothing to delete on this page.")


def page_analytics() -> None:
    st.title("📊 Analytics")
    records, thr = st.session_state.records, threshold()
    if not records:
        st.info("Add some entries to see analytics.")
        return
    render_warnings()
    s = analytics.summarize(records, thr)
    a1, a2, a3, a4 = st.columns(4)
    a1.metric("Entries", s["count"])
    a2.metric("Avg / person / day", f"{s['avg_per_person']} L")
    a3.metric("Avg household total", f"{s['avg_total']:,.0f} L")
    a4.metric("Peak / person", f"{s['max_per_person']} L")
    b1, b2, b3, b4 = st.columns(4)
    b1.metric("Total water", f"{s['total_liters']:,.0f} L")
    b2.metric("Lowest / person", f"{s['min_per_person']} L")
    b3.metric("Over limit / anomalies", f"{s['breaches']} / {s['anomalies']}")
    b4.metric("Trend", s["trend"])

    show_fig(charts.trend_chart(analytics.daily_series(records), thr))
    left, right = st.columns([3, 2])
    totals = analytics.category_totals(records)
    with left:
        show_fig(charts.category_chart(totals))
    with right:
        show_fig(charts.status_chart(s["status_counts"]))

    grand = sum(totals.values()) or 1
    st.subheader("Usage by category")
    st.dataframe(pd.DataFrame([{"Category": CATEGORY_LABELS.get(k, k), "Litres": round(v), "Share": f"{v / grand:.0%}"}
                               for k, v in totals.items()]), hide_index=True, use_container_width=True)


def page_export() -> None:
    st.title("📤 Export")
    records, thr = st.session_state.records, threshold()
    if not records:
        st.info("Nothing to export yet.")
        return
    stamp = date.today().isoformat()
    c1, c2, c3 = st.columns(3)
    c1.download_button("⬇️ Markdown report", exporters.to_markdown(records, thr),
                       f"water_report_{stamp}.md", "text/markdown", use_container_width=True)
    c2.download_button("⬇️ Text audit log", exporters.to_text_audit(records, thr),
                       f"water_audit_{stamp}.txt", "text/plain", use_container_width=True)
    c3.download_button("⬇️ CSV records", exporters.to_csv(records),
                       f"water_records_{stamp}.csv", "text/csv", use_container_width=True)
    d1, d2 = st.columns(2)
    d1.download_button("🖼️ Trend chart (PNG)",
                       charts.fig_to_png(charts.trend_chart(analytics.daily_series(records), thr)),
                       f"water_trend_{stamp}.png", "image/png", use_container_width=True)
    d2.download_button("🖼️ Category chart (PNG)",
                       charts.fig_to_png(charts.category_chart(analytics.category_totals(records))),
                       f"water_categories_{stamp}.png", "image/png", use_container_width=True)
    with st.expander("Preview Markdown report"):
        st.markdown(exporters.to_markdown(records, thr))


def page_import() -> None:
    st.title("📥 Bulk Import")
    st.caption("Upload a CSV with columns: date, people, label, notes and any of "
               + ", ".join(ACTIVITIES) + ". Blank activity cells count as 0.")
    sample_csv = storage.DATA_DIR / "sample_data.csv"
    bad_csv = storage.DATA_DIR / "bad_import.csv"
    cols = st.columns(2)
    for col, path, label in ((cols[0], sample_csv, "Download sample CSV"), (cols[1], bad_csv, "Download CSV with deliberate errors")):
        if path.exists():
            col.download_button(label, path.read_bytes(), path.name, "text/csv", use_container_width=True)

    upload = st.file_uploader("Choose a CSV file", type=["csv"])
    if not upload:
        return
    signature = (upload.name, upload.size)
    valid, errors = importer.import_csv_text(upload.getvalue().decode("utf-8-sig", errors="replace"),
                                             st.session_state.settings)
    m1, m2 = st.columns(2)
    m1.metric("Valid rows", len(valid))
    m2.metric("Rejected rows", len(errors))
    if errors:
        st.subheader("Error log")
        err_df = pd.DataFrame(errors).rename(columns={"row": "Line", "errors": "Problem"})
        st.dataframe(err_df, hide_index=True, use_container_width=True)
        st.download_button("Download error log (CSV)", err_df.to_csv(index=False), "import_errors.csv", "text/csv")
    if valid:
        st.subheader("Rows that will be imported")
        st.dataframe(records_df(valid), hide_index=True, use_container_width=True)
        if signature in st.session_state.imported_files:
            st.success("This file has already been imported in this session.")
        elif st.button(f"Import {len(valid)} valid row(s)", type="primary"):
            st.session_state.records.extend(valid)
            persist()
            st.session_state.imported_files.add(signature)
            flash(f"Imported {len(valid)} row(s); {len(errors)} rejected.")
            st.rerun()


def page_settings() -> None:
    st.title("⚙️ Settings")
    settings = st.session_state.settings
    thr = st.number_input("Daily limit (litres per person per day)", min_value=20.0, max_value=1000.0,
                          value=threshold(), step=5.0)
    st.caption(f"Status bands: Efficient below {0.7 * thr:.0f} L, Normal up to {thr:.0f} L, "
               f"High up to {1.3 * thr:.0f} L, Critical above that.")
    st.subheader("Water coefficients")
    current = calculator.coefficients(settings)
    new_coeffs, cols = {}, st.columns(2)
    for i, (key, act) in enumerate(ACTIVITIES.items()):
        new_coeffs[key] = cols[i % 2].number_input(f"{act.label} (litres per {act.per})", min_value=0.0,
                                                   max_value=1000.0, value=float(current[key]), step=0.5, key=f"coef_{key}")
    b1, b2, b3 = st.columns(3)
    if b1.button("Save settings", type="primary"):
        st.session_state.settings = {"threshold": float(thr), "coefficients": new_coeffs}
        storage.save_settings(st.session_state.settings)
        flash("Settings saved. Use 'Recalculate all records' to apply them to existing entries.")
        st.rerun()
    if b2.button("Recalculate all records"):
        st.session_state.records = [calculator.recompute(r, settings) for r in st.session_state.records]
        persist()
        flash(f"Recalculated {len(st.session_state.records)} record(s) with the saved settings.")
        st.rerun()
    if b3.button("Reset to defaults"):
        st.session_state.settings = storage.default_settings()
        storage.save_settings(st.session_state.settings)
        for key in ACTIVITIES:
            st.session_state.pop(f"coef_{key}", None)
        flash("Settings reset to defaults.")
        st.rerun()


PAGES = {
    "🏠 Home": page_home,
    "➕ Add Entry": page_add_entry,
    "📋 Records": page_records,
    "📊 Analytics": page_analytics,
    "📤 Export": page_export,
    "📥 Bulk Import": page_import,
    "⚙️ Settings": page_settings,
}


def main() -> None:
    init_state()
    st.sidebar.title("💧 Water Usage")
    st.sidebar.caption(f"{len(st.session_state.records)} record(s) saved")
    choice = st.sidebar.radio("Navigate", list(PAGES), label_visibility="collapsed")
    message = st.session_state.pop("flash", None)
    if message:
        st.success(message)
    PAGES[choice]()


main()
