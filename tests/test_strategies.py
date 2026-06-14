from app.config import BreakoutTarget, MeanRevertTarget, UprichAgrtTarget
from app.exchange.base import Ticker
from app.models import EntryType, Side, TimeFrame, Wallet
from app.strategies import build_strategy
from app.strategies.base import MarketView


def _spike(last):
    return [100.0] * 19 + [last]


def _mv(symbol, last, closes_1h):
    return MarketView(symbol=symbol, ticker=Ticker(symbol=symbol, last=last), closes={"1h": closes_1h})


def test_mean_revert_short_fires_on_pierce_and_deviation():
    t = MeanRevertTarget(target_name="MeanRevert", short_use_1h=True, short_use_4h=False, volatility_1h=10.0)
    s = build_strategy(EntryType.MEAN_REVERT, t)
    sig = s.evaluate_entry(_mv("AAAUSDT", 130.0, _spike(130.0)))
    assert sig is not None and sig.side is Side.SHORT
    assert sig.strategy is EntryType.MEAN_REVERT and sig.timeframe is TimeFrame.H1
    assert sig.deviation_pct >= 10.0


def test_no_entry_when_deviation_below_threshold():
    t = MeanRevertTarget(target_name="MeanRevert", short_use_1h=True, volatility_1h=40.0)
    s = build_strategy(EntryType.MEAN_REVERT, t)
    assert s.evaluate_entry(_mv("AAAUSDT", 130.0, _spike(130.0))) is None


def test_open_skip_blocks_side():
    t = MeanRevertTarget(target_name="MeanRevert", short_use_1h=True, volatility_1h=10.0,
                         short_open_skip=True, long_open_skip=True)
    s = build_strategy(EntryType.MEAN_REVERT, t)
    assert s.evaluate_entry(_mv("AAAUSDT", 130.0, _spike(130.0))) is None


def test_breakout_short_only_and_registered():
    t = BreakoutTarget(target_name="Breakout", use_1h=True, volatility_1h=10.0, long_open_skip=True)
    s = build_strategy(EntryType.BREAKOUT, t)
    mv = MarketView(
        symbol="X",
        ticker=Ticker(symbol="X", last=130.0),
        closes={"1h": _spike(130.0)},
        highs={"1h": _spike(130.0)},
        lows={"1h": [100.0] * 20},
    )
    sig = s.evaluate_entry(mv)
    assert sig is not None and sig.side is Side.SHORT


def test_uprich_agrt_uses_short_volatility_band():
    t = UprichAgrtTarget(target_name="UprichAgrt", short_use_1h=True, short_volatility_1h=10.0, long_volatility_1h=10.0)
    s = build_strategy(EntryType.UPRICH_AGRT, t)
    sig = s.evaluate_entry(_mv("AAAUSDT", 130.0, _spike(130.0)))
    assert sig is not None and sig.strategy is EntryType.UPRICH_AGRT


def test_should_add_on_adverse_gap():
    t = MeanRevertTarget(target_name="MeanRevert", short_split_cnt=2, short_split_gap=30.0, split_squared_enabled=False)
    s = build_strategy(EntryType.MEAN_REVERT, t)
    w = Wallet(name="X", side=Side.SHORT, entry_type=EntryType.MEAN_REVERT, timeframe=TimeFrame.H1,
               entry_price=100.0, last_entry_price=100.0, split_count=1, entry_count=10)
    assert s.should_add(w, MarketView("X", Ticker("X", last=131.0))) is True
    assert s.should_add(w, MarketView("X", Ticker("X", last=125.0))) is False
