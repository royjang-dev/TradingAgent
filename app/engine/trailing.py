from __future__ import annotations

from app.config import Target
from app.models import CloseReason, Side, Wallet


def _favorable(side: Side, a: float, b: float) -> float:
    return min(a, b) if side is Side.SHORT else max(a, b)


class ExitEngine:
    """Decoded exit mechanics (design spec §19.3).

    Arm at MinProfit% (TargetHit), then trail at best_favorable*(1 +/- Trailing%);
    exit on cross. Optional hard take-profit / stop-loss. With the observed
    default config (profit_use=False, stop_loss_use=False) every close is a
    trailing-stop and losers are never stopped out.
    """

    @staticmethod
    def update(wallet: Wallet, target: Target, price: float) -> CloseReason | None:
        entry = wallet.entry_price
        wallet.current_price = price
        if entry <= 0:
            return None

        is_short = wallet.side is Side.SHORT
        sgn = 1.0 if is_short else -1.0
        profit_pct = sgn * (entry - price) / entry * 100.0

        if wallet.best_price == 0.0:
            wallet.best_price = entry
        wallet.best_price = _favorable(wallet.side, wallet.best_price, price)

        wallet.min_profit = entry * (1 - sgn * target.min_profit / 100.0)
        wallet.target_price = (
            entry * (1 - sgn * target.profit / 100.0) if target.profit_use else wallet.min_profit
        )
        wallet.trailing_stop = wallet.best_price * (1 + sgn * target.trailing_stop / 100.0)
        wallet.stop_loss = entry * (1 + sgn * target.stop_loss / 100.0)

        roe = wallet.calc_roe()
        wallet.max_profit = max(wallet.max_profit, roe)
        wallet.max_loss = min(wallet.max_loss, roe)

        if profit_pct >= target.min_profit:
            wallet.target_hit = True

        if target.profit_use and profit_pct >= target.profit:
            return CloseReason.PROFIT
        if target.stop_loss_use and (-profit_pct) >= target.stop_loss:
            return CloseReason.STOP_LOSS
        if target.trailing_stop_use and wallet.target_hit:
            crossed = price >= wallet.trailing_stop if is_short else price <= wallet.trailing_stop
            # original behaviour: only exit when the trailing stop LOCKS A PROFIT.
            # if the position armed (+MinProfit) but never ran far enough for the stop to
            # be in profit, it is HELD (never closed at a loss) -> this is what produces
            # the 100% win rate + bag-held losers (design spec §19.3).
            locks_profit = wallet.trailing_stop < entry if is_short else wallet.trailing_stop > entry
            if crossed and locks_profit:
                return CloseReason.TRAILING_STOP
        return None
