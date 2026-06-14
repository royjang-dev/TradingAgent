# Phase 1 — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the data foundation of the Bitget futures bot — enums, models (`Wallet`/`Record`/`Signal`), config + strategy `Target` hierarchy with decoded sizing math, atomic JSON persistence, and original-format category/date logging — all test-covered.

**Architecture:** Pure-Python core with no network/exchange dependencies, so it is fully unit-testable. Pydantic v2 for config; plain dataclasses for runtime models; `Target.get_dynamic_split_gap` encodes the decoded `gap = SplitGap% × multiplier × n` formula; persistence writes `*.json` + `*.json.bak` atomically; logger emits `logs/<CATEGORY>/<YYYY_MM_DD>.txt` lines `[YYYY-MM-DD HH:MM:SS] message`.

**Tech Stack:** Python 3.11+, Pydantic v2, pytest. (Spec: `docs/2026-06-11-uprich-bot-python-design.md`.)

---

## File structure (Phase 1)

- Create `requirements.txt` — pinned deps.
- Create `pyproject.toml` — pytest config + package metadata.
- Create `app/__init__.py` — package marker.
- Create `app/models.py` — `Side`, `TimeFrame`, `EntryType`, `CloseReason` enums + `Signal`, `Wallet`, `Record` dataclasses.
- Create `app/config.py` — `Target` (+ `MeanRevertTarget`/`BreakoutTarget`/`UprichAgrtTarget`), `Config`; load/save.
- Create `app/persistence/__init__.py`.
- Create `app/persistence/store.py` — `JsonStore` atomic write-then-bak + read.
- Create `app/persistence/logger.py` — `FileLogger` original-format logs.
- Create `tests/__init__.py`, `tests/test_models.py`, `tests/test_config.py`, `tests/test_sizing.py`, `tests/test_persistence.py`, `tests/test_logger.py`.

All paths relative to `D:\uprich-bot-python\`.

---

## Task 1: Project setup

**Files:**
- Create: `requirements.txt`, `pyproject.toml`, `app/__init__.py`, `app/persistence/__init__.py`, `tests/__init__.py`

- [ ] **Step 1: Create `requirements.txt`**

```
pydantic>=2.6,<3
ccxt>=4.3
fastapi>=0.110
uvicorn[standard]>=0.29
httpx>=0.27
websockets>=12
pytest>=8
pytest-asyncio>=0.23
```

- [ ] **Step 2: Create `pyproject.toml`**

```toml
[project]
name = "uprich-bot-python"
version = "0.1.0"
requires-python = ">=3.11"

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
addopts = "-q"
```

- [ ] **Step 3: Create empty package markers**

Create `app/__init__.py`, `app/persistence/__init__.py`, `tests/__init__.py` each containing a single newline.

- [ ] **Step 4: Create venv + install**

Run: `python -m venv .venv; .\.venv\Scripts\python -m pip install -r requirements.txt`
Expected: installs without error; `pytest` available.

- [ ] **Step 5: Commit**

```bash
git init
git add requirements.txt pyproject.toml app/__init__.py app/persistence/__init__.py tests/__init__.py
git commit -m "chore: project skeleton + deps"
```

---

## Task 2: Enums + Signal model

**Files:**
- Create: `app/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the failing test**

```python
from app.models import Side, TimeFrame, EntryType, CloseReason, Signal

def test_enum_values():
    assert Side.SHORT.value == "short"
    assert Side.LONG.value == "long"
    assert TimeFrame.H1.value == "1h"
    assert EntryType.UPRICH_AGRT.value == "UprichAgrt"
    assert CloseReason.TRAILING_STOP.value == "TrailingStop"

def test_signal_holds_fields():
    s = Signal(symbol="BTCUSDT", side=Side.SHORT, strategy=EntryType.BREAKOUT,
               timeframe=TimeFrame.D1, ref_price=100.0, deviation_pct=30.0, reason="band")
    assert s.symbol == "BTCUSDT" and s.side is Side.SHORT and s.deviation_pct == 30.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.models'`.

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum


class Side(str, Enum):
    LONG = "long"
    SHORT = "short"


class TimeFrame(str, Enum):
    M1 = "1m"
    M15 = "15m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"


class EntryType(str, Enum):
    MEAN_REVERT = "MeanRevert"
    BREAKOUT = "Breakout"
    UPRICH_AGRT = "UprichAgrt"


