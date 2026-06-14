from __future__ import annotations

from app.config import UprichAgrtTarget
from app.models import EntryType
from app.strategies.base import FadeStrategy, register


@register
class UprichAgrtStrategy(FadeStrategy):
    entry_type = EntryType.UPRICH_AGRT

    def enabled_timeframes(self, side: str) -> list[tuple[str, float]]:
        t: UprichAgrtTarget = self.target  # type: ignore[assignment]
        if side == "short":
            cand = [("1h", t.short_use_1h, t.short_volatility_1h), ("4h", t.short_use_4h, t.short_volatility_4h)]
        else:
            cand = [("1h", t.long_use_1h, t.long_volatility_1h), ("4h", t.long_use_4h, t.long_volatility_4h)]
        return [(tf, vol) for tf, on, vol in cand if on]
