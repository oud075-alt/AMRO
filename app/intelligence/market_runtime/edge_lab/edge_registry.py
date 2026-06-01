"""Registry of behavioral edges — structure-only, no universal strategy."""
from __future__ import annotations

from typing import Callable

import pandas as pd

from app.intelligence.market_runtime.edge_lab.edge_detectors import (
    detect_asia_compression,
    detect_compression_release,
    detect_liquidity_vacuum,
    detect_london_breakout,
    detect_volatility_exhaustion,
)
from app.intelligence.market_runtime.edge_lab.edge_types import EdgeSignal

EdgeDetectorFn = Callable[[pd.DataFrame, int], EdgeSignal]

EDGES: dict[str, EdgeDetectorFn] = {
    "london_breakout": detect_london_breakout,
    "asia_compression": detect_asia_compression,
    "liquidity_vacuum": detect_liquidity_vacuum,
    "volatility_exhaustion": detect_volatility_exhaustion,
    "compression_release": detect_compression_release,
}

EDGE_DETECTORS: list[EdgeDetectorFn] = list(EDGES.values())


def list_edges() -> list[str]:
    return list(EDGES.keys())


def get_edge(name: str) -> EdgeDetectorFn:
    if name not in EDGES:
        raise KeyError(f"Unknown edge: {name}. Available: {list(EDGES)}")
    return EDGES[name]
