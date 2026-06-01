"""Abstention pressure aggregation — separate from governance pressure."""
from __future__ import annotations

import numpy as np

from app.intelligence.market_runtime.structure.market_structure import MarketStructureState
from app.intelligence.market_runtime.abstention.adaptive_abstention import AbstentionDecision


def compute_abstention_pressure(
    market: MarketStructureState,
    abstention: AbstentionDecision,
) -> float:
    """0..1 pressure — NOT interchangeable with governance_pressure."""
    components = [
        abstention.abstention_pressure,
        market.instability_score * 0.3,
        market.synthetic_similarity * 0.25 if market.synthetic_similarity > 0.8 else 0,
        (1.0 - market.volatility_coherence) * 0.2 if market.volatility_coherence < 0.4 else 0,
    ]
    return float(np.clip(max(components), 0, 1))
