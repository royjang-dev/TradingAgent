from app.exchange.base import Ticker


def test_change_and_depth_from_bitget_fields():
    t = Ticker.from_bitget(
        {
            "symbol": "BTCUSDT",
            "lastPr": "110",
            "openUtc": "100",
            "bidPr": "109.5",
            "askPr": "110.5",
            "fundingRate": "0.0001",
            "usdtVolume": "1000000",
        }
    )
    assert t.last == 110.0 and t.open_utc == 100.0
    assert round(t.change_pct, 2) == 10.0
    assert round(t.depth_gap_pct, 4) == round((110.5 - 109.5) / 109.5 * 100, 4)
    assert t.quote_volume == 1000000.0


def test_from_bitget_handles_missing_values():
    t = Ticker.from_bitget({"symbol": "X", "lastPr": "1"})
    assert t.last == 1.0 and t.open_utc == 0.0
    assert t.change_pct == 0.0 and t.depth_gap_pct == 0.0
