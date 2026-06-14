from app.models import (
    CloseReason,
    EntryType,
    Record,
    Side,
    Signal,
    TimeFrame,
    Wallet,
)


def test_enum_values():
    assert Side.SHORT.value == "short"
    assert Side.LONG.value == "long"
    assert TimeFrame.H1.value == "1h"
    assert EntryType.UPRICH_AGRT.value == "UprichAgrt"
    assert CloseReason.TRAILING_STOP.value == "TrailingStop"


def test_signal_holds_fields():
    s = Signal(
        symbol="BTCUSDT",
        side=Side.SHORT,
        strategy=EntryType.BREAKOUT,
        timeframe=TimeFrame.D1,
        ref_price=100.0,
        deviation_pct=30.0,
        reason="band",
    )
    assert s.symbol == "BTCUSDT" and s.side is Side.SHORT and s.deviation_pct == 30.0


def _short_wallet():
    return Wallet(
        name="KATUSDT",
        side=Side.SHORT,
        entry_type=EntryType.BREAKOUT,
        timeframe=TimeFrame.D1,
        leverage=10,
        entry_price=0.01968,
        entry_count=1168.0,
        current_price=0.02212,
    )


def test_wallet_pnl_short_loss():
    w = _short_wallet()
    assert round(w.calc_pnl(), 4) == round((0.01968 - 0.02212) * 1168.0, 4)


def test_wallet_roe_uses_leverage():
    w = _short_wallet()
    expected = (0.01968 - 0.02212) / 0.01968 * 10 * 100
    assert round(w.calc_roe(), 2) == round(expected, 2)


def test_wallet_roundtrip_dict():
    w = _short_wallet()
    assert Wallet.from_dict(w.to_dict()).to_dict() == w.to_dict()


def test_record_from_wallet_captures_close():
    w = _short_wallet()
    r = Record.from_wallet(w, close_price=0.0194832)
    assert r.name == "KATUSDT" and r.side is Side.SHORT
    assert r.entry_price == 0.01968 and r.close_price == 0.0194832
    assert r.pnl > 0 and r.roe > 0


def test_record_roundtrip_dict():
    r = Record.from_wallet(_short_wallet(), close_price=0.0194832)
    assert Record.from_dict(r.to_dict()).to_dict() == r.to_dict()
