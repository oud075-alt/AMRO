"""Shared helpers for behavioral edge structure detection."""
from __future__ import annotations

import hashlib

import numpy as np


def clip(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return float(np.clip(v, lo, hi))


def replay_signature(edge_id: str, *values: float) -> str:
    payload = f"{edge_id}|" + "|".join(f"{v:.6f}" for v in values)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]
