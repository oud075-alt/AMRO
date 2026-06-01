"""Runtime market identity — survivability alignment score, not static pattern match."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

import numpy as np

from app.intelligence.market_runtime.fingerprint.behavioral_fingerprint import (
    compute_fingerprint,
    structure_quality_from_fingerprint,
)
from app.intelligence.market_runtime.fingerprint.fingerprint_alignment import fingerprint_alignment
from app.intelligence.market_runtime.edge_lab.edge_types import EdgeLayerResult
import pandas as pd


@dataclass
class MarketIdentity:
    identity_hash: str
    structure_survivability: float
    dominant_edge_alignment: float
    degradation_factor: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_market_identity(df: pd.DataFrame, edges: EdgeLayerResult) -> MarketIdentity:
    fp = compute_fingerprint(df)
    struct_q = structure_quality_from_fingerprint(fp)
    align = (
        fingerprint_alignment(edges.dominant_edge, fp)
        if edges.dominant_edge
        else 0.5
    )
    decay_edges = [e.confidence_decay for e in edges.edges]
    degradation = float(np.mean(decay_edges)) if decay_edges else 0.5
    survivability = float(np.clip(struct_q * align * (1.0 - degradation * 0.3), 0, 1))

    fp_hash = "|".join(f"{k}:{fp[k]:.3f}" for k in sorted(fp.keys()))

    return MarketIdentity(
        identity_hash=fp_hash[:32],
        structure_survivability=round(survivability, 4),
        dominant_edge_alignment=round(align, 4),
        degradation_factor=round(degradation, 4),
    )
