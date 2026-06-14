from __future__ import annotations

from app.config import MeanRevertTarget
from app.models import EntryType
from app.strategies.base import FadeStrategy, MarketView, register


@register
class MeanRevertStrategy(FadeStrategy):
    entry_type = EntryType.MEAN_REVERT

    def enabled_timeframes(self, side: str) -> list[tuple[str, float]]:
        t: MeanRevertTarget = self.target  # type: ignore[assignment]
        if side == "short":
            cand = [("1h", t.short_use_1h, t.volatility_1h), ("4h", t.short_use_4h, t.volatility_4h)]
        else:
            cand = [("1h", t.long_use_1h, t.volatility_1h), ("4h", t.long_use_4h, t.volatility_4h)]
        return [(tf, vol) for tf, on, vol in cand if on]
