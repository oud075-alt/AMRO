"""
AMRO — Signal API Routes
GET /api/signals/{symbol}

Runtime pipeline (v3):
  market_data → AI#1 context → AI#2 market audit → AI#3 governance → response

Legacy signal_engine / alpha-brain voting is NOT in this path.
"""
from fastapi import APIRouter, Depends, Query
from datetime import datetime, timedelta, timezone
from loguru import logger

from app.core.tiers import Tier, get_tier_config
from app.core.json_utils import json_sanitize
from app.ui.governance_panel import build_governance_panel
from app.services.auth import get_current_tier
from app.intelligence.runtime_orchestrator import run_runtime
from app.intelligence.regime_detector import detect_regime
from app.intelligence.market_data import fetch_market_data
from app.intelligence import brain_stack

router = APIRouter(prefix="/api/signals", tags=["signals"])


@router.get("/{symbol:path}")
async def get_signal(
    symbol: str,
    interval: str = Query("1h", description="1m|5m|15m|1h|4h|1d"),
    audit: bool = Query(False, description="Include extended audit payload"),
    current_tier: Tier = Depends(get_current_tier),
):
    config = get_tier_config(current_tier)

    tier_days = max(config.history_days, 30)
    # Trial/subscription tiers request 90d+ but Yahoo/Kraken on VPS fail on long windows (NZD/USD etc.).
    fetch_days = min(tier_days, 30)
    df = fetch_market_data(symbol=symbol, interval=interval, days=fetch_days)
    if df.empty:
        return {"error": f"ไม่พบข้อมูลสำหรับ {symbol}"}

    # Free tier delay
    if config.signal_delay_minutes > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=config.signal_delay_minutes)
        if df.index.tzinfo is None:
            cutoff = cutoff.replace(tzinfo=None)
        df = df[df.index < cutoff]
        if df.empty:
            return {
                "symbol": symbol,
                "tier": current_tier,
                "message": f"Signal ล่าช้า {config.signal_delay_minutes} นาที สำหรับ free tier",
                "delayed": True,
            }

    decision = run_runtime(
        symbol=symbol,
        interval=interval,
        days=fetch_days,
        run_context_llm=brain_stack.brain1_active(),
        log_decision=True,
        df=df,
    )

    if decision is None:
        return {
            "symbol": symbol,
            "direction": "ABSTAIN",
            "approved": False,
            "risk_mode": "NO_TRADE",
            "governance": {"approved": False, "reason": "insufficient_data", "risk_mode": "NO_TRADE"},
            "architecture": "context_audit_governance_v3",
        }

    response = decision.to_api_response(
        tier=current_tier,
        delayed=config.signal_delay_minutes > 0,
    )

    if decision.market_environment:
        response["market_environment"] = decision.market_environment

    # Regime detail
    regime = detect_regime(df)
    if config.regime_detection:
        response["regime_detail"] = {
            "type": regime.regime,
            "confidence": regime.confidence,
            "description": regime.description,
            "governance_guidance": regime.trade_advice,
            "metrics": regime.metrics,
        }

    # Extended audit scores (subscription+)
    if current_tier != Tier.FREE:
        m = decision.market_audit
        response["audit_scores"] = {
            "structure_confidence": m.structure_confidence,
            "instability_score": m.instability_score,
            "entropy_score": m.entropy_score,
            "synthetic_similarity": m.synthetic_similarity,
            "volatility_coherence": m.volatility_coherence,
            "distribution_shift": m.distribution_shift,
            "signal_reliability": m.signal_reliability,
            "notes": m.notes or [],
            "market_state": m.market_state,
            "tradable": m.tradable,
        }

    if audit or config.audit_agent:
        env = decision.market_environment or {}
        response["audit_result"] = env
        if not decision.approved:
            response["audit_skipped"] = "Participation not approved — see governance status"

    response["market_governance"] = build_governance_panel(response)

    return json_sanitize(response)
