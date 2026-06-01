"""
Runtime edge environment believability — NOT structure_confidence / win probability.
Derived from edge quality + fingerprint alignment + survival (USDJPY edge_validator concept).
"""
from __future__ import annotations

import numpy as np

from app.intelligence.market_runtime.fingerprint import fingerprint_alignment
from app.intelligence.market_runtime.abstention.edge_survival_monitor import EdgeHealth
from app.intelligence.market_runtime.edge_lab.edge_types import EdgeLayerResult


def compute_runtime_believability(
    edges: EdgeLayerResult,
    fingerprint: dict[str, float],
    health: EdgeHealth | None,
) -> float:
    """
    0-1 environment believability for abstention/allocation.
    Separate from market_quality_score and participation quality probability.
    """
    if not edges.dominant_edge:
        base = edges.aggregate_quality * 0.5 + edges.environment_quality * 0.3
        align = 0.5
    else:
        dom = next((e for e in edges.edges if e.edge_id == edges.dominant_edge), None)
        align = fingerprint_alignment(edges.dominant_edge, fingerprint)
        dom_q = dom.edge_quality if dom else 0.0
        dom_s = dom.edge_strength if dom else 0.0
        base = 0.35 * dom_q + 0.25 * dom_s + 0.25 * align + 0.15 * edges.environment_quality

    if health:
        if not health.enabled:
            return 0.0
        base *= health.allocation_multiplier
        if health.replay_mismatch:
            base *= 0.25
        base *= max(0.2, 1.0 - health.degradation_score * 2)

    return float(np.clip(base, 0.0, 1.0))
