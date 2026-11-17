"""Classify 8-K events and turn them into catalyst metrics. Pure functions.

An 8-K lists the event "items" it reports. The item number says what kind of
event it is, not whether it is good or bad. So only items that are reliable
red flags count against a stock (bankruptcy, impairments, restated
financials, auditor changes). Ambiguous items, such as 3.01, which covers both
delisting notices and voluntary exchange transfers, are marked for reading.

Limitation: this sees event types only. It cannot tell how large a contract
is or whether earnings will beat expectations.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta

# item -> (label, kind). Kinds group items for display and scoring.
ITEMS: dict[str, tuple[str, str]] = {
    "1.01": ("Entered a material agreement", "agreement"),
    "1.02": ("Ended a material agreement", "review"),
    "1.03": ("Bankruptcy or receivership", "red_flag"),
    "1.05": ("Material cybersecurity incident", "review"),
    "2.01": ("Completed an acquisition or sale of assets", "acquisition"),
    "2.02": ("Quarterly results (earnings release)", "earnings"),
    "2.03": ("Took on new debt or obligations", "financing"),
    "2.04": ("Debt payment accelerated", "review"),
    "2.05": ("Restructuring or exit costs", "review"),
    "2.06": ("Material impairment", "red_flag"),
    "3.01": ("Listing notice or exchange transfer", "review"),
    "3.02": ("Sold unregistered shares", "dilution"),
    "3.03": ("Changed shareholder rights", "review"),
    "4.01": ("Changed auditor", "review"),
    "4.02": ("Previous financial statements can no longer be relied on", "red_flag"),
    "5.01": ("Change in control", "acquisition"),
    "5.02": ("Executive or director change", "management"),
    "5.03": ("Amended charter or bylaws", "governance"),
    "5.07": ("Shareholder vote results", "governance"),
    "7.01": ("Investor presentation or other disclosure", "disclosure"),
    "8.01": ("Other material event", "other"),
}
IGNORED_ITEMS = {"9.01"}  # exhibits attached to the filing

# Order used to pick the headline item of a filing.
PRIORITY = [
    "red_flag",
    "acquisition",
    "earnings",
    "agreement",
    "review",
    "dilution",
    "financing",
    "management",
    "other",
    "disclosure",
    "governance",
]
RED_FLAG_WEIGHT = {"1.03": 1.0, "2.06": 1.0, "4.02": 1.0, "4.01": 0.5}
MATERIAL_KINDS = {"agreement", "acquisition"}


@dataclass(frozen=True)
class Item:
    code: str
    label: str
    kind: str


@dataclass(frozen=True)
class Event:
    filed_on: date
    items: tuple[str, ...]


def classify(item_codes: Sequence[str]) -> list[Item]:
    out = []
    for raw in item_codes:
        code = raw.strip()
        if not code or code in IGNORED_ITEMS:
            continue
        label, kind = ITEMS.get(code, (f"Item {code}", "other"))
        out.append(Item(code, label, kind))
    return out


def parse_items(text: str) -> list[str]:
    return [part.strip() for part in text.split(",") if part.strip()]


def headline(items: Sequence[Item]) -> Item | None:
    if not items:
        return None
    return min(items, key=lambda i: PRIORITY.index(i.kind) if i.kind in PRIORITY else len(PRIORITY))


def estimate_next_earnings(release_dates: Sequence[date], today: date) -> date | None:
    """Estimate the next earnings release from past ones (item 2.02 filings).

    Companies report on a steady yearly rhythm, so the next release is
    estimated as the release about a year before it, plus one year. With
    less history, the last release plus one quarter is used.
    """
    past = sorted(d for d in release_dates if d <= today)
    if not past:
        return None
    expected = past[-1] + timedelta(days=91)
    year_earlier = [d for d in past if abs((d + timedelta(days=365)) - expected).days <= 25]
    estimate = (
        min(year_earlier, key=lambda d: abs((d + timedelta(days=365)) - expected))
        + timedelta(days=365)
        if year_earlier
        else expected
    )
    # If the estimate has passed without a release, the date is unknown.
    return estimate if estimate >= today - timedelta(days=7) else None


def catalyst_metrics(events: Sequence[Event], today: date) -> dict[str, float | None]:
    red_flags = 0.0
    material = 0
    releases: list[date] = []
    for event in events:
        age = (today - event.filed_on).days
        for code in event.items:
            if code == "2.02":
                releases.append(event.filed_on)
            if age <= 365:
                red_flags += RED_FLAG_WEIGHT.get(code, 0.0)
            if age <= 180 and ITEMS.get(code, ("", ""))[1] in MATERIAL_KINDS:
                material += 1
    next_earnings = estimate_next_earnings(releases, today)
    days_to_earnings = (next_earnings - today).days if next_earnings else None
    return {
        "catalyst_red_flags_365d": red_flags,
        "catalyst_material_events_180d": float(material),
        "catalyst_earnings_within_90d": (
            1.0 if days_to_earnings is not None and 0 <= days_to_earnings <= 90 else 0.0
        ),
        "days_to_estimated_earnings": float(days_to_earnings)
        if days_to_earnings is not None
        else None,
    }
