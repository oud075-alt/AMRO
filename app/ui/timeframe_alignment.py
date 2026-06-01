"""
Market participation flow — causal governance reasoning across timeframes.
Structural states only; no trade signals or narrative theatre.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from app.intelligence.market_data import fetch_market_data
from app.intelligence.regime_detector import RegimeResult, detect_regime
from app.intelligence.market_runtime.structure.audit_layer import AuditResult, compute_audit

TF_SPECS: list[tuple[str, str, int]] = [
    ("D1", "1d", 120),
    ("H4", "4h", 60),
    ("H1", "1h", 30),
    ("M15", "15m", 10),
]


def _tone_from_metrics(ent: float, inst: float, conf: float, shift: float) -> str:
    if ent > 0.74 or inst > 0.66 or conf < 0.38:
        return "conflict"
    if ent > 0.68 or inst > 0.58 or conf < 0.48 or shift > 0.58:
        return "weak"
    return "valid"


def _layer_reason_d1(regime: RegimeResult, audit: AuditResult) -> str:
    r = regime.regime
    if r in ("TRENDING_UP", "TRENDING_DOWN") and audit.instability_score < 0.62:
        direction = "up" if r == "TRENDING_UP" else "down"
        return f"macro trend intact ({direction} bias)"
    if r == "RANGING" and audit.entropy_score < 0.72:
        return "macro range intact"
    if r == "VOLATILE" or audit.instability_score > 0.7:
        return "macro volatility elevated"
    if audit.entropy_score > 0.78:
        return "macro participation unstable"
    return "macro structure unresolved"


def _layer_reason_h4(regime: RegimeResult, audit: AuditResult) -> str:
    r = regime.regime
    conf = audit.structure_confidence
    if r in ("TRENDING_UP", "TRENDING_DOWN") and conf >= 0.5:
        return "continuation participation present"
    if r == "BREAKOUT" and conf >= 0.45:
        return "continuation attempt in progress"
    if r == "RANGING":
        return "continuation participation absent"
    if conf < 0.4:
        return "continuation structure weak"
    if audit.distribution_shift > 0.6:
        return "continuation follow-through degraded"
    return "continuation participation absent"


def _layer_reason_h1(regime: RegimeResult, audit: AuditResult, df: pd.DataFrame) -> str:
    conf = audit.structure_confidence
    if conf < 0.42:
        return "directional acceptance weak"
    if regime.regime == "RANGING":
        return "directional acceptance unresolved"
    if len(df) >= 12:
        ret = float((df["close"].iloc[-1] - df["close"].iloc[-10]) / df["close"].iloc[-10])
        if abs(ret) < 0.002:
            return "directional acceptance flat"
        if ret > 0.006 and conf >= 0.5:
            return "directional acceptance improving"
        if ret > 0:
            return "directional acceptance weak"
        if ret < -0.006 and conf >= 0.5:
            return "directional acceptance improving (down)"
        return "directional acceptance weak"
    return "directional acceptance weak"


def _layer_reason_m15(regime: RegimeResult, audit: AuditResult) -> str:
    if audit.entropy_score > 0.75 or audit.instability_score > 0.65:
        return "rotational instability detected"
    if regime.regime == "VOLATILE":
        return "intraday volatility expansion"
    if regime.regime == "RANGING":
        return "rotational range behavior"
    if audit.distribution_shift > 0.62:
        return "intraday expansion unstable"
    return "intraday structure compressing"


def _governance_reason(ctx: dict[str, Any] | None) -> tuple[str, str]:
    if not ctx:
        return "execution governance pending", "weak"
    approved = ctx.get("approved", False)
    verdict = str(ctx.get("verdict", "")).upper()
    if not approved or verdict in ("BLOCK", "DISABLE", "ABSTAIN"):
        if verdict == "BLOCK":
            return "execution governance blocked", "blocked"
        if verdict == "DISABLE":
            return "execution governance disabled", "blocked"
        return "execution governance activated (standby)", "weak"
    if verdict == "LIMIT":
        return "execution governance activated (limited scale)", "weak"
    return "execution governance cleared for monitoring", "valid"


def _collect_layers(symbol: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for label, interval, days in TF_SPECS:
        try:
            df = fetch_market_data(symbol=symbol, interval=interval, days=days)
            if df.empty or len(df) < 50:
                out[label] = {"ok": False}
                continue
            regime = detect_regime(df)
            audit = compute_audit(df)
            tone = _tone_from_metrics(
                audit.entropy_score,
                audit.instability_score,
                audit.structure_confidence,
                audit.distribution_shift,
            )
            if label == "D1":
                reason = _layer_reason_d1(regime, audit)
            elif label == "H4":
                reason = _layer_reason_h4(regime, audit)
            elif label == "H1":
                reason = _layer_reason_h1(regime, audit, df)
            else:
                reason = _layer_reason_m15(regime, audit)
            out[label] = {
                "ok": True,
                "regime": regime.regime,
                "entropy": audit.entropy_score,
                "instability": audit.instability_score,
                "confidence": audit.structure_confidence,
                "shift": audit.distribution_shift,
                "tone": tone,
                "reason": reason,
            }
        except Exception:
            out[label] = {"ok": False}
    return out


def _build_causal_flow(
    layers: dict[str, dict[str, Any]],
    governance_ctx: dict[str, Any] | None,
) -> list[dict[str, str]]:
    flow: list[dict[str, str]] = []
    order = [
        ("D1", "D1"),
        ("H4", "H4"),
        ("H1", "H1"),
        ("M15", "M15"),
    ]
    for key, prefix in order:
        L = layers.get(key, {})
        if not L.get("ok"):
            flow.append({
                "layer": key,
                "prefix": prefix,
                "reason": f"{prefix.lower()} telemetry unavailable",
                "tone": "weak",
            })
        else:
            flow.append({
                "layer": key,
                "prefix": prefix,
                "reason": L["reason"],
                "tone": L["tone"],
            })
    gov_reason, gov_tone = _governance_reason(governance_ctx)
    flow.append({
        "layer": "GOVERNANCE",
        "prefix": "Runtime",
        "reason": gov_reason,
        "tone": gov_tone,
    })
    return flow


def _build_state_transition(
    layers: dict[str, dict[str, Any]],
    governance_ctx: dict[str, Any] | None,
) -> dict[str, Any]:
    m15 = layers.get("M15", {})
    h1 = layers.get("H1", {})
    h4 = layers.get("H4", {})
    d1 = layers.get("D1", {})

    if not all(x.get("ok") for x in (m15, h1, h4, d1)):
        return {
            "phase": "evaluating",
            "lines": ["Runtime transition mapping in progress", "Awaiting full timeframe telemetry"],
        }

    lines: list[str] = []
    phase = "stable"

    m15_ent = m15.get("entropy", 0.5)
    h1_ent = h1.get("entropy", 0.5)
    h4_conf = h4.get("confidence", 0.5)
    m15_inst = m15.get("instability", 0.5)

    if m15_ent > h1_ent + 0.06 and m15_inst > 0.55:
        lines.append("Participation quality weakening across intraday structure")
        lines.append("Awaiting higher timeframe confirmation")
        phase = "weakening"
    elif h4_conf < 0.45 and h1.get("regime") in ("TRENDING_UP", "TRENDING_DOWN", "BREAKOUT"):
        lines.append("Alignment attempting recovery after failed continuation sequence")
        phase = "recovering"
    elif m15.get("tone") == "conflict" and d1.get("tone") == "valid":
        lines.append("Lower timeframe conflict compressing against stable macro frame")
        lines.append("Execution filter holding until coherence improves")
        phase = "compressing"
    elif h1.get("tone") == "valid" and m15.get("tone") == "weak":
        lines.append("Intraday structure stabilizing under hourly acceptance")
        phase = "stabilizing"
    elif m15.get("tone") == "valid" and h4.get("tone") == "valid":
        lines.append("Participation coherence improving across monitored stack")
        phase = "improving"
    else:
        pressure = (governance_ctx or {}).get("abstention_pressure")
        if pressure is not None and pressure >= 0.45:
            lines.append("Abstention pressure elevated — transition remains constrained")
            phase = "constrained"
        else:
            lines.append("Participation transition neutral at current bar")
            phase = "neutral"

    return {"phase": phase, "lines": lines[:2]}


def compute_timeframe_alignment(
    symbol: str,
    governance_ctx: dict[str, Any] | None = None,
) -> dict[str, Any]:
    layers = _collect_layers(symbol)
    causal_flow = _build_causal_flow(layers, governance_ctx)
    state_transition = _build_state_transition(layers, governance_ctx)

    timeframes = []
    for label, _, _ in TF_SPECS:
        L = layers.get(label, {})
        timeframes.append({
            "timeframe": label,
            "state": L.get("reason", "unavailable") if L.get("ok") else "unavailable",
        })

    return {
        "timeframes": timeframes,
        "summary": None,
        "causal_flow": causal_flow,
        "state_transition": state_transition,
    }
