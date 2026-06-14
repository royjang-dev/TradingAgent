import asyncio

from app.exchange.base import Ticker
from app.exchange.paper_adapter import PaperAdapter


class FakeSource:
    def __init__(self, last):
        self._last = last
        self.closed = False

    async def load_markets(self):
        return ["BTCUSDT", "ETHUSDT"]

    async def fetch_ticker(self, symbol):
        return Ticker(symbol=symbol, last=self._last)

    async def fetch_tickers(self):
        return [Ticker(symbol="BTCUSDT", last=self._last)]

    async def fetch_ohlcv(self, symbol, timeframe, limit=200):
        return [[0, 1, 2, 0.5, 1.5, 10]]

    async def close(self):
        self.closed = True


def test_balance_starts_and_adjusts():
    async def run():
        a = PaperAdapter(FakeSource(100.0), start_balance=10000.0)
        assert await a.fetch_balance() == 10000.0
        a.apply_realized_pnl(250.0)
        assert await a.fetch_balance() == 10250.0

    asyncio.run(run())


def test_fill_uses_source_price_with_slippage():
    async def run():
        a = PaperAdapter(FakeSource(100.0), slippage_pct=1.0)
        short_open = await a.create_market_order("BTCUSDT", "short", qty=2)
        long_open = await a.create_market_order("BTCUSDT", "long", qty=2)
        assert short_open.price == 99.0
        assert long_open.price == 101.0

    asyncio.run(run())


def test_reads_delegate_to_source():
    async def run():
        src = FakeSource(100.0)
        a = PaperAdapter(src)
        assert await a.load_markets() == ["BTCUSDT", "ETHUSDT"]
        assert (await a.fetch_ticker("ETHUSDT")).last == 100.0
        assert len(await a.fetch_tickers()) == 1
        await a.close()
        assert src.closed is True

    asyncio.run(run())
