"""Crash recovery — fail closed, no speculative recovery."""
from __future__ import annotations

from app.runtime.runtime_health import RuntimeHealth, RuntimeStateLevel


def recover_runtime(health: RuntimeHealth) -> RuntimeHealth:
    """On uncertain recovery state, escalate to DISABLED."""
    if health.level in (RuntimeStateLevel.UNTRUSTED, RuntimeStateLevel.DISABLED):
        return health
    if len(health.reasons) >= 2:
        health.level = RuntimeStateLevel.DISABLED
        health.reasons.append("crash_recovery_fail_closed")
    return health
