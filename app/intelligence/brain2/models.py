"""Brain-2 semantic cognition models — probabilistic interpretation only."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class SemanticInterpretation:
    behavior: str
    meaning: str
    confidence: float
    evidence: list[str]
    regime: str
    decay: float = 1.0
    causal_level: int = 2
    governance_eligible: bool = True
    memory_sources: list[str] = field(default_factory=list)
    memory_support: float = 0.0
    contradiction_status: str = "clear"
    replay_trust: float = 0.5
    execution_survivability: str = "unknown"
    regime_alignment: str = "neutral"
    uncertainty_level: str = "moderate"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ContradictionRecord:
    contradiction_id: str
    observed_conflict: list[str]
    interpretation: str
    severity: float
    governance_note: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SequencePhase:
    phase: str
    behavior: str
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GovernanceContextOutput:
    """Compressed semantic context for Brain-3 — advisory only."""
    market_state: str
    fakeout_risk: str
    liquidity_state: str
    continuation_state: str
    confidence_level: float
    governance_implication: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExecutionSignals:
    """Pre-governance execution reality — advisory inputs only."""
    slip_ok: bool = True
    spread_ok: bool = True
    fill_ok: bool = True
    lat_ok: bool = True
    exec_guards_ok: bool = True
    execution_health: float = 1.0
    slip_reason: str = ""
    spread_reason: str = ""
    fill_reason: str = ""
    lat_reason: str = ""
    replay_mismatch: bool = False
    replay_supported: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CognitionRiskSurface:
    """Governance-oriented risk surface — UI exposes this only, not full semantics."""
    contradiction_pressure: float
    instability_level: str
    execution_fragility: str
    replay_live_distrust: str
    semantic_confidence: float
    regime_instability: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "contradiction_pressure": round(self.contradiction_pressure, 4),
            "instability_level": self.instability_level,
            "execution_fragility": self.execution_fragility,
            "replay_live_distrust": self.replay_live_distrust,
            "semantic_confidence": round(self.semantic_confidence, 4),
            "regime_instability": self.regime_instability,
        }


def _level_from_float(v: float, *, low: str, mid: str, high: str, crit: str | None = None) -> str:
    if crit and v >= 0.72:
        return crit
    if v >= 0.55:
        return high
    if v >= 0.28:
        return mid
    return low


@dataclass
class Brain2CognitionState:
    """Active runtime semantic cognition — not execution authority."""
    symbol: str
    regime: str
    interpretations: list[SemanticInterpretation] = field(default_factory=list)
    contradictions: list[ContradictionRecord] = field(default_factory=list)
    sequence: list[SequencePhase] = field(default_factory=list)
    governance_context: GovernanceContextOutput | None = None
    instability_probability: float = 0.0
    continuation_probability: float = 0.0
    fakeout_probability: float = 0.0
    exhaustion_probability: float = 0.0
    semantic_confidence: float = 0.0
    governance_confidence: float = 0.0
    contradiction_pressure: float = 0.0
    memory_hits: list[str] = field(default_factory=list)
    data_gaps: list[str] = field(default_factory=list)
    uncertainty_note: str = ""
    audit_report: dict[str, Any] | None = None
    execution_signals: dict[str, Any] | None = None
    cognition_risk: dict[str, Any] | None = None
    accumulated_contradiction_pressure: float = 0.0
    replay_divergence: dict[str, Any] | None = None
    cognitive_health: dict[str, Any] | None = None
    microstructure: dict[str, Any] | None = None
    crowd_pressure: dict[str, Any] | None = None
    impact_telemetry: dict[str, Any] | None = None
    memory_first_policy: dict[str, Any] | None = None
    abstention_tendency: float = 0.0
    market_emotion: dict[str, Any] | None = None
    thinking_framework: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "regime": self.regime,
            "interpretations": [i.to_dict() for i in self.interpretations],
            "contradictions": [c.to_dict() for c in self.contradictions],
            "sequence": [s.to_dict() for s in self.sequence],
            "governance_context": self.governance_context.to_dict() if self.governance_context else None,
            "instability_probability": round(self.instability_probability, 4),
            "continuation_probability": round(self.continuation_probability, 4),
            "fakeout_probability": round(self.fakeout_probability, 4),
            "exhaustion_probability": round(self.exhaustion_probability, 4),
            "semantic_confidence": round(self.semantic_confidence, 4),
            "governance_confidence": round(self.governance_confidence, 4),
            "contradiction_pressure": round(self.contradiction_pressure, 4),
            "accumulated_contradiction_pressure": round(self.accumulated_contradiction_pressure, 4),
            "memory_hits": self.memory_hits,
            "data_gaps": self.data_gaps,
            "uncertainty_note": self.uncertainty_note,
            "audit_report": self.audit_report,
            "execution_signals": self.execution_signals,
            "cognition_risk": self.cognition_risk,
            "replay_divergence": self.replay_divergence,
            "cognitive_health": self.cognitive_health,
            "microstructure": self.microstructure,
            "crowd_pressure": self.crowd_pressure,
            "impact_telemetry": self.impact_telemetry,
            "memory_first_policy": self.memory_first_policy,
            "abstention_tendency": round(self.abstention_tendency, 4),
            "market_emotion": self.market_emotion,
            "thinking_framework": self.thinking_framework,
        }
