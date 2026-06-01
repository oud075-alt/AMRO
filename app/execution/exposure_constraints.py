"""Hard exposure constraints — deterministic caps."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ExposureConstraints:
    max_position_limit: float
    max_concurrent_risk_units: float
    exposure_state: str


def apply_exposure_constraints(
    raw_limit: float,
    open_positions: int = 0,
    rolling_dd: float = 0.0,
) -> ExposureConstraints:
    limit = raw_limit
    state = "balanced"

    if rolling_dd > 0.12:
        limit *= 0.25
        state = "locked"
    elif rolling_dd > 0.06:
        limit *= 0.5
        state = "constrained"

    if open_positions >= 3:
        limit *= 0.5
        state = "constrained"

    limit = max(0.0, min(1.0, limit))

    return ExposureConstraints(
        max_position_limit=round(limit, 4),
        max_concurrent_risk_units=round(limit * 3, 4),
        exposure_state=state,
    )
