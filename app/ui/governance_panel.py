"""
Market governance panel — STATE / CAUSE / EVIDENCE from measurable runtime telemetry.
Thresholds are explicit and auditable; no fabricated KPIs or narrative theatre.
"""
from __future__ import annotations

from typing import Any

# Execution filter thresholds (documented for UI audit traceability)
THRESHOLDS = {
    "market_quality_min": 0.35,
    "abstention_pressure_limit": 0.35,
    "entropy_max": 0.72,
    "structure_confidence_directional": 0.55,
    "edge_environment_quality_min": 0.35,
    "distribution_shift_max": 0.62,
}

# Replay / guard checks → operational statements (no raw field names on UI)
INTEGRITY_CHECKS: dict[str, tuple[str, str]] = {
    "runtime_parity": ("Runtime parity verified", "Runtime parity not verified"),
    "governance_consistent": ("Governance consistency verified", "Governance consistency not verified"),
    "abstention_consistent": ("Abstention consistency verified", "Abstention consistency not verified"),
    "execution_consistent": ("Execution consistency verified", "Execution consistency not verified"),
}
# Main UI: only the two highest-signal integrity checks
INTEGRITY_UI_KEYS: tuple[str, ...] = ("runtime_parity", "governance_consistent")


def _fmt(v: float | int | None) -> str | None:
    if v is None:
        return None
    return f"{float(v):.2f}"


def _evidence(metric: str, observed: float | None, required: float | None, rule: str) -> dict[str, Any]:
    return {
        "metric": metric,
        "observed": _fmt(observed),
        "required": _fmt(required),
        "rule": rule,
    }


def _evidence_fails_threshold(ev: dict[str, Any]) -> bool:
    """True only when observed/required comparison indicates failure (matches build rules)."""
    rule = ev.get("rule") or "min"
    metric = str(ev.get("metric") or "")
    obs_raw = ev.get("observed")
    req_raw = ev.get("required")

    if rule == "eq":
        if metric == "abstention_flag":
            return str(obs_raw).lower() == "true"
        if metric == "market_tradable":
            return str(obs_raw).lower() == "false"
        if metric == "dominant_edge":
            return not obs_raw or str(obs_raw) == "(none)"
        if metric == "regime":
            obs = str(obs_raw or "").upper()
            return obs == "RANGING"
        return False

    if obs_raw is None or req_raw is None:
        return False
    try:
        obs = float(obs_raw)
        req = float(req_raw)
    except (TypeError, ValueError):
        return False

    if rule == "min":
        return obs < req
    if rule == "max":
        if metric == "abstention_pressure":
            return obs >= req
        return obs > req
    return False


def _integrity_item(metric_key: str, passed: bool) -> dict[str, Any]:
    ok_msg, fail_msg = INTEGRITY_CHECKS[metric_key]
    return {
        "statement": ok_msg if passed else fail_msg,
        "tone": "integrity" if passed else "weak",
        "passed": passed,
        "metric": metric_key,
    }


# Failed-metric → compact execution-denial line (keyed on runtime evidence metric)
_DENIAL_BY_METRIC: dict[str, str] = {
    "abstention_flag": "Execution approval denied by abstention governance",
    "abstention_pressure": "Execution approval denied — abstention pressure above execution limit",
    "market_quality": "Execution approval denied — participation quality below threshold",
    "entropy_score": "Execution approval denied — market noise above execution limit",
    "distribution_shift": "Execution approval denied — distribution shift above execution limit",
    "edge_environment_quality": "Execution approval denied — edge environment quality below threshold",
    "market_tradable": "Execution approval denied — market not tradable under current audit",
    "regime": "Execution approval denied — directional acceptance unresolved",
    "structure_confidence": "Execution approval denied — structure confidence below threshold",
    "dominant_edge": "Execution approval denied — no dominant behavioral edge",
}


def _approval_denial_summary(
    causes: list[dict[str, Any]],
    primary: dict[str, str],
) -> str | None:
    """One compact denial line from the first failing governance cause (runtime-bound)."""
    if primary.get("tone") == "valid" or not causes:
        return None
    for ev in causes[0].get("evidence") or []:
        if not _evidence_fails_threshold(ev):
            continue
        metric = str(ev.get("metric") or "")
        if metric in _DENIAL_BY_METRIC:
            return _DENIAL_BY_METRIC[metric]
    cause = (causes[0].get("cause") or "").strip()
    if cause:
        return f"Execution approval denied — {cause.lower()}"
    return None


def _conclusion_evidence_line(causes: list[dict[str, Any]]) -> str | None:
    """One provable line from the first failing metric only (must pass threshold check)."""
    if not causes:
        return None
    for ev in causes[0].get("evidence") or []:
        if not _evidence_fails_threshold(ev):
            continue
        obs = ev.get("observed")
        req = ev.get("required")
        rule = ev.get("rule") or "min"
        if rule in ("min", "max") and req is not None:
            return f"Observed: {obs} · Required: {req}"
        if rule == "eq" and ev.get("metric") == "abstention_flag":
            return "Abstention flag active"
    return None


