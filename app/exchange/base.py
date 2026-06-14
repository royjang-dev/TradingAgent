from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Ticker:
    symbol: str
    last: float
    open_utc: float = 0.0
    mark: float = 0.0
    index: float = 0.0
    funding_rate: float = 0.0
    bid: float = 0.0
    ask: float = 0.0
    quote_volume: float = 0.0
    high: float = 0.0
    low: float = 0.0

    @property
    def change_pct(self) -> float:
        if self.open_utc <= 0:
            return 0.0
        return (self.last - self.open_utc) / self.open_utc * 100

    @property
    def depth_gap_pct(self) -> float:
        if self.bid <= 0:
            return 0.0
        return (self.ask - self.bid) / self.bid * 100

    @classmethod
    def from_bitget(cls, raw: dict) -> "Ticker":
        def f(key: str, default: float = 0.0) -> float:
            v = raw.get(key)
            return float(v) if v not in (None, "") else default

        return cls(
            symbol=str(raw.get("symbol", "")),
            last=f("lastPr"),
            open_utc=f("openUtc"),
            mark=f("markPrice"),
            index=f("indexPrice"),
            funding_rate=f("fundingRate"),
            bid=f("bidPr"),
            ask=f("askPr"),
            quote_volume=f("usdtVolume", f("quoteVolume")),
            high=f("high24h"),
            low=f("low24h"),
        )


@dataclass
class Fill:
    symbol: str
    side: str
    price: float
    qty: float


class ExchangeAdapter(ABC):
    @abstractmethod
    async def load_markets(self) -> list[str]: ...

    @abstractmethod
    async def fetch_ticker(self, symbol: str) -> Ticker: ...

    @abstractmethod
    async def fetch_tickers(self) -> list[Ticker]: ...

    @abstractmethod
    async def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 200) -> list[list[float]]: ...

    @abstractmethod
    async def fetch_balance(self) -> float: ...

    @abstractmethod
    async def set_leverage(self, symbol: str, leverage: int, side: str) -> None: ...

    @abstractmethod
    async def create_market_order(self, symbol: str, side: str, qty: float, reduce_only: bool = False) -> Fill: ...

    @abstractmethod
    async def close(self) -> None: ...

    def amount_to_precision(self, symbol: str, qty: float) -> float:
        return qty
