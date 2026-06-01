"""Behavioral edge types — structure only, no BUY/SELL."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class EdgeSignal:
    edge_id: str
    edge_detected: bool
    edge_strength: float
    edge_quality: float
    environment_alignment: float
    confidence_decay: float
    replay_signature: str
    description: str = ""

    @property
    def edge_environment_fit(self) -> float:
        """Backward-compatible alias."""
        return self.environment_alignment

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["edge_environment_fit"] = self.environment_alignment
        return d


@dataclass
class EdgeLayerResult:
    symbol: str
    edges: list[EdgeSignal] = field(default_factory=list)
    dominant_edge: str = ""
    aggregate_strength: float = 0.0
    aggregate_quality: float = 0.0
    environment_quality: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "edges": [e.to_dict() for e in self.edges],
            "dominant_edge": self.dominant_edge,
            "aggregate_strength": self.aggregate_strength,
            "aggregate_quality": self.aggregate_quality,
            "environment_quality": self.environment_quality,
        }
