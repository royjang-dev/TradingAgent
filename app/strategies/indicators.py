from __future__ import annotations

import math


def sma(values: list[float], period: int) -> float | None:
    if period <= 0 or len(values) < period:
        return None
    return sum(values[-period:]) / period


def ema(values: list[float], period: int) -> float | None:
    if period <= 0 or len(values) < period:
        return None
    k = 2 / (period + 1)
    e = sum(values[:period]) / period
    for v in values[period:]:
        e = v * k + e * (1 - k)
    return e


def stdev(values: list[float], period: int) -> float | None:
    if period <= 0 or len(values) < period:
        return None
    window = values[-period:]
    m = sum(window) / period
    var = sum((x - m) ** 2 for x in window) / period
    return math.sqrt(var)


def bollinger(values: list[float], period: int = 20, mult: float = 2.0) -> tuple[float, float, float] | None:
    mid = sma(values, period)
    sd = stdev(values, period)
    if mid is None or sd is None:
        return None
    return (mid, mid + mult * sd, mid - mult * sd)


def deviation_pct(price: float, ref: float) -> float:
    if ref == 0:
        return 0.0
    return (price - ref) / ref * 100


def support(lows: list[float], lookback: int = 20) -> float | None:
    if not lows:
        return None
    return min(lows[-lookback:])


def resistance(highs: list[float], lookback: int = 20) -> float | None:
    if not highs:
        return None
    return max(highs[-lookback:])


def atr(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> float | None:
    n = len(closes)
    if n < period + 1 or len(highs) != n or len(lows) != n:
        return None
    trs = []
    for i in range(1, n):
        trs.append(
            max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
        )
    return sum(trs[-period:]) / period


def _rma_series(values: list[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if len(values) < period:
        return out
    s = sum(values[:period]) / period
    out[period - 1] = s
    for i in range(period, len(values)):
        s = (s * (period - 1) + values[i]) / period
        out[i] = s
    return out


def _ema_series(values: list[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if len(values) < period:
        return out
    k = 2 / (period + 1)
    e = sum(values[:period]) / period
    out[period - 1] = e
    for i in range(period, len(values)):
        e = values[i] * k + e * (1 - k)
        out[i] = e
    return out


def ultimate_rsi(closes: list[float], length: int = 14) -> list[float | None]:
    """Augmented RSI (LuxAlgo 'Ultimate RSI') as a series. RMA smoothing."""
    n = len(closes)
    out: list[float | None] = [None] * n
    if n < length + 1:
        return out
    hi: list[float | None] = [None] * n
    lo: list[float | None] = [None] * n
    for i in range(length - 1, n):
        w = closes[i - length + 1:i + 1]
        hi[i], lo[i] = max(w), min(w)
    diff = [0.0] * n
    for i in range(1, n):
        if hi[i] is not None and hi[i - 1] is not None and hi[i] > hi[i - 1]:
            diff[i] = hi[i] - lo[i]
        elif lo[i] is not None and lo[i - 1] is not None and lo[i] < lo[i - 1]:
            diff[i] = -(hi[i] - lo[i])
        else:
            diff[i] = closes[i] - closes[i - 1]
    num = _rma_series(diff, length)
    den = _rma_series([abs(v) for v in diff], length)
    for i in range(n):
        if num[i] is not None and den[i]:
            out[i] = num[i] / den[i] * 50 + 50
    return out


def rsi_crossed_down(closes: list[float], length: int = 14, smooth: int = 14) -> bool:
    """True when the Ultimate RSI crossed DOWN through its signal line on the last bar."""
    arsi = ultimate_rsi(closes, length)
    v0 = next((i for i, a in enumerate(arsi) if a is not None), None)
    if v0 is None or len(arsi) - v0 < smooth + 2:
        return False
    sig = [None] * v0 + _ema_series([a for a in arsi[v0:]], smooth)
    if arsi[-1] is None or sig[-1] is None or arsi[-2] is None or sig[-2] is None:
        return False
    return arsi[-1] < sig[-1] and arsi[-2] >= sig[-2]
