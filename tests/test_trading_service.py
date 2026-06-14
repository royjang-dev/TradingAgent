import asyncio

from app.config import Config, MeanRevertTarget
from app.engine.trading_service import TradingService
from app.exchange.base import Ticker
from app.exchange.paper_adapter import PaperAdapter
from app.models import EntryType
from app.strategies.base import MarketView


class ScriptSource:
    def __init__(self):
        self.last = 0.0

    async def load_markets(self):
        return ["AAAUSDT"]

    async def fetch_ticker(self, s):
        return Ticker(symbol=s, last=self.last)

    async def fetch_tickers(self):
        return [Ticker(symbol="AAAUSDT", last=self.last)]

    async def fetch_ohlcv(self, s, tf, limit=200):
        return []

    async def close(self):
        pass


def _config_meanrevert_only():
    c = Config(breakout_enabled=False, uprich_agrt_enabled=False)
    c.mean_revert_target = MeanRevertTarget(
        target_name="MeanRevert",
        short_use_1h=True,
        volatility_1h=10.0,
        min_profit=1,
        trailing_stop=3,
        trailing_stop_use=True,
        profit_use=False,
        stop_loss_use=False,
        short_usdt=10.0,
        short_leverage=10,
        short_position_cnt=1,
        short_split_cnt=1,
    )
    return c


def test_paper_e2e_open_trail_close():
    async def run():
        src = ScriptSource()
        adapter = PaperAdapter(src, start_balance=10000.0, slippage_pct=0.0)
        ts = TradingService(adapter, _config_meanrevert_only())

        def mv(last, closes):
            return {"AAAUSDT": MarketView("AAAUSDT", Ticker("AAAUSDT", last), closes={"1h": closes})}

        src.last = 130.0
        await ts.cycle(mv(130.0, [100.0] * 19 + [130.0]))
        assert ("AAAUSDT", "short") in ts.pm.positions
        assert ts.pm.positions[("AAAUSDT", "short")].entry_price == 130.0

        src.last = 99.0
        await ts.cycle(mv(99.0, [100.0] * 19 + [99.0]))
        assert ("AAAUSDT", "short") in ts.pm.positions
        assert ts.pm.positions[("AAAUSDT", "short")].target_hit is True

        src.last = 103.0
        await ts.cycle(mv(103.0, [100.0] * 19 + [103.0]))
        assert ("AAAUSDT", "short") not in ts.pm.positions
        assert len(ts.pm.records) == 1
        rec = ts.pm.records[0]
        assert rec.pnl > 0 and rec.entry_type is EntryType.MEAN_REVERT
        assert await adapter.fetch_balance() > 10000.0

    asyncio.run(run())


def test_update_target_hot_reload():
    src = ScriptSource()
    adapter = PaperAdapter(src)
    ts = TradingService(adapter, _config_meanrevert_only())
    new = MeanRevertTarget(target_name="MeanRevert", short_use_1h=True, volatility_1h=99.0)
    ts.update_target(EntryType.MEAN_REVERT, new)
    assert ts.targets[EntryType.MEAN_REVERT].volatility_1h == 99.0
    assert ts.pm.targets[EntryType.MEAN_REVERT].volatility_1h == 99.0