class CloseReason(str, Enum):
    TRAILING_STOP = "TrailingStop"
    PROFIT = "Profit"
    STOP_LOSS = "StopLoss"
    REVERSE_EXIT = "ReverseExit"
    MANUAL = "Manual"
    REBALANCE = "Rebalance"


@dataclass
class Signal:
    symbol: str
    side: Side
    strategy: EntryType
    timeframe: TimeFrame
    ref_price: float
    deviation_pct: float
    reason: str = ""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add app/models.py tests/test_models.py
git commit -m "feat: enums + Signal model"
```

---

## Task 3: Wallet model (PnL/ROE)

**Files:**
- Modify: `app/models.py` (append `Wallet`)
- Test: `tests/test_models.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_models.py`:

```python
from app.models import Wallet

def _short_wallet():
    return Wallet(name="KATUSDT", side=Side.SHORT, entry_type=EntryType.BREAKOUT,
                  timeframe=TimeFrame.D1, leverage=10, entry_price=0.01968,
                  entry_count=1168.0, current_price=0.02212)

def test_wallet_pnl_short_loss():
    w = _short_wallet()
    # short: pnl = (entry - current) * qty
    assert round(w.calc_pnl(), 4) == round((0.01968 - 0.02212) * 1168.0, 4)

def test_wallet_roe_uses_leverage():
    w = _short_wallet()
    # roe% = (entry-current)/entry * leverage * 100  (short)
    expected = (0.01968 - 0.02212) / 0.01968 * 10 * 100
    assert round(w.calc_roe(), 2) == round(expected, 2)

def test_wallet_roundtrip_dict():
    w = _short_wallet()
    assert Wallet.from_dict(w.to_dict()).to_dict() == w.to_dict()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py -k wallet -v`
Expected: FAIL — `ImportError: cannot import name 'Wallet'`.

- [ ] **Step 3: Write minimal implementation**

Append to `app/models.py`:

```python
@dataclass
class Wallet:
    name: str
    side: Side
    entry_type: EntryType
    timeframe: TimeFrame
    leverage: int = 1
    entry_price: float = 0.0
    entry_count: float = 0.0
    current_price: float = 0.0
    last_entry_price: float = 0.0
    split_count: int = 1
    margin_mode: str = "crossed"
    target_price: float = 0.0
    min_profit: float = 0.0
    trailing_stop: float = 0.0
    stop_loss: float = 0.0
    support_line: float = 0.0
    resist_line: float = 0.0
    target_hit: bool = False
    bolinger_hit: bool = False
    is_time_rebalance: bool = False
    max_loss: float = 0.0
    max_profit: float = 0.0
    usdt_balance: float = 0.0
    trading_time: str = ""
    preset_stop_loss_order_id: str | None = None
    preset_take_profit_order_id: str | None = None
    tracking_no: int = 0

    def _dir(self) -> int:
        return 1 if self.side is Side.SHORT else -1

    def calc_pnl(self) -> float:
        return self._dir() * (self.entry_price - self.current_price) * self.entry_count

    def calc_roe(self) -> float:
        if self.entry_price == 0:
            return 0.0
        return self._dir() * (self.entry_price - self.current_price) / self.entry_price * self.leverage * 100

    def is_valid(self) -> bool:
        return bool(self.name) and self.entry_price > 0 and self.entry_count > 0

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["side"] = self.side.value
        d["entry_type"] = self.entry_type.value
        d["timeframe"] = self.timeframe.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Wallet":
        d = dict(d)
        d["side"] = Side(d["side"])
        d["entry_type"] = EntryType(d["entry_type"])
        d["timeframe"] = TimeFrame(d["timeframe"])
        return cls(**d)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_models.py -k wallet -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add app/models.py tests/test_models.py
git commit -m "feat: Wallet model with pnl/roe + dict roundtrip"
```

---

## Task 4: Record model (from_wallet)

**Files:**
- Modify: `app/models.py` (append `Record`)
- Test: `tests/test_models.py` (append)

- [ ] **Step 1: Write the failing test**

```python
from app.models import Record

def test_record_from_wallet_captures_close():
    w = _short_wallet()
    r = Record.from_wallet(w, close_price=0.0194832)
    assert r.name == "KATUSDT" and r.side is Side.SHORT
    assert r.entry_price == 0.01968 and r.close_price == 0.0194832
    # short profit since close < entry
    assert r.pnl > 0 and r.roe > 0

