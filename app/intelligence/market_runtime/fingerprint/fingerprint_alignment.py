"""Edge-specific fingerprint compatibility — fixed weights, not tuned."""
from __future__ import annotations


def fingerprint_alignment(edge_name: str, fp: dict[str, float]) -> float:
    weights = {
        "london_breakout": {
            "session_imbalance": 0.35,
            "compression_persistence": 0.25,
            "expansion_decay": 0.2,
        },
        "asia_compression": {
            "compression_persistence": 0.4,
            "expansion_decay": 0.3,
            "volatility_asymmetry": 0.15,
        },
        "volatility_exhaustion": {
            "directional_persistence_burst": 0.35,
            "expansion_decay": 0.25,
            "reaction_asymmetry": 0.2,
        },
        "liquidity_vacuum": {
            "liquidity_stress": 0.4,
            "directional_persistence_burst": 0.25,
        },
        "compression_release": {
            "expansion_decay": 0.35,
            "reaction_asymmetry": 0.3,
            "liquidity_stress": 0.2,
        },
    }
    w = weights.get(edge_name, {"expansion_decay": 0.5})
    score = total = 0.0
    for k, wt in w.items():
        v = fp.get(k, 0.5)
        score += wt * min(1.0, max(0.0, v if k != "reaction_asymmetry" else abs(v)))
        total += wt
    return float(score / total) if total else 0.5