def _governance_conclusion(
    causes: list[dict[str, Any]],
    primary: dict[str, str],
    approved: bool,
) -> dict[str, Any]:
    if causes:
        out: dict[str, Any] = {
            "statement": causes[0]["cause"],
            "tone": causes[0].get("tone", "weak"),
        }
        line = _conclusion_evidence_line(causes)
        if line:
            out["evidence_line"] = line
        denial = _approval_denial_summary(causes, primary)
        if denial:
            out["denial_summary"] = denial
        return out
    if approved and primary.get("tone") == "valid":
        return {"statement": "Execution governance cleared", "tone": "valid"}
    if not approved:
        return {"statement": primary.get("state", "Execution not permitted"), "tone": "blocked"}
    return {
        "statement": primary.get("state", "Governance state pending"),
        "tone": primary.get("tone", "weak"),
    }


def _primary_execution_state(approved: bool, verdict: str, abstain: bool) -> dict[str, str]:
    v = verdict.upper()
    if v in ("BLOCK", "DISABLE"):
        return {"state": "Execution blocked", "tone": "blocked", "verdict": v}
    if not approved:
        if v == "LIMIT":
            return {"state": "Execution not permitted", "tone": "blocked", "verdict": "LIMIT"}
        if v == "ABSTAIN" or abstain:
            return {"state": "Execution not permitted", "tone": "blocked", "verdict": "ABSTAIN"}
        return {"state": "Execution not permitted", "tone": "blocked", "verdict": v or "STANDBY"}
    if v == "LIMIT":
        return {"state": "Execution limited", "tone": "weak", "verdict": "LIMIT"}
    return {"state": "Execution permitted", "tone": "valid", "verdict": v or "ALLOW"}


