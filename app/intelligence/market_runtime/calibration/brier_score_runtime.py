"""Runtime Brier score proxy from structure vs environment alignment."""
from __future__ import annotations

import numpy as np


def compute_brier_score_runtime(
    structure_confidence: float,
    environment_quality: float,
) -> float:
    predicted = 0.5 + (environment_quality - 0.5) * 0.5
    observed = structure_confidence
    return float(np.clip((predicted - observed) ** 2, 0.0, 1.0))
