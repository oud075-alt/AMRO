"""Runtime reconstructor — rebuild expected state from prior snapshot."""
from __future__ import annotations

from typing import Any


def reconstruct_expected(prior: dict[str, Any]) -> dict[str, Any]:
    return {
        "replay_signature": prior.get("replay_signature", ""),
        "governance_verdict": prior.get("governance_verdict", ""),
        "runtime_trust": prior.get("runtime_trust", 0.5),
        "abstention_pressure": prior.get("abstention_pressure", 0.0),
    }
