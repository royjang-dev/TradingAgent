from app.engine.market_overview import build_market_overview
from app.exchange.base import Ticker


def _t(sym, last, open_, vol, funding=0.0):
    return Ticker(symbol=sym, last=last, open_utc=open_, quote_volume=vol, funding_rate=funding)


def test_overview_counts_and_tops():
    tks = [
        _t("BTCUSDT", 110, 100, 9e9, 0.0001),
        _t("ETHUSDT", 90, 100, 5e9, -0.0002),
        _t("AAAUSDT", 200, 100, 1e9, 0.004),
        _t("BBBUSDT", 80, 100, 2e9, -0.01),
    ]
    ov = build_market_overview(tks, top_n=2)
    assert ov.up_count == 2 and ov.down_count == 2 and ov.total == 4
    assert ov.btc.last == 110 and ov.eth.last == 90
    assert [c.symbol for c in ov.top_gainers] == ["AAAUSDT", "BTCUSDT"]
    assert [c.symbol for c in ov.top_losers] == ["BBBUSDT", "ETHUSDT"]
    assert [c.symbol for c in ov.top_volume] == ["BTCUSDT", "ETHUSDT"]
    assert ov.funding_high.symbol == "AAAUSDT" and ov.funding_low.symbol == "BBBUSDT"


def test_overview_empty_is_safe():
    ov = build_market_overview([])
    assert ov.total == 0 and ov.btc is None and ov.top_gainers == []
