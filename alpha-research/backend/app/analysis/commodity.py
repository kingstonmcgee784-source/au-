"""Oil-price adjustment for oil and gas companies. Pure functions, no I/O.

An oil company's reported results lag the oil price by up to a quarter, so
its valuation (today's price against past profits) and growth ratings can look
better than its next results will. When oil (USO) is now well below its
average over the last quarter, those two ratings are scaled down:

    gap = latest USO close / average close over the last 63 trading days - 1
    no change while the gap is above -5%; otherwise the ratings are
    multiplied by 1 + 2 * gap, never by less than 0.5.

So oil 10% below its quarterly average lowers them by 20%; 25% or more below,
by half. Rising oil is not added as a bonus: past results already include
the earlier, lower prices, and the score stays cautious.
"""

from collections.abc import Sequence

QUARTER = 63  # trading days
THRESHOLD = -0.05
SLOPE = 2.0
FLOOR = 0.5
ADJUSTED = ("valuation", "growth")


def oil_gap(closes: Sequence[float]) -> float | None:
    """Latest close against the average of the last quarter (closes oldest first)."""
    if len(closes) < QUARTER:
        return None
    recent = closes[-QUARTER:]
    return closes[-1] / (sum(recent) / len(recent)) - 1


def factor(gap: float | None) -> float:
    if gap is None or gap >= THRESHOLD:
        return 1.0
    return max(FLOOR, 1 + SLOPE * gap)


def note(gap: float, multiplier: float) -> str:
    return (
        f"Lowered by {(1 - multiplier) * 100:.0f}% because oil (USO) is {abs(gap) * 100:.1f}% "
        "below its average over the last quarter. The company's reported results come from "
        "before that drop, so they likely overstate its next quarter."
    )
