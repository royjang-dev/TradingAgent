from app.config import BreakoutTarget, MeanRevertTarget
from app.engine.trailing import ExitEngine
from app.models import CloseReason, EntryType, Side, TimeFrame, Wallet


def _wallet(side, entry, entry_type=EntryType.BREAKOUT, tf=TimeFrame.D1, lev=10):
    return Wallet(
        name="T",
        side=side,
        entry_type=entry_type,
        timeframe=tf,
        leverage=lev,
        entry_price=entry,
        entry_count=1000.0,
        current_price=entry,
    )


def test_kat_shallow_profit_then_reverse_holds_no_loss_exit():
    # KAT-like: short reaches only +1.3% (< trailing 3%) then rallies back above entry.
    # The trailing stop sits ABOVE entry (a loss) -> original HOLDS (never closes at a loss).
    # This is the mechanic behind the 100% win rate + bag-held losers.
    w = _wallet(Side.SHORT, 0.01968)
    t = BreakoutTarget(target_name="Breakout", min_profit=1, trailing_stop=3,
                       profit_use=False, stop_loss_use=False, trailing_stop_use=True)
    assert ExitEngine.update(w, t, 0.01942) is None  # +1.3% -> arms
    assert w.target_hit is True
    assert abs(w.min_profit - 0.01968 * 0.99) < 1e-9
    assert abs(w.trailing_stop - 0.01942 * 1.03) < 1e-9  # 0.0200026, ABOVE entry => loss-side
    assert ExitEngine.update(w, t, 0.0203) is None  # rallies past loss-side stop -> NOT closed (held)


def test_deep_profit_trailing_locks_and_exits_short():
    w = _wallet(Side.SHORT, 100.0)
    t = BreakoutTarget(target_name="B", min_profit=1, trailing_stop=3,
                       profit_use=False, stop_loss_use=False, trailing_stop_use=True)
    assert ExitEngine.update(w, t, 90.0) is None  # +10% profit; trailing 92.7 (<entry, locks profit) but not crossed
    assert w.target_hit is True
    assert abs(w.trailing_stop - 90.0 * 1.03) < 1e-9
    assert ExitEngine.update(w, t, 92.8) == CloseReason.TRAILING_STOP  # retrace to profit-locking stop -> exit


def test_trailing_long():
    w = _wallet(Side.LONG, 100.0)
    t = BreakoutTarget(target_name="B", min_profit=1, trailing_stop=3, trailing_stop_use=True,
                       profit_use=False, stop_loss_use=False)
    assert ExitEngine.update(w, t, 102.0) is None  # arms
    assert w.target_hit is True
    assert ExitEngine.update(w, t, 110.0) is None  # new high, still running
    assert abs(w.trailing_stop - 110.0 * 0.97) < 1e-9
    assert ExitEngine.update(w, t, 106.0) == CloseReason.TRAILING_STOP


def test_no_hard_stop_holds_loser():
    w = _wallet(Side.SHORT, 0.1407, entry_type=EntryType.MEAN_REVERT, tf=TimeFrame.H1)
    t = MeanRevertTarget(target_name="MeanRevert", min_profit=1, trailing_stop=3,
                         profit_use=False, stop_loss_use=False, trailing_stop_use=True)
    for px in (0.15, 0.17, 0.1792):
        assert ExitEngine.update(w, t, px) is None
    assert w.target_hit is False
    assert w.max_loss < 0


def test_hard_stop_fires_when_enabled():
    w = _wallet(Side.SHORT, 100.0)
    t = BreakoutTarget(target_name="B", stop_loss=10, stop_loss_use=True, trailing_stop_use=False)
    assert ExitEngine.update(w, t, 111.0) == CloseReason.STOP_LOSS


def test_hard_take_profit_fires_when_enabled():
    w = _wallet(Side.SHORT, 100.0)
    t = BreakoutTarget(target_name="B", profit=5, profit_use=True, trailing_stop_use=False)
    assert ExitEngine.update(w, t, 94.0) == CloseReason.PROFIT
