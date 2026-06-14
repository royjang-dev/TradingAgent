from fastapi.testclient import TestClient

from app.config import Config
from app.dashboard.server import create_app
from app.engine.trading_service import TradingService
from app.exchange.base import Ticker
from app.exchange.paper_adapter import PaperAdapter
from app.models import EntryType, Record, Side, TimeFrame, Wallet


class Src:
    async def fetch_ticker(self, s):
        return Ticker(s, 100.0)

    async def fetch_tickers(self):
        return []

    async def load_markets(self):
        return ["BTCUSDT"]

    async def fetch_ohlcv(self, s, tf, limit=200):
        return []

    async def close(self):
        pass


def _client():
    adapter = PaperAdapter(Src(), start_balance=10000.0)
    ts = TradingService(adapter, Config())
    ts.pm.positions[("BTCUSDT", "short")] = Wallet(
        name="BTCUSDT", side=Side.SHORT, entry_type=EntryType.BREAKOUT, timeframe=TimeFrame.D1,
        leverage=30, entry_price=100.0, entry_count=5.0, current_price=110.0,
    )
    ts.pm.records.append(Record(
        name="ETHUSDT", side=Side.SHORT, entry_type=EntryType.MEAN_REVERT, timeframe=TimeFrame.H1,
        entry_price=10.0, close_price=9.0, close_count=3.0, pnl=3.0, roe=30.0, split_count=1,
        trading_time="2026-06-11 10:00:00",
    ))
    return TestClient(create_app(service=ts, adapter=adapter, run_engine=False))


def test_index_served():
    assert _client().get("/").status_code == 200


def test_status_endpoint():
    st = _client().get("/api/status").json()
    assert st["trade_count"] == 1 and st["win_rate"] == 100.0 and st["position_count"] == 1
    assert st["total_pnl"] == 3.0 and st["mode"] == "paper"


def test_positions_and_records_endpoints():
    c = _client()
    pos = c.get("/api/positions").json()
    assert pos[0]["symbol"] == "BTCUSDT" and pos[0]["side"] == "short" and pos[0]["pnl"] < 0
    rec = c.get("/api/records").json()
    assert rec[0]["symbol"] == "ETHUSDT" and rec[0]["pnl"] == 3.0


def test_daily_market_config_endpoints():
    c = _client()
    daily = c.get("/api/daily").json()
    assert daily["labels"] == ["2026-06-11"] and daily["values"] == [3.0]
    assert daily["profit"] == [3.0] and "loss" in daily and "profit_roe" in daily and "loss_roe" in daily
    assert c.get("/api/market").json() == {}
    assert c.get("/api/config").json()["execution_mode"] == "paper"


def test_post_config_applies_and_diffs():
    c = _client()
    cur = c.get("/api/config").json()
    cur["mean_revert_target"]["short_usdt"] = 77.7
    cur["breakout_enabled"] = False
    r = c.post("/api/config", json=cur)
    assert r.status_code == 200
    changes = r.json()["changes"]
    assert any("USDT(Short)" in line for line in changes)
    assert any("Breakout 활성" in line for line in changes)
    assert c.get("/api/config").json()["mean_revert_target"]["short_usdt"] == 77.7