def test_record_roundtrip_dict():
    r = Record.from_wallet(_short_wallet(), close_price=0.0194832)
    assert Record.from_dict(r.to_dict()).to_dict() == r.to_dict()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py -k record -v`
Expected: FAIL — `ImportError: cannot import name 'Record'`.

- [ ] **Step 3: Write minimal implementation**

Append to `app/models.py`:

```python
@dataclass
class Record:
    name: str
    side: Side
    entry_type: EntryType
    timeframe: TimeFrame
    entry_price: float
    close_price: float
    close_count: float
    pnl: float
    roe: float
    split_count: int
    max_loss: float = 0.0
    max_profit: float = 0.0
    entry_time: str = ""
    trading_time: str = ""

    @classmethod
    def from_wallet(cls, w: "Wallet", close_price: float) -> "Record":
        closed = Wallet(**{**w.__dict__})
        closed.current_price = close_price
        return cls(
            name=w.name, side=w.side, entry_type=w.entry_type, timeframe=w.timeframe,
            entry_price=w.entry_price, close_price=close_price, close_count=w.entry_count,
            pnl=closed.calc_pnl(), roe=closed.calc_roe(), split_count=w.split_count,
            max_loss=w.max_loss, max_profit=w.max_profit, trading_time=w.trading_time,
        )

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["side"] = self.side.value
        d["entry_type"] = self.entry_type.value
        d["timeframe"] = self.timeframe.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Record":
        d = dict(d)
        d["side"] = Side(d["side"])
        d["entry_type"] = EntryType(d["entry_type"])
        d["timeframe"] = TimeFrame(d["timeframe"])
        return cls(**d)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_models.py -k record -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add app/models.py tests/test_models.py
git commit -m "feat: Record model + from_wallet"
```

---

## Task 5: Target hierarchy + decoded sizing

**Files:**
- Create: `app/config.py`
- Test: `tests/test_sizing.py`

- [ ] **Step 1: Write the failing test**

```python
from app.config import Target, BreakoutTarget
from app.models import Side

def _t(**kw):
    base = dict(target_name="UprichAgrt", long_usdt=58.2, short_usdt=58.2,
                long_leverage=30, short_leverage=30, long_split_cnt=1, short_split_cnt=1,
                long_split_gap=30.0, short_split_gap=30.0,
                long_auto_input_ctrl=300.0, short_auto_input_ctrl=300.0,
                split_squared_enabled=True, split_interval_multiplier=6.0, split_multiplier_start_at=1)
    base.update(kw)
    return Target(**base)

def test_qty_from_usdt_leverage():
    t = _t()
    # qty = usdt * leverage / price
    assert round(t.qty("short", price=0.04383), 2) == round(58.2 * 30 / 0.04383, 2)

def test_dynamic_split_gap_matches_ui_preview():
    t = _t()  # 30 * 6 * n
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_sizing.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.config'`.

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations
from pydantic import BaseModel


class Target(BaseModel):
    target_name: str = ""
    long_usdt: float = 0.0
    short_usdt: float = 0.0
    long_leverage: int = 1
    short_leverage: int = 1
    long_position_cnt: int = 1
    short_position_cnt: int = 1
    long_split_cnt: int = 1
    short_split_cnt: int = 1
    long_split_gap: float = 0.0
    short_split_gap: float = 0.0
    long_split_add: float = 0.0
    short_split_add: float = 0.0
    long_auto_input_ctrl: float = 0.0
    short_auto_input_ctrl: float = 0.0
    profit: float = 0.0
    stop_loss: float = 0.0
    trailing_stop: float = 0.0
    min_profit: float = 0.0
    trailing_stop_use: bool = True
    profit_use: bool = False
    stop_loss_use: bool = False
    reverse_exit: bool = True
    long_open_skip: bool = False
    short_open_skip: bool = False
    funding_fee_check_enabled: bool = False
    split_squared_enabled: bool = True
    split_interval_multiplier: float = 1.0
    split_multiplier_start_at: int = 1

    def _g(self, side: str, long_val, short_val):
        return long_val if side == "long" else short_val

    def get_usdt(self, side: str) -> float:
        return self._g(side, self.long_usdt, self.short_usdt)

    def get_leverage(self, side: str) -> int:
        return self._g(side, self.long_leverage, self.short_leverage)

    def get_split_cnt(self, side: str) -> int:
        return self._g(side, self.long_split_cnt, self.short_split_cnt)

    def get_split_gap(self, side: str) -> float:
        return self._g(side, self.long_split_gap, self.short_split_gap)

    def is_open_skip(self, side: str) -> bool:
        return self._g(side, self.long_open_skip, self.short_open_skip)

    def qty(self, side: str, price: float) -> float:
        if price <= 0:
            return 0.0
        return self.get_usdt(side) * self.get_leverage(side) / price

    def get_dynamic_split_gap(self, side: str, n: int) -> float:
        base = self.get_split_gap(side)
        if self.split_squared_enabled and n >= self.split_multiplier_start_at:
            return base * self.split_interval_multiplier * n
        return base


