# Phase 2 — Exchange Adapters + Market Data Plan

> Implement task-by-task (TDD). Steps use `- [ ]`. Builds on Phase 1.

**Goal:** Add the exchange boundary — `ExchangeAdapter` ABC + `Ticker`/`Fill`, a network-free-testable `PaperAdapter` (default), a `CcxtAdapter` for Bitget USDT-M (live/testnet), and a pure `build_market_overview` that reproduces the 시장 흐름 panel.

**Architecture:** `ExchangeAdapter` is the only thing the engine talks to. `PaperAdapter` wraps a market-data source (real Bitget public client in prod, a fake in tests) and simulates fills + virtual balance, so paper mode needs no keys and tests need no network. `build_market_overview` is a pure function over `list[Ticker]`.

**Tech Stack:** Python 3.11+, ccxt (async), pytest (+asyncio). Bitget field mapping per spec §19.0.

---

## File structure (Phase 2)

- Create `app/exchange/base.py` — `Ticker`, `Fill`, `ExchangeAdapter` ABC.
- Create `app/exchange/paper_adapter.py` — `PaperAdapter` (default).
- Create `app/exchange/ccxt_adapter.py` — `CcxtAdapter` (Bitget; imports ccxt).
- Create `app/exchange/__init__.py`, `app/engine/__init__.py`.
- Create `app/engine/market_overview.py` — `MarketOverview`, `build_market_overview`.
- Tests: `tests/test_exchange_base.py`, `tests/test_paper_adapter.py`, `tests/test_market_overview.py`.

---

## Task 1: `Ticker`/`Fill` + Bitget mapping

**Files:** Create `app/exchange/__init__.py`, `app/exchange/base.py`; Test `tests/test_exchange_base.py`.

- [ ] **Step 1 — failing test**

```python
from app.exchange.base import Ticker

def test_change_and_depth_from_bitget_fields():
    t = Ticker.from_bitget({"symbol": "BTCUSDT", "lastPr": "110", "openUtc": "100",
                            "bidPr": "109.5", "askPr": "110.5", "fundingRate": "0.0001",
                            "usdtVolume": "1000000"})
    assert t.last == 110.0 and t.open_utc == 100.0
    assert round(t.change_pct, 2) == 10.0
    assert round(t.depth_gap_pct, 4) == round((110.5 - 109.5) / 109.5 * 100, 4)
    assert t.quote_volume == 1000000.0
```

- [ ] **Step 2 — run, expect FAIL** (`ModuleNotFoundError: app.exchange.base`).
- [ ] **Step 3 — implement** `app/exchange/base.py` (Ticker dataclass with `change_pct`/`depth_gap_pct` props + `from_bitget`; `Fill` dataclass; `ExchangeAdapter` ABC with async `load_markets/fetch_ticker/fetch_tickers/fetch_ohlcv/fetch_balance/set_leverage/create_market_order/close`). Full code in execution.
- [ ] **Step 4 — run, expect PASS.**
- [ ] **Step 5 — commit** `feat: exchange base (Ticker/Fill/ABC) + bitget mapping`.

---

## Task 2: `PaperAdapter`

**Files:** Create `app/exchange/paper_adapter.py`; Test `tests/test_paper_adapter.py`.

- [ ] **Step 1 — failing test**

```python
import pytest
from app.exchange.base import Ticker
from app.exchange.paper_adapter import PaperAdapter

class FakeSource:
    def __init__(self, last): self._last = last; self.closed = False
    async def load_markets(self): return ["BTCUSDT", "ETHUSDT"]
    async def fetch_ticker(self, s): return Ticker(symbol=s, last=self._last)
    async def fetch_tickers(self): return [Ticker(symbol="BTCUSDT", last=self._last)]
    async def fetch_ohlcv(self, s, tf, limit=200): return [[0,1,2,0.5,1.5,10]]
    async def close(self): self.closed = True

async def test_balance_starts_and_adjusts():
    a = PaperAdapter(FakeSource(100.0), start_balance=10000.0)
    assert await a.fetch_balance() == 10000.0
    a.apply_realized_pnl(250.0)
    assert await a.fetch_balance() == 10250.0

async def test_fill_uses_source_price_with_slippage():
    a = PaperAdapter(FakeSource(100.0), slippage_pct=1.0)
    short_open = await a.create_market_order("BTCUSDT", "short", qty=2)
    long_open = await a.create_market_order("BTCUSDT", "long", qty=2)
    assert short_open.price == 99.0   # sell fills lower
    assert long_open.price == 101.0   # buy fills higher

async def test_reads_delegate_to_source():
    a = PaperAdapter(FakeSource(100.0))
    assert await a.load_markets() == ["BTCUSDT", "ETHUSDT"]
    assert (await a.fetch_ticker("ETHUSDT")).last == 100.0
```

