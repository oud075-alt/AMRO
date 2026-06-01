"""Track confidence decay from edge layer outputs."""
from __future__ import annotations

import numpy as np

from app.intelligence.market_runtime.edge_lab.edge_types import EdgeLayerResult


def track_confidence_decay(edges: EdgeLayerResult) -> float:
    if not edges.edges:
        return 1.0
    decays = [e.confidence_decay for e in edges.edges]
    return float(np.clip(np.mean(decays), 0.0, 1.0))
