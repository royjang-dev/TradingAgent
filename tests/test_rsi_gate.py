import asyncio

from app.config import Config, MeanRevertTarget
from app.engine.trading_service import TradingService
from app.exchange.base import Ticker
from app.exchange.paper_adapter import PaperAdapter
from app.models import EntryType
from app.strategies import indicators as ind
from app.strategies.base import MarketView


def test_ultimate_rsi_in_range():
    closes = [100 + (i % 7) - 3 for i in range(60)]
    arsi = ind.ultimate_rsi(closes, 14)
    vals = [a for a in arsi if a is not None]
    assert vals and all(0 <= a <= 100 for a in vals)


def test_rsi_crossed_down_detects_turn():
    rising = [100.0 + i for i in range(50)]
    assert ind.rsi_crossed_down(rising) is False           # pure uptrend: no crossdown
    falling = rising + [148.0, 140.0, 132.0, 125.0]        # rise then drop -> momentum turns down
    assert any(ind.rsi_crossed_down(falling[:k]) for k in range(51, len(falling) + 1))


def _gated_config():
    c = Config(breakout_enabled=False, uprich_agrt_enabled=False)
    c.rsi_gated_short_enabled = True
    c.mean_revert_target = MeanRevertTarget(
        target_name="MeanRevert", short_use_1h=True, volatility_1h=10.0,
        min_profit=1, trailing_stop=3, trailing_stop_use=True,
        short_usdt=10.0, short_leverage=10, short_position_cnt=1, short_split_cnt=1,
    )
    return c


class _Src:
    last = 0.0
    async def load_markets(self): return ["AAAUSDT"]
    async def fetch_ticker(self, s): return Ticker(symbol=s, last=self.last)
    async def fetch_tickers(self): return [Ticker(symbol="AAAUSDT", last=self.last)]
    async def fetch_ohlcv(self, s, tf, limit=200): return []
    async def close(self): pass


def _mv(last, closes):
    return {"AAAUSDT": MarketView("AAAUSDT", Ticker("AAAUSDT", last), closes={"1h": closes})}


def test_gate_arms_instead_of_opening():
    async def run():
        ts = TradingService(PaperAdapter(_Src(), start_balance=10000.0), _gated_config())
        await ts.cycle(_mv(130.0, [100.0] * 19 + [130.0]))
        assert ("AAAUSDT", "short") not in ts.pm.positions          # not opened immediately
        assert ("AAAUSDT", EntryType.MEAN_REVERT) in ts._short_watch  # armed instead
    asyncio.run(run())


def test_gate_enters_on_crossdown():
    async def run():
        rising = [100.0 + i for i in range(50)]
        falling = rising + [148.0, 140.0, 132.0, 125.0]
        ks = [k for k in range(51, len(falling) + 1) if ind.rsi_crossed_down(falling[:k])]
        assert ks, "test series must produce a crossdown"
        cl = falling[: ks[0]]
        ts = TradingService(PaperAdapter(_Src(), start_balance=10000.0), _gated_config())
        ts._short_watch[("AAAUSDT", EntryType.MEAN_REVERT)] = 5      # pre-armed watch
        await ts.cycle(_mv(cl[-1], cl))
        assert ("AAAUSDT", "short") in ts.pm.positions               # crossdown -> entered
        assert ("AAAUSDT", EntryType.MEAN_REVERT) not in ts._short_watch
    asyncio.run(run())
