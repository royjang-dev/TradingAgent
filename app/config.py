from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


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
    isolated_margin: bool = False
    rebalance_enabled: bool = False
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


class RiskGuards(BaseModel):
    """Optional safety net beyond the strategy's own exit. OFF by default to
    stay faithful to the original (which runs with no hard stop)."""

    enabled: bool = False
    position_max_loss_roe: float = 0.0   # e.g. -500 => force-close at <= -500% ROE; 0 = off
    daily_loss_limit_usdt: float = 0.0   # e.g. -100 => halt/close when today realized <= -100; 0 = off
    daily_loss_action: Literal["halt", "close_all"] = "halt"


class Config(BaseModel):
    selected_symbols: list[str] = Field(default_factory=list)
    use_two_way_trading: bool = True
    use_fixed_trade: bool = False
    mean_revert_target: MeanRevertTarget = Field(default_factory=lambda: MeanRevertTarget(target_name="MeanRevert"))
    breakout_target: BreakoutTarget = Field(default_factory=lambda: BreakoutTarget(target_name="Breakout"))
    uprich_agrt_target: UprichAgrtTarget = Field(default_factory=lambda: UprichAgrtTarget(target_name="UprichAgrt"))
    mean_revert_enabled: bool = True
    breakout_enabled: bool = True
    uprich_agrt_enabled: bool = True
    enable_console_log: bool = True
    enable_file_log: bool = True
    log_path: str = "logs"
    profit_close_filter_enabled: bool = False
    risk_guards: RiskGuards = Field(default_factory=RiskGuards)
    execution_mode: Literal["paper", "testnet", "live"] = "paper"
    execution_enabled: bool = False
    # SHORT entry gate: a fade signal only ARMS a watch; enter the short when the
    # Ultimate RSI crosses DOWN through its signal line within the arm window.
    rsi_gated_short_enabled: bool = False
    rsi_gate_length: int = 14
    rsi_gate_smooth: int = 14
    rsi_gate_arm_cycles: int = 12


def load_config(path: str | Path) -> Config:
    return Config.model_validate_json(Path(path).read_text(encoding="utf-8"))


def save_config(config: Config, path: str | Path) -> None:
    Path(path).write_text(config.model_dump_json(indent=2), encoding="utf-8")
