import asyncio

from app.config import Config, MeanRevertTarget, RiskGuards
from app.engine.risk import RiskGuard
from app.engine.trading_service import TradingService
from app.exchange.base import Ticker
from app.exchange.paper_adapter import PaperAdapter
from app.models import EntryType, Record, Side, TimeFrame, Wallet
from app.strategies.base import MarketView


class ScriptSource:
    def __init__(self, last):
        self.last = last

    async def fetch_ticker(self, s):
        return Ticker(s, self.last)

    async def fetch_tickers(self):
        return []

    async def load_markets(self):
        return ["X"]

    async def fetch_ohlcv(self, s, tf, limit=200):
        return []

    async def close(self):
        pass


def _short_wallet(roe):
    entry, lev = 100.0, 10
    price = entry * (1 - roe / (lev * 100))  # short roe = (entry-price)/entry*lev*100
    return Wallet(name="X", side=Side.SHORT, entry_type=EntryType.MEAN_REVERT, timeframe=TimeFrame.H1,
                  leverage=lev, entry_price=entry, entry_count=1.0, current_price=price)


def _rec(pnl, day):
    return Record(name="X", side=Side.SHORT, entry_type=EntryType.MEAN_REVERT, timeframe=TimeFrame.H1,
                  entry_price=1, close_price=1, close_count=1, pnl=pnl, roe=0, split_count=1,
                  trading_time=day + " 10:00:00")


def test_position_breach_off_by_default():
    assert RiskGuard(RiskGuards()).position_breached(_short_wallet(-1000)) is False


def test_position_breach_triggers_when_enabled():
    g = RiskGuard(RiskGuards(enabled=True, position_max_loss_roe=-500))
    assert g.position_breached(_short_wallet(-600)) is True
    assert g.position_breached(_short_wallet(-400)) is False


def test_daily_halt():
    g = RiskGuard(RiskGuards(enabled=True, daily_loss_limit_usdt=-100))
    recs = [_rec(-60, "2026-06-11"), _rec(-50, "2026-06-11"), _rec(999, "2026-06-10")]
    assert g.daily_halted(recs, "2026-06-11") is True
    assert g.daily_halted(recs, "2026-06-10") is False


def test_cycle_force_closes_breached_position():
    async def run():
        adapter = PaperAdapter(ScriptSource(160.0), start_balance=10000.0)
        config = Config(breakout_enabled=False, uprich_agrt_enabled=False)
        config.risk_guards = RiskGuards(enabled=True, position_max_loss_roe=-500)
        config.mean_revert_target = MeanRevertTarget(target_name="MeanRevert", short_use_1h=True, volatility_1h=999.0)
        ts = TradingService(adapter, config)
        ts.pm.positions[("X", "short")] = Wallet(
            name="X", side=Side.SHORT, entry_type=EntryType.MEAN_REVERT, timeframe=TimeFrame.H1,
            leverage=10, entry_price=100.0, entry_count=1.0, current_price=100.0,
        )
        await ts.cycle({"X": MarketView("X", Ticker("X", 160.0), closes={"1h": [100.0] * 20})}, now="2026-06-11 10:00:00")
        assert ("X", "short") not in ts.pm.positions
        assert ts.pm.records and ts.pm.records[-1].entry_type is EntryType.MEAN_REVERT

    asyncio.run(run())
