"""Ecology balance audit — measurable runtime checks."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from app.intelligence.market_runtime.ecology.ecosystem_runtime import EcosystemState


@dataclass
class EcologyAudit:
    passed: bool
    blockers: list[str]
    ecology_state: EcosystemState

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "blockers": self.blockers,
            "ecology": self.ecology_state.to_dict(),
        }


def audit_ecology_balance(state: EcosystemState) -> EcologyAudit:
    blockers: list[str] = []
    if state.overcrowding_score > 0.82:
        blockers.append(f"overcrowded={state.overcrowding_score:.2f}")
    if state.structural_incoherence > 0.78:
        blockers.append(f"incoherent={state.structural_incoherence:.2f}")
    if state.volatility_distortion > 0.75:
        blockers.append(f"vol_distorted={state.volatility_distortion:.2f}")
    if state.liquidity_fragmentation > 0.70:
        blockers.append(f"liquidity_fragmented={state.liquidity_fragmentation:.2f}")
    if state.ecology_balance < 0.30:
        blockers.append(f"low_balance={state.ecology_balance:.2f}")

    return EcologyAudit(
        passed=len(blockers) == 0 and state.participation_safe,
        blockers=blockers,
        ecology_state=state,
    )
