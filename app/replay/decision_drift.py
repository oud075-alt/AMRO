"""Decision drift detection for replay validation."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class DriftReport:
    decision_drift: bool
    governance_inconsistent: bool
    runtime_divergence: bool
    context_instability: bool
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def detect_decision_drift(
    prior_signature: str,
    current_signature: str,
    prior_verdict: str,
    current_verdict: str,
    prior_trust: float,
    current_trust: float,
) -> DriftReport:
    notes: list[str] = []
    drift = bool(prior_signature and current_signature and prior_signature != current_signature)
    if drift:
        notes.append("edge_replay_signature_changed")
    gov_inc = prior_verdict == "ALLOW" and current_verdict == "BLOCK"
    if gov_inc:
        notes.append("governance_verdict_regression")
    rt_div = abs(prior_trust - current_trust) > 0.35
    if rt_div:
        notes.append("runtime_trust_divergence")
    return DriftReport(
        decision_drift=drift,
        governance_inconsistent=gov_inc,
        runtime_divergence=rt_div,
        context_instability=rt_div and drift,
        notes=notes,
    )