class MeanRevertTarget(Target):
    long_use_1m: bool = False
    long_use_15m: bool = False
    long_use_1h: bool = True
    long_use_4h: bool = True
    short_use_1m: bool = False
    short_use_15m: bool = False
    short_use_1h: bool = True
    short_use_4h: bool = True
    long_standard_1h: float = 0.0
    long_standard_4h: float = 0.0
    short_standard_1h: float = 0.0
    short_standard_4h: float = 0.0
    volatility_1h: float = 0.0
    volatility_4h: float = 0.0
    funding_filter_enabled: bool = False
    long_max_funding_rate: float = 0.1
    short_max_funding_rate: float = 0.1
    depth_gap_filter_enabled: bool = False
    max_depth_gap: float = 0.7


class BreakoutTarget(Target):
    use_1h: bool = True
    use_4h: bool = True
    use_1d: bool = True
    volatility_1h: float = 0.0
    volatility_4h: float = 0.0
    volatility_1d: float = 0.0
    funding_filter_enabled: bool = False
    depth_gap_filter_enabled: bool = False
    max_depth_gap: float = 0.7


class UprichAgrtTarget(MeanRevertTarget):
    long_volatility_1h: float = 0.0
    long_volatility_4h: float = 0.0
    short_volatility_1h: float = 0.0
    short_volatility_4h: float = 0.0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_sizing.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add app/config.py tests/test_sizing.py
git commit -m "feat: Target hierarchy + decoded sizing (qty, dynamic split gap)"
```

---

## Task 6: Config load/save

**Files:**
- Modify: `app/config.py` (append `Config` + `load_config`/`save_config`)
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
import json
from app.config import Config, load_config, save_config

def test_config_defaults_paper_and_disabled():
    c = Config()
    assert c.execution_mode == "paper"
    assert c.execution_enabled is False

def test_config_roundtrip(tmp_path):
    c = Config(selected_symbols=["BTCUSDT", "ETHUSDT"])
    c.uprich_agrt_target.short_usdt = 58.2
    p = tmp_path / "config.json"
    save_config(c, p)
    loaded = load_config(p)
    assert loaded.selected_symbols == ["BTCUSDT", "ETHUSDT"]
    assert loaded.uprich_agrt_target.short_usdt == 58.2
    assert loaded.execution_mode == "paper"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL — `ImportError: cannot import name 'Config'`.

- [ ] **Step 3: Write minimal implementation**

Append to `app/config.py`:

```python
import json
from pathlib import Path
from typing import Literal
from pydantic import Field


class Config(BaseModel):
    selected_symbols: list[str] = Field(default_factory=list)
    use_two_way_trading: bool = True
    use_fixed_trade: bool = False
    mean_revert_target: MeanRevertTarget = Field(default_factory=lambda: MeanRevertTarget(target_name="MeanRevert"))
    breakout_target: BreakoutTarget = Field(default_factory=lambda: BreakoutTarget(target_name="Breakout"))
    uprich_agrt_target: UprichAgrtTarget = Field(default_factory=lambda: UprichAgrtTarget(target_name="UprichAgrt"))
    enable_console_log: bool = True
    enable_file_log: bool = True
    log_path: str = "logs"
    profit_close_filter_enabled: bool = False
    execution_mode: Literal["paper", "testnet", "live"] = "paper"
    execution_enabled: bool = False


def load_config(path: str | Path) -> Config:
    return Config.model_validate_json(Path(path).read_text(encoding="utf-8"))


def save_config(config: Config, path: str | Path) -> None:
    Path(path).write_text(config.model_dump_json(indent=2), encoding="utf-8")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add app/config.py tests/test_config.py
