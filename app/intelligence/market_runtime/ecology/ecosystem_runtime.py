"""Ecosystem runtime — observable pressure metrics, not narrative psychology."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

import numpy as np
import pandas as pd

from app.intelligence.market_runtime.structure.market_structure import MarketStructureState
from app.intelligence.market_runtime.edge_lab.edge_types import EdgeLayerResult


@dataclass
class EcosystemState:
    overcrowding_score: float
    structural_incoherence: float
    volatility_distortion: float
    liquidity_fragmentation: float
    ecology_balance: float
    participation_safe: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_ecosystem(
    df: pd.DataFrame,
    market: MarketStructureState,
    edges: EdgeLayerResult,
) -> EcosystemState:
    # Edge quality is audited separately by Brain-3; ecology should not double-penalize it.
    _ = edges
    rets = df["close"].pct_change().dropna()
    vol = df.get("volume", pd.Series(0, index=df.index))

    overcrowding = float(np.clip(market.entropy_score * 0.6 + market.synthetic_similarity * 0.4, 0, 1))
    incoherence = float(np.clip(market.instability_score * 0.5 + (1 - market.volatility_coherence) * 0.5, 0, 1))
    vol_distort = float(np.clip(abs(rets.tail(20).std() / (rets.tail(80).std() + 1e-10) - 1.0), 0, 1))

    frag = 0.5
    if vol.sum() > 0:
        frag = float(np.clip(1.0 - vol.tail(10).mean() / (vol.tail(50).mean() + 1e-8), 0, 1))

    balance = float(np.clip(1.0 - (overcrowding + incoherence + vol_distort + frag) / 4, 0, 1))

    safe = balance >= 0.35 and overcrowding < 0.85 and incoherence < 0.80

    return EcosystemState(
        overcrowding_score=round(overcrowding, 4),
        structural_incoherence=round(incoherence, 4),
        volatility_distortion=round(vol_distort, 4),
        liquidity_fragmentation=round(frag, 4),
        ecology_balance=round(balance, 4),
        participation_safe=safe,
    )
