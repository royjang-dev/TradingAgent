from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.config import Target
from app.exchange.base import Ticker
from app.models import CloseReason, EntryType, Side, Signal, TimeFrame, Wallet
from app.strategies import indicators as ind

_TF = {"1m": TimeFrame.M1, "15m": TimeFrame.M15, "1h": TimeFrame.H1, "4h": TimeFrame.H4, "1d": TimeFrame.D1}


@dataclass
class MarketView:
    symbol: str
    ticker: Ticker
    closes: dict[str, list[float]] = field(default_factory=dict)
    highs: dict[str, list[float]] = field(default_factory=dict)
    lows: dict[str, list[float]] = field(default_factory=dict)


_REGISTRY: dict[EntryType, type["Strategy"]] = {}


def register(cls: type["Strategy"]) -> type["Strategy"]:
    _REGISTRY[cls.entry_type] = cls
    return cls


def build_strategy(entry_type: EntryType, target: Target) -> "Strategy":
    return _REGISTRY[entry_type](target)


class Strategy(ABC):
    entry_type: EntryType

    def __init__(self, target: Target):
        self.target = target

    @abstractmethod
    def evaluate_entry(self, mv: MarketView) -> Signal | None: ...

    def should_add(self, wallet: Wallet, mv: MarketView) -> bool:
        side = "short" if wallet.side is Side.SHORT else "long"
        if wallet.split_count >= self.target.get_split_cnt(side):
            return False
        gap = self.target.get_dynamic_split_gap(side, wallet.split_count + 1)
        ref = wallet.last_entry_price or wallet.entry_price
        if ref <= 0:
            return False
        last = mv.ticker.last
        adverse = (last - ref) / ref * 100 if wallet.side is Side.SHORT else (ref - last) / ref * 100
        return adverse >= gap

    def evaluate_exit(self, wallet: Wallet, mv: MarketView) -> CloseReason | None:
        if not self.target.reverse_exit:
            return None
        opp = self.evaluate_entry(mv)
        if opp is not None and opp.side is not wallet.side:
            return CloseReason.REVERSE_EXIT
        return None


class FadeStrategy(Strategy):
    """RECONSTRUCTED (spec §19.2, MEDIUM confidence). Short when price pierces
    the upper band/resistance with deviation (이탈율) >= Volatility{tf}; long the
    symmetric oversold case. Subclasses override timeframe/threshold + band hooks."""

    bollinger_period = 20
    bollinger_mult = 2.0
    lookback = 20

    def enabled_timeframes(self, side: str) -> list[tuple[str, float]]:
        raise NotImplementedError

    def bands(self, tf: str, mv: MarketView) -> tuple[float, float, float] | None:
        return ind.bollinger(mv.closes.get(tf, []), self.bollinger_period, self.bollinger_mult)

    def evaluate_entry(self, mv: MarketView) -> Signal | None:
        last = mv.ticker.last
        for side in ("short", "long"):
            if self.target.is_open_skip(side):
                continue
            for tf, vol in self.enabled_timeframes(side):
                bb = self.bands(tf, mv)
                if bb is None:
                    continue
                mid, upper, lower = bb
                dev = ind.deviation_pct(last, mid)
                if side == "short" and last >= upper and dev >= vol:
                    return Signal(mv.symbol, Side.SHORT, self.entry_type, _TF[tf], mid, dev, "upper-band fade")
                if side == "long" and last <= lower and -dev >= vol:
                    return Signal(mv.symbol, Side.LONG, self.entry_type, _TF[tf], mid, -dev, "lower-band fade")
        return None
