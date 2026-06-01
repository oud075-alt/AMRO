"""Latency guard — execution health gate."""
from __future__ import annotations


def check_latency(execution_health: float, min_health: float = 0.5) -> tuple[bool, str]:
    if execution_health < min_health:
        return False, f"latency_instability_health={execution_health:.2f}"
    return True, "latency_ok"
