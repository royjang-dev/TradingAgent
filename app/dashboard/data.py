from __future__ import annotations

from collections import defaultdict


def build_status(balance, available, positions, records) -> dict:
    total_pnl = sum(r.pnl for r in records)
    wins = sum(1 for r in records if r.pnl > 0)
    n = len(records)
    total_roe = sum(r.roe for r in records)
    unrealized = sum(p.calc_pnl() for p in positions)
    return {
        "balance": round(balance, 2),
        "available": round(available, 2),
        "unrealized_pnl": round(unrealized, 2),
        "equity": round(balance + unrealized, 2),  # true account value incl. open (bag) positions
        "total_pnl": round(total_pnl, 2),
        "trade_count": n,
        "total_roe": round(total_roe, 2),
        "win_rate": round(wins / n * 100, 1) if n else 0.0,
        "position_count": len(positions),
        "order_count": 0,
        "avg_roe": round(total_roe / n, 2) if n else 0.0,
        "win": wins,
        "loss": n - wins,
    }


def serialize_positions(positions) -> list[dict]:
    return [
        {
            "symbol": w.name,
            "strategy": w.entry_type.value,
            "side": w.side.value,
            "qty": round(w.entry_count, 4),
            "entry_price": w.entry_price,
            "current_price": w.current_price,
            "pnl": round(w.calc_pnl(), 2),
            "roe": round(w.calc_roe(), 2),
            "leverage": w.leverage,
            "split": w.split_count,
            "tf": w.timeframe.value,
            "entry_time": w.trading_time,
        }
        for w in positions
    ]


def serialize_records(records) -> list[dict]:
    return [
        {
            "symbol": r.name,
            "side": r.side.value,
            "entry_price": r.entry_price,
            "close_price": r.close_price,
            "qty": round(r.close_count, 4),
            "pnl": round(r.pnl, 2),
            "roe": round(r.roe, 2),
            "split": r.split_count,
            "type": r.entry_type.value,
            "tf": r.timeframe.value,
            "entry_time": r.entry_time,
            "close_time": r.trading_time,
            "reason": r.reason,
        }
        for r in records
    ]


def build_daily(records) -> dict:
    agg: dict[str, dict] = defaultdict(lambda: {"net": 0.0, "profit": 0.0, "loss": 0.0, "profit_roe": 0.0, "loss_roe": 0.0})
    for r in records:
        day = ((r.trading_time or r.entry_time) or "")[:10]  # fall back to entry date if close time missing
        if not day:
            continue
        a = agg[day]
        a["net"] += r.pnl
        if r.pnl >= 0:
            a["profit"] += r.pnl
            a["profit_roe"] += r.roe
        else:
            a["loss"] += r.pnl
            a["loss_roe"] += r.roe
    days = sorted(agg)
    return {
        "labels": days,
        "values": [round(agg[d]["net"], 2) for d in days],
        "profit": [round(agg[d]["profit"], 2) for d in days],
        "loss": [round(agg[d]["loss"], 2) for d in days],
        "profit_roe": [round(agg[d]["profit_roe"], 2) for d in days],
        "loss_roe": [round(agg[d]["loss_roe"], 2) for d in days],
    }


def _coin(c) -> dict | None:
    return None if c is None else {"symbol": c.symbol, "pct": round(c.pct, 4)}


def _tick(t) -> dict | None:
    return None if t is None else {"symbol": t.symbol, "last": t.last, "change": round(t.change_pct, 2), "high": t.high, "low": t.low}


def serialize_market(ov) -> dict:
    if ov is None:
        return {}
    return {
        "btc": _tick(ov.btc),
        "eth": _tick(ov.eth),
        "up": ov.up_count,
        "down": ov.down_count,
        "total": ov.total,
        "up_ratio": round(ov.up_ratio, 1),
        "avg_change": round(ov.avg_change, 2),
        "avg_volatility": round(ov.avg_volatility, 2),
        "daily_range": round(ov.avg_daily_range, 2),
        "avg_funding": round(ov.avg_funding, 4),
        "funding_high": _coin(ov.funding_high),
        "funding_low": _coin(ov.funding_low),
        "top_gainers": [_coin(c) for c in ov.top_gainers],
        "top_losers": [_coin(c) for c in ov.top_losers],
        "top_volume": [
            {"symbol": c.symbol, "vol": round(c.quote_volume, 0), "pct": round(c.change_pct, 2)}
            for c in ov.top_volume
        ],
    }
