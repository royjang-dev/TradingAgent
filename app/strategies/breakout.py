from __future__ import annotations

from app.config import BreakoutTarget
from app.models import EntryType
from app.strategies import indicators as ind
from app.strategies.base import FadeStrategy, MarketView, register


@register
class BreakoutStrategy(FadeStrategy):
    """Fades range-breakouts (resistance/support pierce) on 1h/4h/1d. Short-only
    in practice (long_open_skip)."""

    entry_type = EntryType.BREAKOUT

    def enabled_timeframes(self, side: str) -> list[tuple[str, float]]:
        t: BreakoutTarget = self.target  # type: ignore[assignment]
        cand = [("1h", t.use_1h, t.volatility_1h), ("4h", t.use_4h, t.volatility_4h), ("1d", t.use_1d, t.volatility_1d)]
        return [(tf, vol) for tf, on, vol in cand if on]

    def bands(self, tf: str, mv: MarketView) -> tuple[float, float, float] | None:
        mid = ind.sma(mv.closes.get(tf, []), self.lookback)
        upper = ind.resistance(mv.highs.get(tf, []), self.lookback)
        lower = ind.support(mv.lows.get(tf, []), self.lookback)
        if mid is None or upper is None or lower is None:
            return None
        return (mid, upper, lower)
