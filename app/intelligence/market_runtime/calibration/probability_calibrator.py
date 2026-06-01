"""Participation-quality calibration — not win or direction probability."""
from __future__ import annotations

import numpy as np


def calibrate_participation_quality_probability(
    raw_score: float,
    sample_count: int,
    brier_score: float,
) -> float:
    """Map raw environment quality to a participation-quality probability."""
    if sample_count < 30:
        return 0.5
    penalty = min(0.25, max(0.0, brier_score))
    calibrated = 0.5 + (raw_score - 0.5) * (1.0 - penalty)
    return float(np.clip(calibrated, 0.0, 1.0))