git commit -m "feat: Config load/save (paper default, execution disabled)"
```

---

## Task 7: Atomic JSON persistence (write-then-bak)

**Files:**
- Create: `app/persistence/store.py`
- Test: `tests/test_persistence.py`

- [ ] **Step 1: Write the failing test**

```python
from app.persistence.store import JsonStore

def test_save_creates_file_and_reads_back(tmp_path):
    store = JsonStore(tmp_path / "wallets.json")
    data = [{"name": "BTCUSDT", "side": "short"}]
    store.save(data)
    assert store.load() == data

def test_second_save_creates_bak_of_previous(tmp_path):
    path = tmp_path / "records.json"
    store = JsonStore(path)
    store.save([{"v": 1}])
    store.save([{"v": 2}])
    assert store.load() == [{"v": 2}]
    bak = JsonStore(path.with_suffix(".json.bak"))
    assert bak.load() == [{"v": 1}]

def test_load_missing_returns_default(tmp_path):
    store = JsonStore(tmp_path / "none.json")
    assert store.load(default=[]) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_persistence.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.persistence.store'`.

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations
import json
import os
import tempfile
from pathlib import Path
from typing import Any


class JsonStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.bak = self.path.with_suffix(self.path.suffix + ".bak")

    def load(self, default: Any = None) -> Any:
        if not self.path.exists():
            return default
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, data: Any) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            self.bak.write_text(self.path.read_text(encoding="utf-8"), encoding="utf-8")
        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_persistence.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add app/persistence/store.py tests/test_persistence.py
git commit -m "feat: atomic JSON store with .bak sibling"
```

---

## Task 8: Original-format file logger

**Files:**
- Create: `app/persistence/logger.py`
- Test: `tests/test_logger.py`

- [ ] **Step 1: Write the failing test**

```python
import re
from app.persistence.logger import FileLogger

def test_writes_category_date_file(tmp_path):
    log = FileLogger(base=tmp_path, now=lambda: "2026-06-11 16:55:34")
    log.write("TRADE", "MR USDT(Long): 29.1 -> 58.3")
    f = tmp_path / "TRADE" / "2026_06_11.txt"
    assert f.exists()
    line = f.read_text(encoding="utf-8").strip()
    assert line == "[2026-06-11 16:55:34] MR USDT(Long): 29.1 -> 58.3"

def test_appends_multiple_lines(tmp_path):
    log = FileLogger(base=tmp_path, now=lambda: "2026-06-11 16:55:34")
    log.write("DATA", "심볼 서칭 완료: 520개 (45731ms)")
    log.write("DATA", "TargetsManager: Breakout Target 업데이트")
    f = tmp_path / "DATA" / "2026_06_11.txt"
    assert len(f.read_text(encoding="utf-8").strip().splitlines()) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_logger.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.persistence.logger'`.

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Callable


def _default_now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class FileLogger:
    def __init__(self, base: str | Path = "logs", now: Callable[[], str] = _default_now,
                 console: bool = False):
        self.base = Path(base)
        self.now = now
        self.console = console

    def write(self, category: str, message: str) -> None:
        ts = self.now()
        date = ts[:10].replace("-", "_")
        folder = self.base / category
        folder.mkdir(parents=True, exist_ok=True)
        line = f"[{ts}] {message}"
        with (folder / f"{date}.txt").open("a", encoding="utf-8") as f:
            f.write(line + "\n")
        if self.console:
            print(line)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_logger.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Run the full suite + commit**

Run: `pytest -q`
Expected: all pass (~16 tests).

```bash
git add app/persistence/logger.py tests/test_logger.py
git commit -m "feat: original-format category/date file logger"
```

---

## Done criteria (Phase 1)

- `pytest -q` green (models, sizing, config, persistence, logger).
- `Target.get_dynamic_split_gap` reproduces the UI preview `360/540/720/900`.
- `Wallet.calc_pnl/roe` reproduce sign + leverage (short loss when price rises).
- `JsonStore` leaves a `.bak` of the prior version; logger writes `logs/<CAT>/<YYYY_MM_DD>.txt`.

## Next phases (separate plans)
2. Exchange adapters (PaperAdapter + Bitget CcxtAdapter) + market data + market_overview.
3. Strategies (indicators + decoded entry/exit + sizing wiring).
4. Engine (scanner + trading_service + position_manager + trailing + targets_manager + event_bus).
5. Dashboard (FastAPI + 6 views + WebSocket + Chart.js, de-branded).
6. Telegram + optional risk guards + README (tail-risk warning).
