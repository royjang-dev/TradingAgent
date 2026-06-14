# UPRICH-style Futures Bot (Python) — Design Spec

- Date: 2026-06-11
- Status: DESIGN (pre-implementation)
- Target dir: `D:\uprich-bot-python\`
- Source of truth: static analysis of `UPRICH FUTURE BOT V1.5.4` + live UI screenshots (12) + `config.json` / `SAVE/*.json` / `logs/`

---

## 0. Context & honesty caveat

This is a **functional reimplementation** of the observable behavior and UI of UPRICH FUTURE BOT v1.5.4 in Python. It is **de-branded** (no UPRICH logo/branding in the UI, per operator).

The original's **strategy signal math is obfuscated** (commercial .NET protector; method bodies are IL stubs and were never recovered). Therefore:

- **Faithfully replicated** (from metadata/observation): architecture, `config.json` schema, data models, order lifecycle, split/martingale sizing, dynamic split-gap formula, trailing-stop exit, persistence format, log vocabulary, 6-view dashboard layout, settings hot-reload (`TargetsManager`), market-overview composition.
- **Reconstructed best-effort** (NOT identical to proprietary formulas): each strategy's entry/exit *signal* decision. Implemented behind a **pluggable `Strategy` interface** so the operator can replace any signal with their own without touching the engine.

No claim of byte-identical strategy behavior is made.

---

## 1. Goals / Non-goals

### Goals
1. Bitget USDT-M (mix) futures bot via ccxt `bitget`, 3 strategies: `MeanRevert`, `Breakout`, `UprichAgrt`. (Exchange corrected Binance → **Bitget**; evidence in §19.0.)
2. Same `config.json` schema and parameters (leverage, USDT/테더, 자동투입금, split, TP/SL, funding filter, rebalance…).
3. Order lifecycle = signal → size/gate → entry → split-add → trailing → close → record, with identical log lines.
4. Split/martingale sizing incl. dynamic gap `gap(n) = SplitGap% × SplitIntervalMultiplier × n`.
5. Web dashboard (FastAPI) reproducing the 6 views (대시보드/포지션/심볼/거래기록/설정/로그) exactly, dark theme, real-time.
6. **Paper trading by default**; testnet and live as explicit opt-ins.
7. Persistence (`SAVE/wallets.json`, `records.json` + `.bak`) and category/date logs in original format.
8. Telegram notifications, settings hot-reload (`TargetsManager`), market-overview panel.

### Non-goals
- Exact clone of proprietary signal math.
- License/trial/activation system (original had it; not reproduced).
- Auto-live trading without explicit operator opt-in.
- Embedding real API keys anywhere in code or `config.json`.

---

## 2. Tech stack

Python 3.11+, `asyncio`, `ccxt` (async), FastAPI + Uvicorn, Pydantic v2, `websockets`, `httpx`, Chart.js (dashboard, CDN), `pytest`. JSON file persistence. No DB.

---

## 3. Architecture — single async process

```
                +-------------------- TradingService (orchestrator) --------------------+
                |                                                                        |
 config.json -> Config -> InitializeAsync                                  events ->  EventBus (asyncio)
   .env keys                |                                                   |          |
                            v                                                   |          v
 Scanner loop (~scan-complete cadence, ~520 symbols)                           |    Dashboard (FastAPI + WS)
   for each enabled Strategy x symbol:                                          |          ^
     evaluate_entry / should_add / evaluate_exit  --(Signal)-->  Sizing  --> Order --> ExchangeAdapter
                                                                     |                   (paper|ccxt)
                                                              PositionManager (Wallet) --+
                                                                     |                    -> Persistence (SAVE/, logs/)
                                                              Trailing / Risk             -> Telegram
 TargetsManager: settings save -> update Targets -> auto-activate -> DATA log
```

One process hosts the engine (asyncio tasks) and the FastAPI dashboard. Engine emits events on an in-process bus; the dashboard subscribes and pushes to the browser over WebSocket.

---

## 4. Project layout

```
D:\uprich-bot-python\
  pyproject.toml | requirements.txt
  config.example.json        # full schema, placeholder values
  .env.example               # BINANCE_KEY / BINANCE_SECRET / TELEGRAM_* (never committed real)
  README.md                  # incl. tail-risk warning (no-stop-loss martingale)
  app/
    main.py                  # boot engine + dashboard
    config.py                # Config, Target, MeanRevertTarget, BreakoutTarget, UprichAgrtTarget (Pydantic)
    models.py                # Wallet, Record, Signal, enums
    exchange/
      base.py                # ExchangeAdapter ABC
      ccxt_adapter.py        # live + testnet (ccxt.binanceusdm)
      paper_adapter.py       # public data + simulated fills/balance  (DEFAULT)
    strategies/
      base.py                # Strategy ABC + registry
      indicators.py          # MA, stdev/vol, deviation%, ATR, bollinger, 이탈율
      mean_revert.py         # RECONSTRUCTED
      breakout.py            # RECONSTRUCTED
      uprich_agrt.py         # RECONSTRUCTED
    engine/
      scanner.py             # universe load + per-symbol scan loop
      trading_service.py     # orchestrator + events
      sizing.py              # qty, splits, GetDynamicSplitGap
      position_manager.py    # Wallet lifecycle, adds, max positions
      trailing.py            # trailing stop / min-profit / reverse exit
      risk.py                # OPTIONAL guards (off by default)
      targets_manager.py     # settings hot-reload + auto-activate
      market_overview.py     # 시장 흐름 aggregation
      event_bus.py           # asyncio pub/sub
    persistence/
      store.py               # atomic write-then-bak (wallets/records)
      logger.py              # category/date file logs in original format
    notify/telegram.py
    dashboard/
      server.py              # FastAPI app + WS broadcast
      routes.py              # REST: positions/records/logs/settings/market/symbols/start/stop
      static/                # index.html + app.js + styles.css (dark, de-branded, Chart.js)
  tests/
    test_config.py test_sizing.py test_strategies.py
    test_paper_engine.py test_persistence.py test_market_overview.py test_targets_manager.py
  docs/
    2026-06-11-uprich-bot-python-design.md   # this file
```

---

## 5. Config schema (`config.json`)

Mirrors the original `Config` model. Exchange credentials — Bitget `AccessKey` + `SecretKey` + **`Passphrase`** — live in `.env`, NOT here.

Top level: `SelectedSymbols`, `UseTwoWayTrading`, `UseFixedTrade`, `MeanRevertTarget`, `BreakoutTarget`, `UprichAgrtTarget`, `EnableConsoleLog`, `EnableFileLog`, `LogPath`, `ProfitCloseFilterEnabled`, plus new: `execution_mode` (`paper`|`testnet`|`live`, default `paper`), `execution_enabled` (default `false`), `risk_guards` (object, all off by default).

Per-strategy `Target` params (observed live values shown as example, operator-editable):
`TargetName`, `Long/ShortUSDT` (테더, e.g. 58.2), `Long/ShortLeverage` (e.g. 30), `Long/ShortPositionCnt` (최대 포지션, e.g. 1), `Long/ShortSplitCnt` (분할 횟수, e.g. 1), `Long/ShortSplitGap` (분할 간격 %, e.g. 30), `Long/ShortSplitAdd` (분할 추가 %, e.g. 0), `Long/ShortAutoInputCtrl` (자동투입금, e.g. 300), `Profit`/`StopLoss`/`TrailingStop`/`MinProfit`, toggles (`TrailingStopUse`, `ProfitUse`, `StopLossUse`, `ReverseExit`, funding/isolated/rebalance), `SplitSquaredEnabled`, `SplitIntervalMultiplier` (배율, e.g. 6), `SplitMultiplierStartAt` (시작 차수, e.g. 1), timeframe enables + `Standard`/`Volatility` bands.

Direction structure (confirmed from screenshots):
- `MeanRevertTarget`, `UprichAgrtTarget`: **Long + Short** (two-column UI).
- `BreakoutTarget`: **single-direction** (short-only in practice; `LongOpenSkip`).

Risk-mode presets (`공격적 / 일반적 / 안정적 / 커스텀`) = named parameter bundles applied to the Targets; `커스텀` keeps operator values.

---

## 6. Data models

- `enums`: `Side{LONG,SHORT}`, `TimeFrame{M1,M15,H1,H4,D1}`, `EntryType{MeanRevert,Breakout,UprichAgrt}`, `CloseReason{TrailingStop,Profit,StopLoss,ReverseExit,Manual,Rebalance}`.
- `Target` (+ 3 subclasses): params above + sizing methods `get_usdt(side)`, `get_leverage(side)`, `get_split_cnt(side)`, `get_split_gap(side)`, `get_dynamic_split_gap(side, n)`, `is_open_skip(side)`.
- `Wallet` (live position): name, side, margin_mode, entry_type, timeframe, leverage, entry_count, split_count, entry_price, current_price, last_entry_price, target_price, min_profit, trailing_stop, stop_loss, current_pnl, current_roe, usdt_balance, max_loss, max_profit, target_hit, trading_time, preset order ids. `is_valid()`, `calc_roe()`, `calc_pnl()`.
- `Record` (closed trade): name, side, entry_type, timeframe, entry_price, close_price, close_count, pnl, roe, split_count, max_loss, max_profit, entry_time, trading_time. `Record.from_wallet(wallet, close_price)`.
- `Signal`: symbol, side, strategy, timeframe, ref_price, deviation_pct (이탈율), reason.

---

## 7. Strategy plugin model + decoded logic

`Strategy` ABC (registry by `EntryType`):
- `evaluate_entry(symbol, market) -> Signal | None`
- `should_add(wallet, market) -> bool`
- `evaluate_exit(wallet, market) -> CloseReason | None`

`market` = OHLCV per timeframe + Bitget ticker (`lastPr`, `markPrice`, `indexPrice`, `openUtc`, `fundingRate`, `bid/askPr`, `usdtVolume`).

Indicators (`indicators.py`): SMA/EMA, **Bollinger Bands**, **support/resistance** (swing/pivot), rolling volatility%, deviation% (`이탈율 = (lastPr − ref)/ref × 100`), ATR%, funding & depth-gap helpers.

**Core thesis (decoded — §19):** all three strategies are **overextension fades** — short a coin that pierced its upper Bollinger band / `ResistLine` with `이탈율 ≥ Volatility{tf}%`; long the symmetric oversold case. In the observed market almost every entry was a short on a pumped small-cap alt. Entry *pipeline* and *exit mechanics* are decoded HIGH confidence; the exact band/threshold formula is MEDIUM (tunable, pluggable).

- **MeanRevert**: symmetric Long/Short `Standard{tf}` + shared `Volatility{tf}` across enabled `1m/15m/1h/4h`.
- **UprichAgrt**: same but **separate `Long/ShortVolatility{tf}`** (asymmetric bands).
- **Breakout**: fades larger moves on `1h/4h/1d`, higher `Volatility{tf}` (`이탈율` ~30% observed); short-only (`LongOpenSkip`).
- **Exit (all):** decoded price-level trailing (§19.3) — arm at `MinProfit%` (`TargetHit`), trail at `best × (1 ± Trailing%)`, exit on cross; no hard stop unless `StopLossUse`. Default config → every close is `[TrailingStop]` and losers are bag-held.

Full evidence, formulas and confidence in §19–§20. Each reconstructed signal method is annotated with its confidence and is overridable via the registry.

---

## 8. Sizing & splits (faithful)

- `qty = (USDT × Leverage) / price` (matches logged quantities, e.g. 2.2×10/price; 30x at live scale).
- `AutoInputCtrl` (자동투입금) acts as the per-cycle auto-sizing budget cap.
- Splits: up to `SplitCnt` entries spaced by `SplitGap%`; add fires when adverse gap reaches threshold (`should_add`).
- **Dynamic gap (confirmed from settings preview)**: for split index `n ≥ SplitMultiplierStartAt`,
  `gap(n) = SplitGap% × SplitIntervalMultiplier × n` → with 30×6: `2차=360, 3차=540, 4차=720, 5차=900` (%). Gated by `SplitSquaredEnabled`.
- `PositionCnt` (최대 포지션) caps concurrent positions per direction.

---

## 9. Engine

- **Scanner**: load symbol universe via `load_all_symbols` (~520 Binance USDT-M perps observed). Cadence = **scan-complete → next cycle** (one full sweep ~45.7s for 520 symbols observed; logged as `심볼 서칭 완료: N개 (Xms)`), not a fixed 60s timer.
- **TradingService** (orchestrator) — methods: `initialize_async(config)->bool`, `test_connection(key,secret)->(ok,msg,balance)`, `start_trading()`, `stop_trading()`, `close_all_positions()`, `close_position(symbol,side)`, `refresh_balance()`, `refresh_positions()`, `update_target(target)`, `load_all_symbols()`, `get_market_overview()`. Props: `is_initialized`, `is_running`, `is_server_banned`. Events: `status_updated`, `positions_updated(list[Wallet])`, `log_received`, `error_occurred`, `trade_executed`, `initialization_completed(bool)`, `auto_input_updated(long, short, total)`.
- **PositionManager**: Wallet open/add/close, max-position enforcement, mark-to-market.
- **Trailing**: trailing stop, min-profit floor, reverse-exit.
- **Risk** (OPTIONAL, default OFF for fidelity): hard stop-loss, daily loss limit, liquidation buffer. README documents the measured tail risk (live open bag reached −4,452% ROE; realized +$11,015 vs unrealized −$10,804 ≈ net +$212).
- **TargetsManager**: on settings save → diff + `TRADE` log lines (`MR USDT(Long): 29.1 -> 58.3` …) → update Targets → auto-activate → `DATA` log (`TargetsManager: X Target 업데이트`, `… 완료 (자동 활성화)`).

---

## 10. Exchange adapters

`ExchangeAdapter` ABC: `klines`, `ticker`, `funding_rate`, `markets/universe`, `balance`, `positions`, `set_leverage`, `create_order`, `close_position`.

- `PaperAdapter` (**default**): real public market data via ccxt (no auth) + simulated fills at signal price (configurable slippage), virtual balance, virtual positions. Dashboard/records behave identically without real money.
- `CcxtAdapter`: `ccxt.async_support.bitget` (USDT-M mix, `productType=USDT-FUTURES`), `testnet` or `live` via `execution_mode`. Needs AccessKey + SecretKey + **Passphrase**; price/qty rounding via `pricePlace`/`volumePlace`/`priceEndStep`, min size via `minTradeNum`/`sizeMultiplier`. Live also requires `execution_enabled=true` + keys in `.env` + startup warning acknowledgement.

---

## 11. Persistence & logging

- `SAVE/wallets.json` (live `Wallet[]`) and `SAVE/records.json` (closed `Record[]`), each with atomic write-then-`.bak` sibling.
- Logs: `logs/{DATA,TRADE,ERROR,WARN,INFO}/YYYY_MM_DD.txt`, line format `[YYYY-MM-DD HH:MM:SS] message`.
- Log vocabulary identical to original: `매매 감지`, `… 진입 … 이탈율=…%`, `포지션 등록`, `체결 확인`, `추가매수 감지`, `추가 진입 N차`, `분할매수 체결 #N`, `… 청산 … [TrailingStop]`, `거래 기록 … 수익률 …% / … USDT`, `포지션 삭제`, `청산 완료`, `[설정 저장] N건 변경`, `TargetsManager: …`, `심볼 서칭 완료: N개 (Xms)`.

---

## 12. Dashboard (web) — 6 views, exact

Dark theme (bg `#0c0d11`, panels `#15161c`, borders `#20222b`; accents teal `#2fd4bf`, green `#34d399`, blue `#5b8def`, gold `#d8a72e`, red `#f15668`). **De-branded**: sidebar starts at the menu (no UPRICH logo); titlebar carries no UPRICH text. Real-time via WebSocket.

Sidebar: `대시보드 / 포지션 / 심볼 / 거래 기록 / 설정 / 로그` + bottom `STOP`.

1. **대시보드**: 4 KPI cards (잔고+가용 / 누적 수익금+거래수 / 누적 수익률+승률 / 포지션+주문) · 일별 수익 차트 (Chart.js bar + cumulative line, date range) · 시장 흐름 (top row: BTC/ETH+range, 시장 심리 [상승/하락·전체·평균], 시장 변동성 [높음 avg·일일], 펀딩비 [평균·최고·최저]; bottom row: Top 상승 / Top 하락 / Top 거래량, 5 each). (Tech-support panel = de-branded out or replaced with a generic info card.)
2. **포지션**: `Running` badge + Margin% + table (심볼·전략·방향·수량·진입가·현재가·손익·수익률·배율·분할·TF·진입 시간) + buttons (선택코인 매도 / 지갑에서 삭제 / 전체 청산).
3. **심볼** *(inferred — actual screen not provided)*: universe selection from `SymbolSelectViewModel` recovered symbols — 전체선택/해제, Top20, per-symbol toggle, 확인/취소, ~520-symbol list with 24h change/volume. Will be corrected when the real screen is supplied.
4. **거래 기록**: 4 KPI (총 손익+trades / 오늘 손익 / 승률 W·L / 평균 수익률 + Max·Min) + filter dropdown + 선택 삭제 + table (심볼·방향·진입가·청산가·수량·손익·수익률·분할·타입·TF·진입/청산 시간).
5. **설정**: API panel (Secret Key + Connected+balance + API 연결 / 잔액 새로고침) · 리스크 모드 (공격적/일반적/안정적/커스텀) · 전략 탭 (MeanRevert/Breakout/UprichAgrt) + enable toggles · 매매 설정 (롱/숏 two-column for MR/UA; single for BO) · 익절/손절 (익절/손절/트레일링/최소수익 + toggles incl. 격리 마진 OFF=교차) · 분할 간격 배율 (제곱·배율·시작 차수 + Long/Short preview) · buttons (라이센스 교체 / 기술지원모드 / Reset / Save). License/tech-support buttons may be de-branded or repurposed.
6. **로그**: 시간·카테고리·메시지 + 카테고리 filter + count + category badges (TRADE/DATA/ERROR/WARN/INFO).

Market-overview computation (each refresh, from ~520 tickers): BTC/ETH price+24h±+high/low; sentiment = up/down counts, %up, avg |Δ|; volatility = avg |24h Δ| & daily range; funding = avg + max/min symbol; Top 상승/하락 = sort by 24h Δ; Top 거래량 = sort by quote volume.

---

## 13. Telegram

Optional `TelegramNotifier` on `trade_executed` / `error_occurred` (entry, close+PnL, error). `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` via `.env`.

---

## 14. Safety posture

- `execution_mode=paper` default. `testnet`/`live` are opt-in. `live` additionally requires `execution_enabled=true` + `.env` keys + explicit startup warning acknowledgement.
- API keys ONLY in `.env`; never in `config.json`, code, or logs.
- Optional risk guards (hard stop / daily loss / liq buffer) OFF by default to stay faithful; README documents the measured no-stop-loss tail risk and how to enable guards.
- De-branded UI.

---

## 15. Testing (pytest, no network)

- `test_config`: load/save roundtrip, schema, presets.
- `test_sizing`: qty, splits, `get_dynamic_split_gap` (30×6 → 360/540/720/900).
- `test_strategies`: entry/exit/should_add on synthetic candles.
- `test_paper_engine`: E2E signal → fill → split → trailing → close → record on PaperAdapter.
- `test_persistence`: atomic write-then-bak, log format.
- `test_market_overview`: aggregation on a mock ticker set.
- `test_targets_manager`: settings-save diff → target update → auto-activate logs.

---

## 16. Run

```
pip install -r requirements.txt
cp config.example.json config.json        # edit params
cp .env.example .env                       # keys (only needed for testnet/live)
python -m app.main                         # engine + dashboard at http://localhost:8000
```

---

## 17. Open items

- 심볼 view is inferred (actual screenshot not yet provided) — adjust on receipt.
- Exchange resolved to **Bitget** (§19.0); the earlier "Binance" call is corrected.
- Exit / sizing / lifecycle = HIGH confidence (§20). Exact *entry* band formula (`Standard{tf}` meaning, Bollinger period/mult, S/R calc) = MEDIUM — tune against paper results; pluggable for operator replacement.

---

## 18. Build phases (for the implementation plan)

1. Skeleton: config + models + enums + persistence + logger (+ tests).
2. Exchange adapters (PaperAdapter first) + market data + market_overview.
3. Strategies + indicators + sizing (+ tests).
4. Engine: scanner + trading_service + position_manager + trailing + targets_manager + event_bus → paper E2E.
5. Dashboard: FastAPI + 6 views + WebSocket + Chart.js (de-branded).
6. Telegram + optional risk guards + README (tail-risk warning) + polish.

TDD where practical; paper mode green before any testnet/live wiring.

---

## 19. Decoded original logic (evidence-based)

Reverse-engineered from `Wallet`/`Record` member names (preserved through obfuscation), `config.json`, runtime `logs/`, and `SAVE/*.json` values. Method bodies are protector stubs, so this is inference — but the exit/sizing parts reconcile numerically and are HIGH confidence.

### 19.0 Exchange = Bitget (correction)
Core data models carry **Bitget V2 API** field names throughout — ticker `lastPr/askPr/bidPr/askSz/bidSz/baseVolume/quoteVolume/usdtVolume/openUtc/indexPrice/fundingRate/markPrice`; contract `baseCoin/quoteCoin/symbolType/pricePlace/volumePlace/priceEndStep/minTradeNum/sizeMultiplier/maker-takerFeeRate/buy-sellLimitPriceRatio`; position `holdSide/marginCoin/marginSize/openPriceAvg/unrealizedPL/liquidationPrice/keepMarginRate/marginMode/posMode`. These are Bitget-specific (Binance uses different names). The `"binance"` default string is in the UI/service layer and is vestigial. **Primary venue = Bitget USDT-M (mix), productType `USDT-FUTURES`.** `~520` universe ≈ Bitget USDT perp count.

### 19.1 Signals the strategy computes (from `Wallet` fields)
`TargetPrice`, `TargetHit`, `BolingerHit` (Bollinger), `SupportLine`, `ResistLine`, `MinProfit`, `TrailingStop`, `StopLoss`, `LastEntryPrice`, `MaximumLoss/Profit` → indicator set = **Bollinger Bands + support/resistance + target price + trailing/min-profit levels.**

### 19.2 Entry (set HIGH / exact formula MEDIUM)
Short when price pierces upper Bollinger / `ResistLine` (`BolingerHit`), `이탈율 = (lastPr − ref)/ref ≥ Volatility{tf}%` on an enabled TF, `Standard{tf}` strength gate passes, and optional filters pass — funding (`|fundingRate| ≤ MaxFundingRate`), depth gap (`(askPr − bidPr)/bidPr ≤ MaxDepthGap`), trailing-entry (`TrailingEntryEnabled`: await `TrailingEntryPercent` pullback within `TrailingEntryTimeout`). Long = symmetric on lower band / `SupportLine`. Observed `이탈율` ≈ `Volatility` config (MR/UA 1h ~8–11; BO ~30) — strong match. Exact meaning of `Standard{tf}` (band multiplier vs RSI-like level) unresolved → MEDIUM.

### 19.3 Exit (HIGH — reconciles numerically, `Leverage=10`)
- `MinProfit` price `= entry × (1 ∓ MinProfit%/100)` (short −). KAT `0.01968 × 0.99 = 0.0194832` ✓.
- `TargetPrice` = `MinProfit` price when `ProfitUse=false` (else `entry × (1 ∓ Profit%)`).
- On reaching MinProfit, `TargetHit=true` → **arm trailing**.
- `TrailingStop` price `= best_favorable_price × (1 ± Trailing%/100)` (short +), ratchets. KAT best `≈ entry×(1−0.0132)`, `×1.03 = 0.02000` ✓; ESPORTS `0.41751 × 1.03 = 0.43003` ✓.
- Exit `청산 [TrailingStop]` when price crosses the armed trailing stop.
- Hard TP only if `ProfitUse`; hard SL only if `StopLossUse`. Observed config: both **off** → exits exclusively trailing; losers **never** stopped (held to reversion) → the 100%-win-rate + huge-open-drawdown signature (live `ALLOUSDT −4,452%`). `StopLoss` field ≈ `entry × (1 + Trailing%)` at init.

### 19.4 Sizing & adds (HIGH — martingale)
`qty = USDT × Leverage / entry`. Up to `SplitCnt` adds; an add fires (`추가매수 감지 … gap=−X%`) as the position moves adverse, averaging entry (martingale). Dynamic spacing `gap(n) = SplitGap% × SplitIntervalMultiplier × n` for `n ≥ SplitMultiplierStartAt` (30×6 → 360/540/720/900) when `SplitSquaredEnabled`. `AutoInputCtrl` (자동투입금) caps auto-sizing.

### 19.5 Filters / ops
Funding filter (`fundingRate`), depth-gap (`askPr/bidPr`), funding-fee PnL (`FundingFeeCheckEnabled`), rebalance (`RebalanceEnabled/Hours/LossPercent`, `IsTimeRebalance`), reverse-exit (`ReverseExit`), crossed margin (`격리 마진 OFF=교차`, `marginMode`). 시장 흐름 from 24h change (`lastPr` vs `openUtc`), `usdtVolume`, `fundingRate` across the universe.

## 20. Fidelity confidence matrix

| Area | Confidence | Basis |
|---|---|---|
| Exchange = Bitget | HIGH | Bitget V2 API field names in Core |
| Exit (trailing / arming / no-stop) | HIGH | wallets.json values reconcile numerically |
| Sizing + dynamic split gap | HIGH | config + settings preview + logs |
| Order lifecycle + logs + persistence | HIGH | runtime logs + SAVE files |
| Entry indicator SET (Bollinger + S/R + vol-dev + filters) | HIGH | Wallet fields + config + Bitget data |
| Exact entry formula (`Standard` meaning, band period/mult, S/R calc) | MEDIUM | not in stubs; inferred from params/logs — tunable |
| Risk-mode preset bundles (공격/일반/안정) | LOW–MED | UI labels only; values inferred |
