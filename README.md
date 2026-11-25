# 💧 Water Usage Calculator

DataSpark Challenge, Project #44 (Environment & Sustainability). A Streamlit app that estimates household
water use from simple daily activity inputs, validates every entry, saves records to JSON, and reports
totals, trends and warnings.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python scripts/generate_sample_data.py   # optional: regenerates the sample files with fresh dates
streamlit run app.py
```

On an empty install, the Home page offers a **Load sample data** button (42 entries).

## Features

| Brief requirement | Where |
|---|---|
| Interactive interface | Sidebar navigation, Streamlit forms (`app.py`) |
| Defensive validation | `core/validation.py`, repeated at widget level and on import |
| Calculation engine | `core/calculator.py` (coefficient table in `core/models.py`) |
| JSON persistence | `core/storage.py` (atomic writes, corrupt-file backup, schema version) |
| Search and filter | Records page: keyword, status, activity, date range, sort, pagination |
| Summary generation | Analytics page and `core/analytics.py` |
| Matplotlib plots | `core/charts.py` (trend, category, status) |
| Markdown / TXT / CSV export | Export page, `core/exporters.py` |
| Threshold warnings | Banners on Home and Analytics, `analytics.build_warnings` |
| Bulk CSV import with error log | Bulk Import page, `core/importer.py` |

## How the estimate works

Quantities are the **household total for the day**. `litres = sum(quantity x coefficient) + 5 L x people`
(cooking and drinking). Status compares litres per person with a daily limit (default 135 L):

| Status | Per-person use |
|---|---|
| Efficient | below 70% of the limit |
| Normal | up to 100% |
| High | up to 130% |
| Critical | above 130% |

The limit and every coefficient can be changed on the Settings page. Coefficients are typical planning
estimates, so tune them to your region and cite your source in the demo.

An entry is flagged as an **anomaly** if its total is more than 3x the average of that household's other
entries (needs at least 3 earlier entries for the household).

## Data files

- `data/records.json` live store, created on first run (git-ignored)
- `data/settings.json` limit and coefficient overrides (git-ignored)
- `data/sample_data.csv` / `.json` 42 seeded entries: normal days, boundary values (1 and 20 people, every activity at its cap, zero activity) and edge cases (suspected leak, garden and car-wash spike)
- `data/bad_import.csv` 11 rows, 3 valid and 8 deliberately invalid, to demo the row-by-row error log

If `records.json` is corrupt, it is renamed to `records.corrupt.<timestamp>.json` and a clean file is created.

## Tests

```bash
pytest
```

Covers the calculator, validation, storage recovery, importer, search, analytics and exports.

## Demo script

1. Launch the app and show Home.
2. Click **Load sample data** and show the warnings banner.
3. Add Entry: try a future date and watch the error appear and Save stay disabled, then fix it and save.
4. Analytics: show the metrics, trend chart and category chart.
5. Stop the server and relaunch: the records are still there.
6. Bulk Import: upload `bad_import.csv`, show the error log, then import the valid rows.
7. Export the Markdown report and the trend chart PNG.

## Project layout

```
app.py              Streamlit UI (pages only, no business logic)
core/               models, calculator, validation, storage, importer, search, analytics, charts, exporters
scripts/            sample data generator
tests/              pytest suite
data/               sample datasets (+ live records at runtime)
```
