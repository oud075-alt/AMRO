"""
Sole telemetry trace system — records full execution decision lineage.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any

import numpy as np
from loguru import logger

_LOG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "runtime_logs",
)


def _sanitize_json(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _sanitize_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_json(v) for v in obj]
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    return obj


@dataclass
class DecisionLineage:
    timestamp: str
    symbol: str
    context_state: dict
    edge_state: dict
    abstention_state: dict
    governance_state: dict
    runtime_state: dict
    allocation_state: dict
    execution_outcome: dict
    final_execution_reason: str
    approved: bool
    position_limit: float
    market_runtime_state: dict | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_lineage(**kwargs) -> DecisionLineage:
    return DecisionLineage(
        timestamp=datetime.now(timezone.utc).isoformat(),
        **kwargs,
    )


def record_lineage(lineage: DecisionLineage) -> str:
    os.makedirs(_LOG_DIR, exist_ok=True)
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = os.path.join(_LOG_DIR, f"decisions_{day}.jsonl")
    record = _sanitize_json(lineage.to_dict())
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    logger.debug(f"[DecisionLineage] {path}")
    return path
