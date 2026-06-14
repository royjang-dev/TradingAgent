from __future__ import annotations

from app.config import RiskGuards
from app.models import Wallet


class RiskGuard:
    """Optional global safety net. Disabled unless `risk_guards.enabled` and the
    relevant threshold is set (non-zero). The original ran with none of these."""

    def __init__(self, guards: RiskGuards):
        self.g = guards

    def position_breached(self, wallet: Wallet) -> bool:
        if not self.g.enabled or self.g.position_max_loss_roe >= 0:
            return False
        return wallet.calc_roe() <= self.g.position_max_loss_roe

    def daily_realized(self, records, today: str) -> float:
        return sum(r.pnl for r in records if (r.trading_time or "")[:10] == today)

    def daily_halted(self, records, today: str) -> bool:
        if not self.g.enabled or self.g.daily_loss_limit_usdt >= 0:
            return False
        return self.daily_realized(records, today) <= self.g.daily_loss_limit_usdt