def build_governance_panel(payload: dict[str, Any]) -> dict[str, Any]:
    audit = payload.get("market_audit") or {}
    abst = payload.get("abstention") or {}
    gov = payload.get("governance") or {}
    rm = payload.get("runtime_metrics") or {}
    edges = payload.get("behavioral_edges") or {}
    approved = payload.get("approved", False)
    regime = (payload.get("regime") or "").upper()
    replay = payload.get("replay_validation")
    verdict = str(gov.get("verdict", rm.get("governance_state", ""))).upper()
    abstain = bool(abst.get("abstain", False))

    conf = audit.get("structure_confidence")
    pressure = rm.get("abstention_pressure")
    if pressure is None:
        pressure = abst.get("abstention_pressure")
    mq = rm.get("market_quality")
    ent = audit.get("entropy_score")
    env_q = edges.get("environment_quality")
    if rm.get("edge_environment_quality") is not None:
        env_q = rm.get("edge_environment_quality")
    dominant = edges.get("dominant_edge") or ""
    tradable = audit.get("tradable", True)
    shift = audit.get("distribution_shift")

    primary = _primary_execution_state(approved, verdict, abstain)
    causes: list[dict[str, Any]] = []

    # ── Participation: one primary cause, evidence only for metrics that failed ──
    if abstain:
        causes.append({
            "cause": "Abstention active",
            "tone": "weak",
            "evidence": [{"metric": "abstention_flag", "observed": "true", "required": "false", "rule": "eq"}],
        })
    elif pressure is not None and pressure >= THRESHOLDS["abstention_pressure_limit"]:
        causes.append({
            "cause": "Abstention pressure above execution limit",
            "tone": "weak",
            "evidence": [_evidence("abstention_pressure", pressure, THRESHOLDS["abstention_pressure_limit"], "max")],
        })
    elif mq is not None and mq < THRESHOLDS["market_quality_min"]:
        causes.append({
            "cause": "Participation quality below required threshold",
            "tone": "weak",
            "evidence": [_evidence("market_quality", mq, THRESHOLDS["market_quality_min"], "min")],
        })
    elif ent is not None and ent > THRESHOLDS["entropy_max"]:
        causes.append({
            "cause": "Market noise above execution limit",
            "tone": "weak",
            "evidence": [_evidence("entropy_score", ent, THRESHOLDS["entropy_max"], "max")],
        })

    # ── Continuation structure (only failed checks in evidence) ──
    if tradable is False:
        causes.append({
            "cause": "Market not tradable under current audit",
            "tone": "weak",
            "evidence": [{"metric": "market_tradable", "observed": "false", "required": "true", "rule": "eq"}],
        })
    elif shift is not None and shift > THRESHOLDS["distribution_shift_max"]:
        causes.append({
            "cause": "Distribution shift above execution limit",
            "tone": "weak",
            "evidence": [_evidence("distribution_shift", shift, THRESHOLDS["distribution_shift_max"], "max")],
        })
    elif not dominant and env_q is not None and env_q < THRESHOLDS["edge_environment_quality_min"]:
        causes.append({
            "cause": "Edge environment quality below threshold",
            "tone": "weak",
            "evidence": [_evidence("edge_environment_quality", env_q, THRESHOLDS["edge_environment_quality_min"], "min")],
        })

    # ── Directional context ──
    market_state = str(audit.get("market_state", "")).lower()
    if regime == "RANGING" or market_state == "ranging":
        causes.append({
            "cause": "Directional acceptance unresolved",
            "tone": "weak",
            "evidence": [{"metric": "regime", "observed": regime or market_state, "required": "TRENDING_*|BREAKOUT", "rule": "enum"}],
        })
    elif (
        conf is not None
        and conf < THRESHOLDS["structure_confidence_directional"]
        and regime not in ("TRENDING_UP", "TRENDING_DOWN", "BREAKOUT")
    ):
        causes.append({
            "cause": "Structure confidence below directional threshold",
            "tone": "weak",
            "evidence": [_evidence("structure_confidence", conf, THRESHOLDS["structure_confidence_directional"], "min")],
        })

    env = payload.get("market_environment") or {}
    upside_pct = env.get("upside_pressure_pct")
    downside_pct = env.get("downside_pressure_pct")
    governance_overrides = not approved or verdict in ("BLOCK", "DISABLE", "LIMIT", "ABSTAIN")

    # ── Runtime integrity (replay / guards) — readable validation only ──
    integrity_items: list[dict[str, Any]] = []
    integrity_available = False
    if replay and isinstance(replay, dict):
        integrity_available = True
        for key in INTEGRITY_UI_KEYS:
            if key in replay:
                integrity_items.append(_integrity_item(key, bool(replay.get(key))))
    elif rm.get("execution_guards_ok") is False:
        integrity_available = True
        integrity_items.append({
            "statement": "Execution guards not verified",
            "tone": "weak",
            "passed": False,
            "metric": "execution_guards_ok",
        })

    conclusion = _governance_conclusion(causes, primary, approved)

    b2 = payload.get("brain2_cognition") or {}
    cognition_risk = b2.get("cognition_risk")
    if not cognition_risk and b2:
        cognition_risk = {
            "contradiction_pressure": max(
                float(b2.get("contradiction_pressure") or 0),
                float(b2.get("accumulated_contradiction_pressure") or 0),
            ),
            "instability_level": "elevated" if float(b2.get("instability_probability") or 0) >= 0.55 else "moderate" if float(b2.get("instability_probability") or 0) >= 0.28 else "low",
            "execution_fragility": "fragile" if rm.get("execution_guards_ok") is False else "stable",
            "replay_live_distrust": (b2.get("replay_divergence") or {}).get("distrust_level", "unknown"),
            "semantic_confidence": float(b2.get("governance_confidence") or b2.get("semantic_confidence") or 0),
            "regime_instability": "shifting" if (audit.get("distribution_shift") or 0) > 0.45 else "stable",
        }

    # Legacy flat list for any old consumers
    governance_states = [{"statement": primary["state"], "tone": primary["tone"]}]
    for c in causes:
        governance_states.append({"statement": c["cause"], "tone": c["tone"]})

    return {
        "thresholds": THRESHOLDS,
        "telemetry": {
            "approved": bool(approved),
            "verdict": verdict or None,
            "abstain": bool(abstain),
            "regime": regime or None,
            "market_state": str(audit.get("market_state") or "") or None,
            "market_quality": mq,
            "abstention_pressure": pressure,
            "entropy_score": ent,
            "structure_confidence": conf,
            "edge_environment_quality": env_q,
            "distribution_shift": shift,
            "market_tradable": tradable,
            "dominant_edge": dominant or None,
            "replay_validation_present": bool(replay),
            "execution_guards_ok": rm.get("execution_guards_ok"),
        },
        "primary_state": primary,
        "governance_conclusion": conclusion,
        "causes": causes,
        "runtime_integrity": {
            "available": integrity_available and len(integrity_items) > 0,
            "items": integrity_items,
            "fallback": None if integrity_available else "Validation unavailable",
        },
        "governance_hierarchy": {
            "execution_overrides_environment": governance_overrides,
            "note": (
                "Governance filters execution; environment lean is context only."
                if governance_overrides
                else None
            ),
            "environment_upside_pressure_pct": upside_pct,
            "environment_downside_pressure_pct": downside_pct,
        },
        "governance_states": governance_states,
        "cognition_risk": cognition_risk,
        # Legacy alias — same payload as runtime_integrity
        "governance_impact": {
            "available": integrity_available and len(integrity_items) > 0,
            "status": "replay_evidence_present" if replay else "validation_unavailable",
            "items": integrity_items,
            "fallback": None if integrity_available else "Validation unavailable",
        },
    }
