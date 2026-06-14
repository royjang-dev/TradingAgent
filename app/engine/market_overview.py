from __future__ import annotations

from dataclasses import dataclass, field

from app.exchange.base import Ticker


@dataclass
class CoinChange:
    symbol: str
    pct: float


@dataclass
class CoinVolume:
    symbol: str
    quote_volume: float
    change_pct: float


@dataclass
class MarketOverview:
    btc: Ticker | None = None
    eth: Ticker | None = None
    up_count: int = 0
    down_count: int = 0
    total: int = 0
    up_ratio: float = 0.0
    avg_change: float = 0.0
    avg_volatility: float = 0.0
    avg_daily_range: float = 0.0
    avg_funding: float = 0.0
    funding_high: CoinChange | None = None
    funding_low: CoinChange | None = None
    top_gainers: list[CoinChange] = field(default_factory=list)
    top_losers: list[CoinChange] = field(default_factory=list)
    top_volume: list[CoinVolume] = field(default_factory=list)


def build_market_overview(tickers: list[Ticker], top_n: int = 5) -> MarketOverview:
    if not tickers:
        return MarketOverview()
    by_symbol = {t.symbol: t for t in tickers}
    total = len(tickers)
    changes = [t.change_pct for t in tickers]
    up = sum(1 for c in changes if c > 0)
    down = sum(1 for c in changes if c < 0)
    by_change_desc = sorted(tickers, key=lambda t: t.change_pct, reverse=True)
    by_funding = sorted(tickers, key=lambda t: t.funding_rate)
    by_volume = sorted(tickers, key=lambda t: t.quote_volume, reverse=True)
    return MarketOverview(
        btc=by_symbol.get("BTCUSDT"),
        eth=by_symbol.get("ETHUSDT"),
        up_count=up,
        down_count=down,
        total=total,
        up_ratio=up / total * 100,
        avg_change=sum(changes) / total,
        avg_volatility=sum(abs(c) for c in changes) / total,
        avg_daily_range=(
            sum((t.high - t.low) / t.low * 100 for t in tickers if t.low > 0 and t.high > 0)
            / max(sum(1 for t in tickers if t.low > 0 and t.high > 0), 1)
        ),
        avg_funding=sum(t.funding_rate for t in tickers) / total * 100,
        funding_high=CoinChange(by_funding[-1].symbol, by_funding[-1].funding_rate * 100),
        funding_low=CoinChange(by_funding[0].symbol, by_funding[0].funding_rate * 100),
        top_gainers=[CoinChange(t.symbol, t.change_pct) for t in by_change_desc[:top_n]],
        top_losers=[CoinChange(t.symbol, t.change_pct) for t in reversed(by_change_desc[-top_n:])],
        top_volume=[CoinVolume(t.symbol, t.quote_volume, t.change_pct) for t in by_volume[:top_n]],
    )
