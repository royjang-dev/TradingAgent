from __future__ import annotations

from .base import ExchangeAdapter, Fill, Ticker


class PaperAdapter(ExchangeAdapter):
    """Simulated exchange: real prices from a market-data source, virtual
    balance, simulated fills. Needs no API keys; tests need no network."""

    def __init__(self, data_source, start_balance: float = 10000.0, slippage_pct: float = 0.0):
        self._src = data_source
        self._balance = float(start_balance)
        self._slip = float(slippage_pct)
        self._leverage: dict[tuple[str, str], int] = {}

    async def load_markets(self) -> list[str]:
        return await self._src.load_markets()

    async def fetch_ticker(self, symbol: str) -> Ticker:
        return await self._src.fetch_ticker(symbol)

    async def fetch_tickers(self) -> list[Ticker]:
        return await self._src.fetch_tickers()

    async def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 200) -> list[list[float]]:
        return await self._src.fetch_ohlcv(symbol, timeframe, limit)

    async def fetch_balance(self) -> float:
        return self._balance

    def apply_realized_pnl(self, amount: float) -> None:
        self._balance += float(amount)

    async def set_leverage(self, symbol: str, leverage: int, side: str) -> None:
        self._leverage[(symbol, side)] = leverage

    def amount_to_precision(self, symbol: str, qty: float) -> float:
        fn = getattr(self._src, "amount_to_precision", None)
        return fn(symbol, qty) if fn else qty

    async def create_market_order(self, symbol: str, side: str, qty: float, reduce_only: bool = False) -> Fill:
        ticker = await self._src.fetch_ticker(symbol)
        price = self._apply_slippage(ticker.last, side, reduce_only)
        return Fill(symbol=symbol, side=side, price=price, qty=self.amount_to_precision(symbol, qty))

    def _apply_slippage(self, price: float, side: str, reduce_only: bool) -> float:
        s = self._slip / 100.0
        buying = (side == "long" and not reduce_only) or (side == "short" and reduce_only)
        return price * (1 + s) if buying else price * (1 - s)

    async def close(self) -> None:
        close = getattr(self._src, "close", None)
        if close is not None:
            await close()
