"""Crowd/ecology pressure proxies — reduce price-only illusion."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

import pandas as pd

from app.intelligence.market_runtime.ecology.ecosystem_runtime import EcosystemState
from app.intelligence.brain2.microstructure_grounding import MicrostructureGrounding


@dataclass
class CrowdPressureState:
    leverage_crowding_proxy: float
    liquidation_pressure_proxy: float
    directional_imbalance: float
    panic_participation_acceleration: float
    crowd_pressure: float

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        for k in d:
            if isinstance(d[k], float):
                d[k] = round(d[k], 4)
        return d


def compute_crowd_pressure(
    df: pd.DataFrame,
    ecology: EcosystemState,
    micro: MicrostructureGrounding,
    *,
    instability: float,
    entropy: float,
) -> CrowdPressureState:
    rets = df["close"].pct_change().dropna()
    recent = rets.tail(10)
    down_shock = float((recent < -recent.std() * 1.5).sum()) / max(1, len(recent))
    vol_accel = 0.0
    if len(rets) >= 30:
        short_v = float(rets.tail(5).std())
        long_v = float(rets.tail(30).std())
        vol_accel = max(0.0, min(1.0, short_v / (long_v + 1e-10) - 1.0))

    leverage_crowd = min(1.0, ecology.overcrowding_score * 0.55 + entropy * 0.25 + instability * 0.2)
    liq_pressure = min(1.0, down_shock * 0.45 + micro.vol_liquidity_elasticity * 0.25 + (1.0 - micro.fill_vol_ratio) * 0.3)
    directional = abs(micro.signed_pressure)
    panic_accel = min(1.0, vol_accel * 0.5 + instability * 0.3 + entropy * 0.2)

    combined = min(
        1.0,
        leverage_crowd * 0.3 + liq_pressure * 0.3 + directional * 0.2 + panic_accel * 0.2,
    )

    return CrowdPressureState(
        leverage_crowding_proxy=leverage_crowd,
        liquidation_pressure_proxy=liq_pressure,
        directional_imbalance=directional,
        panic_participation_acceleration=panic_accel,
        crowd_pressure=combined,
    )
