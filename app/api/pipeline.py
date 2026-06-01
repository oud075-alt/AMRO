"""
AMRO — Pipeline API
POST /api/pipeline/run   — Context → Market Runtime → Governance (orchestration only)
GET  /api/pipeline/status — latest EA governance permission
"""
from fastapi import APIRouter, Query
from loguru import logger
from app.api.ea_bridge import get_decision_snapshot
from app.intelligence.ai_pipeline import run_pipeline

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


@router.post("/run")
async def run_ai_pipeline(
    symbol: str = Query("EURUSD=X", description="Symbol เช่น EURUSD=X, GC=F, BTC/USDT"),
    interval: str = Query("1h", description="Timeframe: 15m|1h|4h|1d"),
    base_lot: float = Query(0.10, description="Ignored — sizing is allocation authority"),
    dry_run: bool = Query(True, description="Reserved — no EA writes from pipeline"),
):
    logger.info(f"[API] Pipeline run: {symbol} {interval} dry_run={dry_run}")

    result = run_pipeline(
        symbol=symbol,
        interval=interval,
        base_lot=base_lot,
        publish_permission=not dry_run,
    )

    rm = result.runtime_metrics or {}
    return {
        "symbol": result.symbol,
        "timestamp": result.timestamp,
        "approved": result.approved,
        "risk_mode": result.risk_mode,
        "position_limit": result.position_limit,
        "governance_reason": result.governance_reason,
        "final_execution_reason": result.final_execution_reason,
        "architecture": "amro_consolidated_runtime_v7",
        "context_state": result.context_state,
        "market_runtime_state": result.market_runtime_state,
        "governance_decision": result.governance_decision,
        "runtime_metrics": {
            "runtime_trust": rm.get("runtime_trust"),
            "governance_state": rm.get("governance_state"),
            "abstention_pressure": rm.get("abstention_pressure"),
            "risk_pressure": rm.get("risk_pressure"),
            "market_quality": rm.get("market_quality"),
            "execution_health": rm.get("execution_health"),
            "runtime_health": rm.get("runtime_health"),
        },
    }


@router.get("/status")
async def get_permission_status(symbol: str | None = None):
    """ดู governance permission ล่าสุดที่ EA bridge ถืออยู่ใน memory."""
    data = get_decision_snapshot(symbol)
    if not data:
        return {"status": "no_permission", "message": "ยังไม่มี permission จาก governance"}
    return {"status": "ok", "permission": data}
