from app.config import BreakoutTarget, Target


def _t(**kw):
    base = dict(
        target_name="UprichAgrt",
        long_usdt=58.2,
        short_usdt=58.2,
        long_leverage=30,
        short_leverage=30,
        long_split_cnt=1,
        short_split_cnt=1,
        long_split_gap=30.0,
        short_split_gap=30.0,
        long_auto_input_ctrl=300.0,
        short_auto_input_ctrl=300.0,
        split_squared_enabled=True,
        split_interval_multiplier=6.0,
        split_multiplier_start_at=1,
    )
    base.update(kw)
    return Target(**base)


def test_qty_from_usdt_leverage():
    t = _t()
    assert round(t.qty("short", price=0.04383), 2) == round(58.2 * 30 / 0.04383, 2)


def test_dynamic_split_gap_matches_ui_preview():
    t = _t()
    assert t.get_dynamic_split_gap("short", 2) == 360.0
    assert t.get_dynamic_split_gap("short", 3) == 540.0
    assert t.get_dynamic_split_gap("short", 4) == 720.0
    assert t.get_dynamic_split_gap("short", 5) == 900.0


def test_dynamic_split_gap_flat_when_squared_off():
    t = _t(split_squared_enabled=False)
    assert t.get_dynamic_split_gap("short", 3) == 30.0


def test_breakout_is_short_only():
    b = BreakoutTarget(target_name="Breakout", long_open_skip=True)
    assert b.is_open_skip("long") is True
    assert b.is_open_skip("short") is False
