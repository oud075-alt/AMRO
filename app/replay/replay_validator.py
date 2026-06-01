"""Replay validator — governance, abstention, execution consistency."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from app.replay.decision_drift import DriftReport, detect_decision_drift


@dataclass
class ReplayValidation:
    runtime_parity: bool
    governance_consistent: bool
    abstention_consistent: bool
    execution_consistent: bool
    drift: DriftReport

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["drift"] = self.drift.to_dict()
        return d


def validate_replay(
    prior: dict[str, Any],
    current: dict[str, Any],
) -> ReplayValidation:
    drift = detect_decision_drift(
        prior.get("replay_signature", ""),
        current.get("replay_signature", ""),
        prior.get("governance_verdict", ""),
        current.get("governance_verdict", ""),
        float(prior.get("runtime_trust", 0.5)),
        float(current.get("runtime_trust", 0.5)),
    )
    abs_p_prior = float(prior.get("abstention_pressure", 0))
    abs_p_cur = float(current.get("abstention_pressure", 0))
    abstention_consistent = abs(abs_p_prior - abs_p_cur) < 0.4 or not drift.decision_drift

    return ReplayValidation(
        runtime_parity=not drift.runtime_divergence,
        governance_consistent=not drift.governance_inconsistent,
        abstention_consistent=abstention_consistent,
        execution_consistent=not drift.decision_drift,
        drift=drift,
    )
