from __future__ import annotations

from app.engine.trailing import ExitEngine
from app.exchange.base import Ticker
from app.models import CloseReason, Record, Signal, Wallet
from app.strategies.base import MarketView


class _NullLogger:
    def write(self, category: str, message: str) -> None:
        pass


class PositionManager:
    def __init__(self, adapter, targets, strategies, store_wallets=None, store_records=None, logger=None, bus=None):
        self.adapter = adapter
        self.targets = targets
        self.strategies = strategies
        self.store_wallets = store_wallets
        self.store_records = store_records
        self.logger = logger or _NullLogger()
        self.bus = bus
        self.positions: dict[tuple[str, str], Wallet] = {}
        self.records: list[Record] = []

    def list(self) -> list[Wallet]:
        return list(self.positions.values())

    async def open(self, signal: Signal, ticker: Ticker, now: str = "") -> Wallet:
        side = signal.side.value
        target = self.targets[signal.strategy]
        lev = target.get_leverage(side)
        await self.adapter.set_leverage(signal.symbol, lev, side)
        qty = target.qty(side, ticker.last)
        fill = await self.adapter.create_market_order(signal.symbol, side, qty)
        w = Wallet(
            name=signal.symbol,
            side=signal.side,
            entry_type=signal.strategy,
            timeframe=signal.timeframe,
            leverage=lev,
            entry_price=fill.price,
            last_entry_price=fill.price,
            entry_count=fill.qty,
            current_price=fill.price,
            best_price=fill.price,
            split_count=1,
            trading_time=now,
        )
        self.positions[(w.name, side)] = w
        self.logger.write("TRADE", f"{w.name} {side} 진입 {fill.price} ({fill.qty:g}개) 이탈율={signal.deviation_pct:.2f}%")
        self.logger.write("TRADE", f"포지션 등록: {w.name} {side} {fill.price} ({fill.qty:g}개)")
        self.logger.write("TRADE", f"체결 확인: {w.name} {side} {fill.price} ({signal.strategy.value})")
        self._save_wallets()
        self._emit_positions()
        return w

    async def add(self, wallet: Wallet, ticker: Ticker) -> None:
        side = wallet.side.value
        target = self.targets[wallet.entry_type]
        qty = target.qty(side, ticker.last)
        fill = await self.adapter.create_market_order(wallet.name, side, qty)
        total = wallet.entry_count + fill.qty
        wallet.entry_price = (wallet.entry_price * wallet.entry_count + fill.price * fill.qty) / total
        wallet.entry_count = total
        wallet.last_entry_price = fill.price
        wallet.split_count += 1
        self.logger.write("TRADE", f"추가 진입: {wallet.name} {side} {wallet.split_count}차 {fill.price}")
        self.logger.write("TRADE", f"분할매수 체결: {wallet.name} {side} #{wallet.split_count}")
        self._save_wallets()
        self._emit_positions()

    async def manage(self, wallet: Wallet, mv: MarketView, now: str = "") -> Record | None:
        reason = ExitEngine.update(wallet, self.targets[wallet.entry_type], mv.ticker.last)
        self._emit_positions()
        if reason is not None:
            # preset-order fidelity: trailing/SL/TP fill at their TRIGGER price, not the
            # (possibly gapped) polling price. A market fill ~1 cycle later can book a loss
            # even though the trailing stop sat in profit — that was the source of the
            # occasional loss-closes. The original used preset exchange orders (fill at trigger).
            px = mv.ticker.last
            if reason is CloseReason.TRAILING_STOP:
                px = wallet.trailing_stop
            elif reason is CloseReason.STOP_LOSS:
                px = wallet.stop_loss
            elif reason is CloseReason.PROFIT:
                px = wallet.target_price
            return await self.close(wallet, reason, px, now)
        strat = self.strategies.get(wallet.entry_type)
        if strat is not None and strat.should_add(wallet, mv):
            self.logger.write("TRADE", f"추가매수 감지: {wallet.name} {wallet.side.value} ({wallet.entry_type.value})")
            await self.add(wallet, mv.ticker)
        return None

    async def close(self, wallet: Wallet, reason: CloseReason, price: float, now: str = "") -> Record:
        side = wallet.side.value
        await self.adapter.create_market_order(wallet.name, side, wallet.entry_count, reduce_only=True)
        rec = Record.from_wallet(wallet, price)
        rec.trading_time = now
        rec.reason = reason.value
        apply = getattr(self.adapter, "apply_realized_pnl", None)
        if apply is not None:
            apply(rec.pnl)
        self.records.append(rec)
        self.positions.pop((wallet.name, side), None)
        self.logger.write("TRADE", f"{wallet.name} {side} 청산 {price} [{reason.value}]")
        self.logger.write("TRADE", f"거래 기록: {wallet.name} {side} 수익률 {rec.roe:.2f}% / {rec.pnl:.2f} USDT")
        self.logger.write("TRADE", f"청산 완료: {wallet.name} {side}")
        self._save_records()
        self._save_wallets()
        if self.bus is not None:
            self.bus.emit("trade_executed", rec)
        self._emit_positions()
        return rec

    def _save_wallets(self) -> None:
        if self.store_wallets is not None:
            self.store_wallets.save([w.to_dict() for w in self.positions.values()])

    def _save_records(self) -> None:
        if self.store_records is not None:
            self.store_records.save([r.to_dict() for r in self.records])

    def _emit_positions(self) -> None:
        if self.bus is not None:
            self.bus.emit("positions_updated", self.list())
