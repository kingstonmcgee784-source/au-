import pytest

from app.analysis import scoring, technical


def test_sma_window() -> None:
    assert technical.sma([1, 2, 3, 4, 5], 3) == [None, None, 2.0, 3.0, 4.0]


def test_ema_seeds_with_sma_then_smooths() -> None:
    result = technical.ema([1, 2, 3, 4], 3)
    assert result[:2] == [None, None]
    assert result[2] == pytest.approx(2.0)
    # alpha = 0.5: 0.5 * 4 + 0.5 * 2
    assert result[3] == pytest.approx(3.0)


def test_rsi_extremes_and_known_value() -> None:
    rising = [float(i) for i in range(20)]
    assert technical.rsi(rising, 14)[-1] == pytest.approx(100.0)
    flat = [10.0] * 20
    assert technical.rsi(flat, 14)[-1] == pytest.approx(50.0)
    # Two gains of 1 and one loss of 1 over period 3: RS = (2/3)/(1/3) = 2.
    assert technical.rsi([1, 2, 3, 2], 3)[-1] == pytest.approx(100 - 100 / 3)


def test_rsi_undefined_without_enough_history() -> None:
    assert technical.rsi([1, 2, 3], 14) == [None, None, None]


def test_macd_defined_after_slow_period() -> None:
    closes = [float(i) for i in range(40)]
    line, signal, histogram = technical.macd(closes)
    assert line[24] is None and line[25] is not None
    assert signal[32] is None and signal[33] is not None
    assert histogram[-1] == pytest.approx(line[-1] - signal[-1])  # type: ignore[operator]


def test_invalid_periods_rejected() -> None:
    with pytest.raises(ValueError):
        technical.sma([1, 2], 0)
    with pytest.raises(ValueError):
        technical.macd([1, 2], fast=26, slow=12)


def test_score_weights_total_100() -> None:
    assert sum(category.weight for category in scoring.CATEGORIES) == 100


def test_total_score_from_ratings() -> None:
    ratings = {category.key: 0.5 for category in scoring.CATEGORIES}
    total, points = scoring.total_score(ratings)
    assert total == 50
    assert points["fundamentals"] == 10


def test_total_score_rejects_missing_or_out_of_range() -> None:
    with pytest.raises(ValueError, match="missing"):
        scoring.total_score({"fundamentals": 1.0})
    ratings = {category.key: 0.5 for category in scoring.CATEGORIES}
    ratings["valuation"] = 1.5
    with pytest.raises(ValueError, match="between 0 and 1"):
        scoring.total_score(ratings)


@pytest.mark.parametrize(
    ("score", "label"),
    [(95, "Exceptional"), (80, "Very attractive"), (65, "Mixed"), (10, "Avoid")],
)
def test_interpret_bands(score: float, label: str) -> None:
    assert scoring.interpret(score).startswith(label)
