"""
AI pipeline — orchestrates intelligence flow only.
No BUY/SELL, no execution, no position sizing. EA receives governance permission only.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from loguru import logger

from app.intelligence.runtime_orchestrator import run_runtime


@dataclass
class PipelineResult:
    symbol: str
    timestamp: str
    pipeline_version: str = "7.0"
    approved: bool = False
    risk_mode: str = "blocked"
    position_limit: float = 0.0
    governance_reason: str = ""
    context_state: dict = field(default_factory=dict)
    market_runtime_state: dict = field(default_factory=dict)
    governance_decision: dict = field(default_factory=dict)
    runtime_metrics: dict = field(default_factory=dict)
    final_execution_reason: str = ""


def run_pipeline(
    symbol: str,
    interval: str = "1h",
    base_lot: float = 0.10,
    publish_permission: bool = True,
) -> PipelineResult:
    start = time.time()
    ts = datetime.utcnow().isoformat()
    result = PipelineResult(symbol=symbol, timestamp=ts)

    runtime = run_runtime(
        symbol=symbol,
        interval=interval,
        days=30,
        run_context_llm=True,
        log_decision=True,
        publish_to_ea=publish_permission,
    )

    if runtime is None:
        result.governance_reason = "insufficient_data"
        result.final_execution_reason = "fail_closed_no_data"
        logger.info(f"[Pipeline] FAIL CLOSED — no data for {symbol}")
        return result

    gov = runtime.governance
    result.approved = runtime.approved
    result.risk_mode = runtime.risk_mode
    result.position_limit = runtime.position_limit
    result.governance_reason = gov.reason
    result.context_state = runtime.context.to_dict()
    result.market_runtime_state = runtime.market_audit.to_dict()
    result.governance_decision = gov.to_dict()
    result.runtime_metrics = runtime.runtime_metrics or {}
    result.final_execution_reason = runtime.final_execution_reason

    elapsed = time.time() - start
    logger.info(f"[Pipeline] DONE {elapsed:.1f}s approved={result.approved}")
    return result
