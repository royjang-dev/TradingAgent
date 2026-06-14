import asyncio

from app.config import MeanRevertTarget
from app.engine.position_manager import PositionManager
from app.exchange.base import Ticker
from app.exchange.paper_adapter import PaperAdapter
from app.models import EntryType, Side, Signal, TimeFrame
from app.strategies import build_strategy
from app.strategies.base import MarketView


class ScriptSource:
    def __init__(self, last):
        self.last = last

    async def fetch_ticker(self, s):
        return Ticker(symbol=s, last=self.last)

    async def fetch_tickers(self):
        return [Ticker("AAAUSDT", self.last)]

    async def load_markets(self):
        return ["AAAUSDT"]

    async def fetch_ohlcv(self, s, tf, limit=200):
        return []

    async def close(self):
        pass


def test_add_averages_entry_and_increments_split():
    async def run():
        src = ScriptSource(100.0)
        adapter = PaperAdapter(src, slippage_pct=0.0)
        t = MeanRevertTarget(
            target_name="MeanRevert",
            short_usdt=10.0,
            short_leverage=10,
            short_split_cnt=2,
            short_split_gap=30.0,
            split_squared_enabled=False,
            trailing_stop_use=False,
        )
        strat = build_strategy(EntryType.MEAN_REVERT, t)
        pm = PositionManager(adapter, {EntryType.MEAN_REVERT: t}, {EntryType.MEAN_REVERT: strat})

        sig = Signal("AAAUSDT", Side.SHORT, EntryType.MEAN_REVERT, TimeFrame.H1, 100.0, 20.0)
        w = await pm.open(sig, Ticker("AAAUSDT", 100.0))
        assert w.split_count == 1 and w.entry_price == 100.0

        src.last = 140.0  # +40% adverse for a short -> add fires (gap 30)
        await pm.manage(w, MarketView("AAAUSDT", Ticker("AAAUSDT", 140.0), closes={"1h": [100.0] * 19 + [140.0]}))
        assert w.split_count == 2
        assert 100.0 < w.entry_price < 140.0
        assert ("AAAUSDT", "short") in pm.positions

    asyncio.run(run())
