from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Side(str, Enum):
    LONG = "long"
    SHORT = "short"


class TimeFrame(str, Enum):
    M1 = "1m"
    M15 = "15m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"


class EntryType(str, Enum):
    MEAN_REVERT = "MeanRevert"
    BREAKOUT = "Breakout"
    UPRICH_AGRT = "UprichAgrt"


class CloseReason(str, Enum):
    TRAILING_STOP = "TrailingStop"
    PROFIT = "Profit"
    STOP_LOSS = "StopLoss"
    REVERSE_EXIT = "ReverseExit"
    MANUAL = "Manual"
    REBALANCE = "Rebalance"
    RISK_GUARD = "RiskGuard"


@dataclass
class Signal:
    symbol: str
    side: Side
    strategy: EntryType
    timeframe: TimeFrame
    ref_price: float
    deviation_pct: float
    reason: str = ""


@dataclass
class Wallet:
    name: str
    side: Side
    entry_type: EntryType
    timeframe: TimeFrame
    leverage: int = 1
    entry_price: float = 0.0
    entry_count: float = 0.0
    current_price: float = 0.0
    last_entry_price: float = 0.0
    best_price: float = 0.0
    split_count: int = 1
    margin_mode: str = "crossed"
    target_price: float = 0.0
    min_profit: float = 0.0
    trailing_stop: float = 0.0
    stop_loss: float = 0.0
    support_line: float = 0.0
    resist_line: float = 0.0
    target_hit: bool = False
    bolinger_hit: bool = False
    is_time_rebalance: bool = False
    max_loss: float = 0.0
    max_profit: float = 0.0
    usdt_balance: float = 0.0
    trading_time: str = ""
    preset_stop_loss_order_id: str | None = None
    preset_take_profit_order_id: str | None = None
    tracking_no: int = 0

    def _dir(self) -> int:
        return 1 if self.side is Side.SHORT else -1

    def calc_pnl(self) -> float:
        return self._dir() * (self.entry_price - self.current_price) * self.entry_count

    def calc_roe(self) -> float:
        if self.entry_price == 0:
            return 0.0
        return self._dir() * (self.entry_price - self.current_price) / self.entry_price * self.leverage * 100

    def is_valid(self) -> bool:
        return bool(self.name) and self.entry_price > 0 and self.entry_count > 0

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["side"] = self.side.value
        d["entry_type"] = self.entry_type.value
        d["timeframe"] = self.timeframe.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Wallet":
        d = dict(d)
        d["side"] = Side(d["side"])
        d["entry_type"] = EntryType(d["entry_type"])
        d["timeframe"] = TimeFrame(d["timeframe"])
        return cls(**d)


@dataclass
class Record:
    name: str
    side: Side
    entry_type: EntryType
    timeframe: TimeFrame
    entry_price: float
    close_price: float
    close_count: float
    pnl: float
    roe: float
    split_count: int
    max_loss: float = 0.0
    max_profit: float = 0.0
    entry_time: str = ""
    trading_time: str = ""
    reason: str = ""

    @classmethod
    def from_wallet(cls, w: "Wallet", close_price: float) -> "Record":
        closed = Wallet(**{**w.__dict__})
        closed.current_price = close_price
        return cls(
            name=w.name,
            side=w.side,
            entry_type=w.entry_type,
            timeframe=w.timeframe,
            entry_price=w.entry_price,
            close_price=close_price,
            close_count=w.entry_count,
            pnl=closed.calc_pnl(),
            roe=closed.calc_roe(),
            split_count=w.split_count,
            max_loss=w.max_loss,
            max_profit=w.max_profit,
            entry_time=w.trading_time,
            trading_time=w.trading_time,
        )

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["side"] = self.side.value
        d["entry_type"] = self.entry_type.value
        d["timeframe"] = self.timeframe.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Record":
        d = dict(d)
        d["side"] = Side(d["side"])
        d["entry_type"] = EntryType(d["entry_type"])
        d["timeframe"] = TimeFrame(d["timeframe"])
        return cls(**d)
