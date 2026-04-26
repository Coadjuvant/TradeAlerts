from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RiskResult:
    account_size: float
    max_risk_percent: float
    dollar_risk: float
    stop_distance: float
    quantity: float
    notional_exposure: float
    warnings: list[str]


def calculate_position_size(
    account_size: float,
    max_risk_percent: float,
    entry_price: float,
    stop_loss: float,
    slippage_assumption: float,
) -> RiskResult:
    warnings: list[str] = []
    dollar_risk = account_size * (max_risk_percent / 100)
    stop_distance = abs(entry_price - stop_loss)
    if stop_distance <= 0:
        return RiskResult(account_size, max_risk_percent, dollar_risk, stop_distance, 0.0, 0.0, ["invalid_stop_distance"])
    effective_risk_per_share = stop_distance + entry_price * slippage_assumption
    qty = max(0.0, dollar_risk / effective_risk_per_share)
    if stop_distance < entry_price * 0.001:
        warnings.append("stop_too_tight")
    if qty > 100000:
        warnings.append("position_size_unrealistic")
    exposure = qty * entry_price
    if effective_risk_per_share > stop_distance * 1.5:
        warnings.append("slippage_makes_trade_less_attractive")
    return RiskResult(account_size, max_risk_percent, dollar_risk, stop_distance, qty, exposure, warnings)
