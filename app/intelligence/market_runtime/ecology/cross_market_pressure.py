"""Cross-market pressure — optional multi-symbol stress (runtime-linked)."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class CrossMarketPressure:
    pressure_score: float
    correlated_instability: bool
    notes: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compute_cross_market_pressure(
    primary_instability: float,
    peer_instabilities: list[float] | None = None,
) -> CrossMarketPressure:
    peers = peer_instabilities or []
    if not peers:
        return CrossMarketPressure(
            pressure_score=round(primary_instability * 0.5, 4),
            correlated_instability=False,
            notes="single_market_mode",
        )
    avg_peer = sum(peers) / len(peers)
    pressure = min(1.0, (primary_instability + avg_peer) / 2)
    correlated = primary_instability > 0.6 and avg_peer > 0.6
    return CrossMarketPressure(
        pressure_score=round(pressure, 4),
        correlated_instability=correlated,
        notes="correlated_stress" if correlated else "diversified",
    )
