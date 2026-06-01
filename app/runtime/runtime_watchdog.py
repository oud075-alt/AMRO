"""Runtime watchdog — pipeline integrity + execution permission gate."""
from __future__ import annotations

from dataclasses import dataclass

from app.runtime.runtime_health import RuntimeHealth, RuntimeStateLevel


@dataclass
class IntegrityCheck:
    ok: bool
    violations: list[str]


def check_pipeline_integrity(
    has_market: bool,
    has_edges: bool,
    has_abstention: bool,
    has_governance: bool,
    has_allocation: bool,
) -> IntegrityCheck:
    violations: list[str] = []
    if not has_market:
        violations.append("missing_market_structure")
    if not has_edges:
        violations.append("missing_edge_layer")
    if not has_abstention:
        violations.append("missing_abstention")
    if not has_governance:
        violations.append("missing_governance")
    if not has_allocation:
        violations.append("missing_allocation")
    return IntegrityCheck(ok=len(violations) == 0, violations=violations)


def execution_permitted(health: RuntimeHealth) -> tuple[bool, str]:
    if health.level == RuntimeStateLevel.DISABLED:
        return False, "runtime_disabled"
    if health.level == RuntimeStateLevel.UNTRUSTED:
        return False, "runtime_untrusted"
    if health.replay_mismatch:
        return False, "replay_mismatch"
    if health.data_stale:
        return False, "stale_candles"
    if health.missing_candles:
        return False, "missing_candles"
    if health.telemetry_corrupt:
        return False, "telemetry_corruption"
    if health.level == RuntimeStateLevel.DEGRADED:
        return True, "runtime_degraded_limited"
    return True, "runtime_ok"
