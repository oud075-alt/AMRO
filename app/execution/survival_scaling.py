"""Survival scaling from runtime trust + edge health + DD."""
from __future__ import annotations

import numpy as np

from app.intelligence.market_runtime.abstention.edge_survival_monitor import EdgeHealth


def compute_survival_scaling(
    runtime_trust: float,
    health: EdgeHealth | None,
    rolling_dd: float,
    abstention_pressure: float,
) -> float:
    scale = runtime_trust
    if health:
        scale *= health.allocation_multiplier
        if not health.enabled:
            return 0.0
    if rolling_dd > 0.08:
        scale *= 0.25
    elif rolling_dd > 0.04:
        scale *= 0.5
    scale *= max(0.1, 1.0 - abstention_pressure * 0.5)
    return float(np.clip(scale, 0, 1))
