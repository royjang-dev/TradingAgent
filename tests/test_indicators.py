from app.strategies import indicators as ind


def test_sma_and_insufficient():
    assert ind.sma([1, 2, 3, 4, 5], 5) == 3
    assert ind.sma([1, 2], 5) is None


def test_bollinger_constant_series_collapses():
    vals = [10.0] * 20
    mid, up, lo = ind.bollinger(vals, period=20, mult=2.0)
    assert mid == 10.0 and up == 10.0 and lo == 10.0


def test_bollinger_widens_with_spread():
    vals = [9, 11] * 10
    mid, up, lo = ind.bollinger(vals, period=20, mult=2.0)
    assert mid == 10.0 and up > 10.0 and lo < 10.0


def test_deviation_pct():
    assert ind.deviation_pct(110, 100) == 10.0
    assert ind.deviation_pct(90, 100) == -10.0
    assert ind.deviation_pct(1, 0) == 0.0


def test_support_resistance():
    assert ind.resistance([1, 5, 3, 4], lookback=4) == 5
    assert ind.support([1, 5, 3, 4], lookback=4) == 1


def test_atr_basic():
    highs = [10, 11, 12, 13, 14]
    lows = [9, 10, 11, 12, 13]
    closes = [9.5, 10.5, 11.5, 12.5, 13.5]
    assert ind.atr(highs, lows, closes, period=2) is not None