- [ ] **Step 2 — run, expect FAIL.**
- [ ] **Step 3 — implement** `PaperAdapter(data_source, start_balance=10000.0, slippage_pct=0.0)`: delegate reads; `fetch_balance` returns virtual balance; `apply_realized_pnl`; `create_market_order` fills at `source.fetch_ticker(symbol).last` adjusted by slippage (buy higher / sell lower; buy = long-open or short-close).
- [ ] **Step 4 — run, expect PASS.**
- [ ] **Step 5 — commit** `feat: PaperAdapter (virtual balance + simulated fills)`.

---

## Task 3: `build_market_overview`

**Files:** Create `app/engine/__init__.py`, `app/engine/market_overview.py`; Test `tests/test_market_overview.py`.

- [ ] **Step 1 — failing test**

```python
from app.exchange.base import Ticker
from app.engine.market_overview import build_market_overview

def _t(sym, last, open_, vol, funding=0.0):
    return Ticker(symbol=sym, last=last, open_utc=open_, quote_volume=vol, funding_rate=funding)

def test_overview_counts_and_tops():
    tks = [_t("BTCUSDT",110,100,9e9,0.0001), _t("ETHUSDT",90,100,5e9,-0.0002),
           _t("AAAUSDT",200,100,1e9,0.004), _t("BBBUSDT",80,100,2e9,-0.01)]
    ov = build_market_overview(tks, top_n=2)
    assert ov.up_count == 2 and ov.down_count == 2 and ov.total == 4
    assert ov.btc.last == 110 and ov.eth.last == 90
    assert [c.symbol for c in ov.top_gainers] == ["AAAUSDT", "BTCUSDT"]
    assert [c.symbol for c in ov.top_losers] == ["BBBUSDT", "ETHUSDT"]
    assert [c.symbol for c in ov.top_volume] == ["BTCUSDT", "ETHUSDT"]
    assert ov.funding_high.symbol == "AAAUSDT" and ov.funding_low.symbol == "BBBUSDT"
```

- [ ] **Step 2 — run, expect FAIL.**
- [ ] **Step 3 — implement** `MarketOverview`/`CoinChange`/`CoinVolume` dataclasses + `build_market_overview(tickers, top_n=5)` (BTC/ETH pick, up/down counts via `change_pct`, avg change, avg volatility `mean(|change|)`, avg funding, funding high/low symbol, top gainers/losers by `change_pct`, top volume by `quote_volume`).
- [ ] **Step 4 — run, expect PASS.**
- [ ] **Step 5 — commit** `feat: build_market_overview (시장 흐름 aggregation)`.

---

## Task 4: `CcxtAdapter` (Bitget) + smoke import

**Files:** Create `app/exchange/ccxt_adapter.py`.

- [ ] **Step 1 — implement** `CcxtAdapter(api_key, secret, password, testnet=False)` over `ccxt.async_support.bitget` (`defaultType=swap`); `load_markets` → USDT swap symbols; `_map_ticker` from ccxt unified + `info`; orders map `short→sell`/`long→buy` (inverted when `reduce_only`); `set_sandbox_mode` on testnet. No network test — validated live in a later phase (never auto-live).
- [ ] **Step 2 — smoke import** `python -c "import app.exchange.ccxt_adapter"` → no error (after `pip install ccxt`).
- [ ] **Step 3 — full suite** `pytest -q` green.
- [ ] **Step 4 — commit** `feat: CcxtAdapter (Bitget USDT-M, live/testnet)`.

---

## Done criteria (Phase 2)
- `pytest -q` green (base + paper + market_overview; network-free).
- `app.exchange.ccxt_adapter` imports cleanly.
- `build_market_overview` reproduces 시장 흐름 panel fields; `PaperAdapter` gives real prices + simulated fills with no keys.

## Notes
- ccxt unified symbol vs Bitget raw `BTCUSDT` normalization refined in Phase 4 (engine wiring).
- Live order path remains gated (`execution_mode`/`execution_enabled`) — Phase 2 wires structure only.
