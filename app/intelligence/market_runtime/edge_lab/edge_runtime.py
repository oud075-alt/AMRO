"""Run behavioral edge layer at latest bar — structure only."""
from __future__ import annotations

import pandas as pd
from loguru import logger

from app.intelligence.market_runtime.edge_lab._session import enrich_market_df
from app.intelligence.market_runtime.edge_lab.edge_registry import EDGE_DETECTORS
from app.intelligence.market_runtime.edge_lab.edge_types import EdgeLayerResult, EdgeSignal


def prepare_edge_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize OHLCV index → timestamp column + ATR/session features."""
    return enrich_market_df(df)


def run_edge_layer(df: pd.DataFrame, symbol: str) -> EdgeLayerResult:
    enriched = prepare_edge_dataframe(df)
    if len(enriched) < 50:
        return EdgeLayerResult(symbol=symbol)

    i = len(enriched) - 1
    edges: list[EdgeSignal] = [fn(enriched, i) for fn in EDGE_DETECTORS]

    detected = [e for e in edges if e.edge_detected]
    dominant = ""
    if detected:
        best = max(detected, key=lambda e: e.edge_quality * e.edge_strength)
        dominant = best.edge_id

    strengths = [e.edge_strength for e in edges]
    qualities = [e.edge_quality for e in edges]
    fits = [e.edge_environment_fit for e in edges]

    result = EdgeLayerResult(
        symbol=symbol,
        edges=edges,
        dominant_edge=dominant,
        aggregate_strength=round(float(sum(strengths) / len(strengths)), 4),
        aggregate_quality=round(float(sum(qualities) / len(qualities)), 4),
        environment_quality=round(float(sum(fits) / len(fits)), 4),
    )
    logger.info(
        f"[EdgeLab] {symbol} bar={i} dominant={dominant or 'none'} "
        f"env_q={result.environment_quality:.2f} detected={len(detected)}/{len(edges)}"
    )
    return result
