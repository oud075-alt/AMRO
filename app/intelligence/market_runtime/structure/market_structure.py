"""AI #2 market structure state — audit outputs only."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

import pandas as pd
from loguru import logger

from app.intelligence.market_runtime.structure.audit_layer import AuditResult, compute_audit


@dataclass
class MarketStructureState:
    market_state: str
    structure_confidence: float
    instability_score: float
    distribution_shift: float
    tradable: bool
    reason: str
    entropy_score: float = 0.0
    synthetic_similarity: float = 0.0
    volatility_coherence: float = 0.0
    signal_reliability: float = 0.0
    notes: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


MarketAudit = MarketStructureState


def _classify_market_state(a: AuditResult) -> tuple[str, bool, str]:
    sc = a.structure_confidence
    inst = a.instability_score
    ent = a.entropy_score
    synth = a.synthetic_similarity
    shift = a.distribution_shift

    if "insufficient_data" in (a.notes or []):
        return "dead", False, "Insufficient market data for audit"

    if sc < 0.15:
        return "dead", False, f"Structure confidence too low ({sc:.2f})"

    if inst > 0.82 and ent > 0.72:
        return "chaotic", False, f"Chaotic conditions (instability={inst:.2f}, entropy={ent:.2f})"

    if shift > 0.75:
        return "unstable", False, f"Distribution shift elevated ({shift:.2f})"

    if inst > 0.65 or synth > 0.80:
        return "unstable", True, f"Elevated instability or synthetic noise (inst={inst:.2f}, synth={synth:.2f})"

    if sc < 0.30:
        return "unstable", False, f"Structure confidence below tradable minimum ({sc:.2f})"

    if a.signal_reliability < 0.25:
        return "unstable", False, f"Signal reliability too low ({a.signal_reliability:.2f})"

    return "tradable", True, "Market audit passed — conditions within constitutional bounds"


def compute_market_audit(df: pd.DataFrame) -> MarketStructureState:
    audit = compute_audit(df)
    state, tradable, reason = _classify_market_state(audit)

    logger.info(f"[MarketStructure] market_state={state} tradable={tradable} | {reason}")

    return MarketStructureState(
        market_state=state,
        structure_confidence=audit.structure_confidence,
        instability_score=audit.instability_score,
        distribution_shift=audit.distribution_shift,
        tradable=tradable,
        reason=reason,
        entropy_score=audit.entropy_score,
        synthetic_similarity=audit.synthetic_similarity,
        volatility_coherence=audit.volatility_coherence,
        signal_reliability=audit.signal_reliability,
        notes=audit.notes,
    )
