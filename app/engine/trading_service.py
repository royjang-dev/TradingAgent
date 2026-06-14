from __future__ import annotations

import asyncio

from app.config import Config, Target
from app.engine.event_bus import EventBus
from app.engine.position_manager import PositionManager
from app.engine.risk import RiskGuard
from app.models import CloseReason, EntryType, Side, Signal, TimeFrame
from app.strategies import build_strategy
from app.strategies import indicators as ind
from app.strategies.base import MarketView


class TradingService:
    """Orchestrator: scan cycle (manage open positions -> evaluate entries),
    events, settings hot-reload. Exchange-agnostic (paper or ccxt adapter)."""

    def __init__(self, adapter, config: Config, store_wallets=None, store_records=None, logger=None, bus=None):
        self.adapter = adapter
        self.config = config
        self.logger = logger
        self.bus = bus or EventBus()
        self.is_running = False
        self.is_initialized = True
        self.risk = RiskGuard(config.risk_guards)
        self.targets = self._active_targets(config)
        self.strategies = {et: build_strategy(et, tgt) for et, tgt in self.targets.items()}
        self.pm = PositionManager(adapter, self.targets, self.strategies, store_wallets, store_records, logger, self.bus)
        self._short_watch: dict[tuple[str, EntryType], int] = {}  # (symbol, strategy) -> cycles left

    @staticmethod
    def _active_targets(config: Config) -> dict[EntryType, Target]:
        out: dict[EntryType, Target] = {}
        if config.mean_revert_enabled:
            out[EntryType.MEAN_REVERT] = config.mean_revert_target
        if config.breakout_enabled:
            out[EntryType.BREAKOUT] = config.breakout_target
        if config.uprich_agrt_enabled:
            out[EntryType.UPRICH_AGRT] = config.uprich_agrt_target
        return out

    def _log(self, category: str, message: str) -> None:
        if self.logger is not None:
            self.logger.write(category, message)

    def _at_max(self, signal: Signal) -> bool:
        target = self.targets[signal.strategy]
        cap = target.short_position_cnt if signal.side.value == "short" else target.long_position_cnt
        cnt = sum(1 for w in self.pm.positions.values() if w.entry_type is signal.strategy and w.side is signal.side)
        return cnt >= cap

    async def cycle(self, views: dict[str, MarketView], now: str = "") -> None:
        today = now[:10]
        for wallet in list(self.pm.positions.values()):
            mv = views.get(wallet.name)
            if mv is None:
                continue
            rec = await self.pm.manage(wallet, mv, now)
            if rec is None and (wallet.name, wallet.side.value) in self.pm.positions and self.risk.position_breached(wallet):
                await self.pm.close(wallet, CloseReason.RISK_GUARD, mv.ticker.last, now)
        if self.risk.daily_halted(self.pm.records, today):
            if self.config.risk_guards.daily_loss_action == "close_all":
                for wallet in list(self.pm.positions.values()):
                    mv = views.get(wallet.name)
                    if mv is not None:
                        await self.pm.close(wallet, CloseReason.RISK_GUARD, mv.ticker.last, now)
            self._log("WARN", f"일일 손실 한도 도달 — 신규 진입 중단 ({self.config.risk_guards.daily_loss_action})")
            return
        if self.config.rsi_gated_short_enabled:
            await self._process_short_watch(views, now)
        for _symbol, mv in views.items():
            for entry_type, strat in self.strategies.items():
                signal = strat.evaluate_entry(mv)
                if signal is None:
                    continue
                if (signal.symbol, signal.side.value) in self.pm.positions or self._at_max(signal):
                    continue
                if self.config.rsi_gated_short_enabled and signal.side is Side.SHORT:
                    key = (signal.symbol, entry_type)
                    if key not in self._short_watch:
                        self._short_watch[key] = self.config.rsi_gate_arm_cycles
                        self._log("TRADE", f"감시 등록: {signal.symbol} short ({entry_type.value}) — RSI 하향돌파 대기")
                    continue  # do NOT open yet — wait for the RSI crossdown
                self._log("TRADE", f"매매 감지: {signal.symbol} {signal.side.value} {signal.timeframe.value} ({entry_type.value})")
                await self.pm.open(signal, mv.ticker, now)
                break

    async def _process_short_watch(self, views: dict[str, MarketView], now: str = "") -> None:
        """Armed fade-shorts enter only when the Ultimate RSI crosses DOWN through its signal."""
        for key in list(self._short_watch.keys()):
            symbol, entry_type = key
            if (symbol, "short") in self.pm.positions or entry_type not in self.strategies:
                del self._short_watch[key]
                continue
            self._short_watch[key] -= 1
            mv = views.get(symbol)
            if mv is not None and ind.rsi_crossed_down(
                mv.closes.get("1h", []), self.config.rsi_gate_length, self.config.rsi_gate_smooth
            ):
                sig = Signal(symbol, Side.SHORT, entry_type, TimeFrame.H1, mv.ticker.last, 0.0, "rsi-gate")
                if not self._at_max(sig):
                    self._log("TRADE", f"RSI 하향돌파 확인 → 숏 진입: {symbol} ({entry_type.value})")
                    await self.pm.open(sig, mv.ticker, now)
                del self._short_watch[key]
            elif self._short_watch[key] <= 0:
                self._log("TRADE", f"감시 만료: {symbol} short ({entry_type.value})")
                del self._short_watch[key]

    async def build_views(self, symbols, ticker_map=None, timeframes=("1h", "4h", "1d"), limit=60) -> dict[str, MarketView]:
        async def one(sym):
            ticker = (ticker_map or {}).get(sym) or await self.adapter.fetch_ticker(sym)
            closes, highs, lows = {}, {}, {}
            for tf in timeframes:
                ohlcv = await self.adapter.fetch_ohlcv(sym, tf, limit)
                closes[tf] = [c[4] for c in ohlcv]
                highs[tf] = [c[2] for c in ohlcv]
                lows[tf] = [c[3] for c in ohlcv]
            return MarketView(symbol=sym, ticker=ticker, closes=closes, highs=highs, lows=lows)

        results = await asyncio.gather(*[one(s) for s in symbols], return_exceptions=True)
        return {v.symbol: v for v in results if isinstance(v, MarketView)}

    def update_target(self, entry_type: EntryType, target: Target) -> None:
        self.targets[entry_type] = target
        self.strategies[entry_type] = build_strategy(entry_type, target)
        self.pm.targets[entry_type] = target
        self.pm.strategies[entry_type] = self.strategies[entry_type]
        self._log("DATA", f"TargetsManager: {entry_type.value} Target 업데이트")
        self._log("DATA", f"{entry_type.value} Target 업데이트 완료 (자동 활성화)")

    def apply_config(self, new_config: Config) -> list[str]:
        changes = self._diff(self.config, new_config)
        self.config = new_config
        self.risk = RiskGuard(new_config.risk_guards)
        self.targets = self._active_targets(new_config)
        self.strategies = {et: build_strategy(et, t) for et, t in self.targets.items()}
        self.pm.targets = self.targets
        self.pm.strategies = self.strategies
        if changes:
            self._log("TRADE", f"[설정 저장] {len(changes)}건 변경:")
            for line in changes:
                self._log("TRADE", line)
        for entry_type in self.targets:
            self._log("DATA", f"TargetsManager: {entry_type.value} Target 업데이트")
            self._log("DATA", f"{entry_type.value} Target 업데이트 완료 (자동 활성화)")
        return changes

    @staticmethod
    def _diff(old: Config, new: Config) -> list[str]:
        strat = [("MR", "mean_revert_target"), ("BO", "breakout_target"), ("UA", "uprich_agrt_target")]
        fields = [
            ("USDT(Long)", "long_usdt"), ("USDT(Short)", "short_usdt"),
            ("레버리지(Long)", "long_leverage"), ("레버리지(Short)", "short_leverage"),
            ("자동투입금(Long)", "long_auto_input_ctrl"), ("자동투입금(Short)", "short_auto_input_ctrl"),
            ("익절", "profit"), ("손절", "stop_loss"), ("트레일링", "trailing_stop"), ("최소수익", "min_profit"),
            ("분할횟수(Short)", "short_split_cnt"),
        ]
        lines: list[str] = []
        for prefix, attr in strat:
            o, n = getattr(old, attr), getattr(new, attr)
            for label, field in fields:
                ov, nv = getattr(o, field, None), getattr(n, field, None)
                if ov != nv:
                    lines.append(f"{prefix} {label}: {ov} -> {nv}")
        for label, field in [("MeanRevert", "mean_revert_enabled"), ("Breakout", "breakout_enabled"), ("UprichAgrt", "uprich_agrt_enabled")]:
            if getattr(old, field) != getattr(new, field):
                lines.append(f"{label} 활성: {getattr(old, field)} -> {getattr(new, field)}")
        return lines

    def start(self) -> None:
        self.is_running = True

    def stop(self) -> None:
        self.is_running = False
