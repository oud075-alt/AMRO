"""
AMRO — EA Bridge API
Endpoints ที่ MT5 EA ใช้สื่อสารกับ server

POST /api/ea/telemetry   — EA ส่ง event log
GET  /api/ea/decision    — EA poll governance permission ล่าสุด
POST /api/ea/report      — EA report ผล trade
POST /api/ea/heartbeat   — EA heartbeat / health ping
"""
from datetime import datetime, timezone
import time as _time
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from loguru import logger

from app.core.config import settings

router = APIRouter(prefix="/api/ea", tags=["EA Bridge"])


# ── In-memory store (replace with DB/Redis in production) ─────────
_decision_store: dict = {}      # symbol → decision dict
_telemetry_log:  list = []      # rolling log (capped at 500 entries)
_reports:        list = []      # trade reports
_heartbeats:     dict = {}      # symbol → latest heartbeat


# ── Schemas ────────────────────────────────────────────────────────

class TelemetryPayload(BaseModel):
    symbol:  str
    event:   str
    detail:  str
    price:   float = 0.0
    ticket:  int   = 0
    ts:      int   = 0          # unix timestamp from EA

class HeartbeatPayload(BaseModel):
    symbol:         str
    status:         str
    open_positions: int   = 0
    equity:         float = 0.0
    balance:        float = 0.0
    ts:             int   = 0

class ReportPayload(BaseModel):
    symbol: str
    action: str                 # OPEN / CLOSE / MODIFY
    ticket: int   = 0
    lot:    float = 0.0
    entry:  float = 0.0
    sl:     float = 0.0
    tp:     float = 0.0
    reason: str   = ""
    ts:     int   = 0

class DecisionResponse(BaseModel):
    symbol: str
    permission: str             # ALLOW / LIMIT / ABSTAIN / BLOCK / DISABLE
    approved: bool
    max_lot_scale: float
    risk_state: str
    governance_verdict: str
    execution_reason: str
    uncertainty: float = 1.0
    confidence: float = 0.0
    expires_at: int = 0         # unix — EA must fail closed after expiry
    timestamp: int              # unix — EA uses this for stale check


# ── Endpoints ──────────────────────────────────────────────────────

@router.post("/telemetry", status_code=200)
async def receive_telemetry(payload: TelemetryPayload):
    """EA ส่ง telemetry event มาเก็บไว้"""
    entry = payload.model_dump()
    entry["received_at"] = datetime.utcnow().isoformat()
    _telemetry_log.append(entry)

    # cap at 500
    if len(_telemetry_log) > 500:
        _telemetry_log.pop(0)

    logger.info(f"[EA Telemetry] {payload.symbol} | {payload.event} | {payload.detail}")
    return {"ok": True}


@router.post("/heartbeat", status_code=200)
async def receive_heartbeat(payload: HeartbeatPayload):
    """EA heartbeat — confirms EA is alive"""
    _heartbeats[payload.symbol] = {
        **payload.model_dump(),
        "received_at": datetime.utcnow().isoformat(),
    }
    logger.debug(f"[EA Heartbeat] {payload.symbol} status={payload.status} "
                 f"eq={payload.equity:.2f} open={payload.open_positions}")
    return {"ok": True}


@router.post("/report", status_code=200)
async def receive_report(payload: ReportPayload):
    """EA reports trade execution result"""
    entry = payload.model_dump()
    entry["received_at"] = datetime.utcnow().isoformat()
    _reports.append(entry)

    if len(_reports) > 1000:
        _reports.pop(0)

    logger.info(f"[EA Report] {payload.symbol} | {payload.action} "
                f"ticket={payload.ticket} lot={payload.lot} entry={payload.entry}")
    return {"ok": True}


