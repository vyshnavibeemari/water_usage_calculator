"""Constants and the UsageRecord data model."""
from __future__ import annotations

from dataclasses import asdict, dataclass

SCHEMA_VERSION = 1
DEFAULT_THRESHOLD = 135.0        # litres per person per day
BASELINE_L_PER_PERSON = 5.0      # cooking and drinking, added automatically
BASELINE_KEY = "cooking_drinking"
BASELINE_LABEL = "Cooking & drinking"
MIN_PEOPLE, MAX_PEOPLE = 1, 20
MAX_LABEL_LEN, MAX_NOTES_LEN = 60, 200
STATUSES = ("Efficient", "Normal", "High", "Critical")
STATUS_BANDS = (0.70, 1.00, 1.30)   # share of threshold: <70% Efficient, <=100% Normal, <=130% High


@dataclass(frozen=True)
class Activity:
    key: str
    label: str
    unit: str          # plural, used for the quantity input ("minutes")
    per: str           # singular, used for the coefficient ("per minute")
    coefficient: float  # litres per unit
    max_value: float    # household total per day


ACTIVITIES = {
    a.key: a
    for a in (
        Activity("shower", "Shower", "minutes", "minute", 9.5, 600),
        Activity("toilet", "Toilet flushes", "flushes", "flush", 6.0, 200),
        Activity("tap", "Tap running (brushing, shaving)", "minutes", "minute", 6.0, 300),
        Activity("dishwasher", "Dishwasher", "cycles", "cycle", 15.0, 20),
        Activity("handwash", "Hand-washing dishes", "minutes", "minute", 8.0, 300),
        Activity("washer", "Washing machine", "loads", "load", 50.0, 20),
        Activity("garden", "Garden hose", "minutes", "minute", 15.0, 600),
        Activity("carwash", "Car wash", "washes", "wash", 100.0, 10),
    )
}


@dataclass
class UsageRecord:
    id: str
    date: str                       # ISO YYYY-MM-DD
    label: str
    people: int
    activities: dict[str, float]    # quantity per activity key (household total for the day)
    total_liters: float
    per_person: float
    breakdown: dict[str, float]     # litres per category (includes cooking_drinking)
    status: str
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)
