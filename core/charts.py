"""Matplotlib figures. Callers must close figures (fig_to_png does it automatically)."""
from __future__ import annotations

from io import BytesIO

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from .analytics import moving_average  # noqa: E402
from .models import ACTIVITIES, BASELINE_KEY, BASELINE_LABEL, STATUSES  # noqa: E402

STATUS_COLORS = {"Efficient": "#2e9e6b", "Normal": "#3b82c4", "High": "#e8932f", "Critical": "#d64545"}
CATEGORY_LABELS = {k: a.label for k, a in ACTIVITIES.items()} | {BASELINE_KEY: BASELINE_LABEL}


def _empty(ax, message="No data yet") -> None:
    ax.text(0.5, 0.5, message, ha="center", va="center", transform=ax.transAxes, color="gray")
    ax.set_xticks([])
    ax.set_yticks([])


def trend_chart(series: list[dict], threshold: float, window: int = 7):
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.set_title("Daily water use per person")
    if not series:
        _empty(ax)
        return fig
    labels = [s["date"] for s in series]
    vals = [s["avg_per_person"] for s in series]
    x = list(range(len(vals)))
    ax.plot(x, vals, marker="o", color="#3b82c4", label="Avg L/person/day")
    ax.plot(x, moving_average(vals, window), linestyle="--", color="#2e9e6b", label=f"{window}-day moving avg")
    ax.axhline(threshold, color="#d64545", linestyle=":", label=f"Limit ({threshold:g} L)")
    step = max(1, len(x) // 10)
    ax.set_xticks(x[::step])
    ax.set_xticklabels(labels[::step], rotation=45, ha="right")
    ax.set_ylabel("Litres per person")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    return fig


def category_chart(totals: dict[str, float]):
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.set_title("Where the water goes (litres)")
    items = [(CATEGORY_LABELS.get(k, k), v) for k, v in totals.items() if v > 0]
    if not items:
        _empty(ax)
        return fig
    items.sort(key=lambda kv: kv[1])
    ax.barh([k for k, _ in items], [v for _, v in items], color="#3b82c4")
    ax.set_xlabel("Litres")
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    return fig


def status_chart(counts: dict[str, int]):
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.set_title("Status distribution")
    if not sum(counts.values()):
        _empty(ax)
        return fig
    ax.bar(STATUSES, [counts.get(s, 0) for s in STATUSES], color=[STATUS_COLORS[s] for s in STATUSES])
    ax.set_ylabel("Entries")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    return fig


def fig_to_png(fig) -> bytes:
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()