@router.get("/decision", response_model=DecisionResponse)
async def get_decision(symbol: str):
    """
    EA polls ตรงนี้ทุก N วินาที
    คืน permission ล่าสุดที่ governance publish ไว้
    ถ้าไม่มี → คืน BLOCK/ABSTAIN แบบ fail-closed
    """
    if symbol not in _decision_store:
        return DecisionResponse(
            symbol=symbol,
            permission="ABSTAIN",
            approved=False,
            max_lot_scale=0.0,
            risk_state="NO_DECISION",
            governance_verdict="ABSTAIN",
            execution_reason="No governance permission available for this symbol",
            uncertainty=1.0,
            confidence=0.0,
            expires_at=0,
            timestamp=0,
        )

    d = _decision_store[symbol]
    return DecisionResponse(**d)


# ── Internal: called by pipeline to publish decision ──────────────

def publish_decision(
    symbol: str,
    approved: bool,
    permission: str,
    max_lot_scale: float,
    risk_state: str,
    governance_verdict: str,
    execution_reason: str,
    uncertainty: float = 1.0,
    confidence: float = 0.0,
    ttl_seconds: int = 90,
):
    """
    Pipeline สร้าง governance permission แล้วเรียก publish_decision()
    เพื่อให้ EA poll ได้โดย fail-closed ไม่ใช่รับ BUY/SELL signal
    """
    now = int(_time.time())
    _decision_store[symbol] = {
        "symbol": symbol,
        "permission": permission,
        "approved": approved,
        "max_lot_scale": max(0.0, min(1.0, float(max_lot_scale))),
        "risk_state": risk_state,
        "governance_verdict": governance_verdict,
        "execution_reason": execution_reason,
        "uncertainty": max(0.0, min(1.0, float(uncertainty))),
        "confidence": max(0.0, min(1.0, float(confidence))),
        "expires_at": now + max(1, int(ttl_seconds)),
        "timestamp": now,
    }
    logger.info(
        f"[EA Bridge] Published permission: {symbol} "
        f"permission={permission} approved={approved} scale={max_lot_scale}"
    )


def get_decision_snapshot(symbol: str | None = None) -> dict:
    """Internal/admin helper for current in-memory EA permissions."""
    if symbol:
        return _decision_store.get(symbol, {})
    return dict(_decision_store)


# ── Test / Debug endpoint ─────────────────────────────────────────

@router.post("/test-permission")
async def inject_test_permission(
    symbol:     str   = "XAUUSD",
    permission: str   = "LIMIT",
    max_lot_scale: float = 0.25,
):
    """
    inject test permission เพื่อทดสอบว่า EA รับ governance permission ได้จริง
    (ใช้ใน development เท่านั้น)
    """
    if settings.APP_ENV != "development":
        raise HTTPException(status_code=404, detail="Not found")

    publish_decision(
        symbol=symbol,
        approved=permission.upper() in ("ALLOW", "LIMIT"),
        permission=permission.upper(),
        max_lot_scale=max_lot_scale,
        risk_state="TEST_PERMISSION",
        governance_verdict=permission.upper(),
        execution_reason=f"TEST PERMISSION — {permission.upper()} injected manually",
        uncertainty=0.5,
        confidence=0.5,
    )
    logger.warning(f"[TEST] Injected test permission: {symbol} {permission} scale={max_lot_scale}")
    return {
        "ok": True,
        "message": f"Test permission injected: {symbol} {permission}",
        "permission": _decision_store.get(symbol),
    }


# ── Admin read endpoints ───────────────────────────────────────────

@router.get("/telemetry/log")
async def get_telemetry_log(limit: int = 50):
    """ดู telemetry log ล่าสุด (admin)"""
    return {"entries": _telemetry_log[-limit:]}


@router.get("/heartbeats")
async def get_heartbeats():
    """ดู heartbeat ล่าสุดจากทุก symbol"""
    return {"heartbeats": _heartbeats}


@router.get("/reports")
async def get_reports(limit: int = 50):
    """ดู trade reports ล่าสุด"""
    return {"reports": _reports[-limit:]}
