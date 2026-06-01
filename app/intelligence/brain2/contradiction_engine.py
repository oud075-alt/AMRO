"""Contradiction engine — prioritize conflicting runtime semantics."""
from __future__ import annotations

from app.intelligence.brain2.memory_loader import SemanticMemoryStore
from app.intelligence.brain2.models import ContradictionRecord


def detect_contradictions(
    *,
    market_state: str,
    tradable: bool,
    structure_confidence: float,
    instability: float,
    environment_quality: float,
    edge_strength: float,
    edge_detected: bool,
    event_risk: float,
    invalidate_trade: bool,
    memory: SemanticMemoryStore,
    entropy: float = 0.0,
    synthetic_similarity: float = 0.0,
    distribution_shift: float = 0.0,
    slip_ok: bool = True,
    spread_ok: bool = True,
    fill_ok: bool = True,
    lat_ok: bool = True,
    exec_guards_ok: bool = True,
    replay_mismatch: bool = False,
    contradiction_pressure_prior: float = 0.0,
) -> list[ContradictionRecord]:
    records: list[ContradictionRecord] = []

    def add(conflict: list[str], interpretation: str, severity: float, note: str, cid: str) -> None:
        records.append(ContradictionRecord(
            contradiction_id=cid,
            observed_conflict=conflict,
            interpretation=interpretation,
            severity=min(1.0, severity),
            governance_note=note,
        ))

    if edge_detected and edge_strength > 0.4 and environment_quality < 0.35:
        add(
            ["behavioral edge active", "weak edge environment", "low participation quality"],
            "false confidence risk",
            0.72,
            "reduce trust in continuation",
            "RUNTIME_CONTRA_EDGE_ENV",
        )

    if structure_confidence > 0.55 and instability > 0.65:
        add(
            ["structure confidence elevated", "instability elevated"],
            "unstable continuation",
            0.68,
            "reduce exposure",
            "RUNTIME_CONTRA_CONF_INST",
        )

    if market_state in ("tradable", "unstable") and not tradable:
        add(
            [f"market_state={market_state}", "tradable=false"],
            "semantic state conflict",
            0.61,
            "verify before participation",
            "RUNTIME_CONTRA_TRADABLE",
        )

    if edge_strength > 0.45 and structure_confidence < 0.35:
        add(
            ["breakout/edge signal", "weak structure confidence"],
            "trap probability elevated",
            0.74,
            "reduce trust in breakout",
            "RUNTIME_CONTRA_BREAKOUT",
        )

    if invalidate_trade and structure_confidence > 0.5:
        add(
            ["context invalidates trade", "structure appears stable"],
            "context-structure divergence",
            0.66,
            "context overrides structure lean",
            "RUNTIME_CONTRA_CONTEXT",
        )

    if event_risk >= 0.6 and edge_strength > 0.35:
        add(
            [f"event_risk={event_risk:.2f}", "edge activity present"],
            "event-edge conflict",
            0.70,
            "stand down until event risk clears",
            "RUNTIME_CONTRA_EVENT",
        )

    if not spread_ok and edge_strength > 0.4:
        add(
            ["spread guard fail", "edge signal active", "adverse selection risk"],
            "microstructure rejects breakout narrative",
            0.78,
            "execution pathology overrides signal",
            "RUNTIME_CONTRA_SPREAD_EDGE",
        )

    if not exec_guards_ok and structure_confidence > 0.5:
        add(
            ["execution guards fail", "structure confidence elevated"],
            "implementation shortfall dominates theoretical edge",
            0.82,
            "fail-closed on execution pathology",
            "RUNTIME_CONTRA_EXEC_PATH",
        )

    if not slip_ok and not fill_ok:
        add(
            ["slippage spike", "fill degradation", "liquidity collapse sequence"],
            "volatility-liquidity feedback — resiliency collapse",
            0.75,
            "reduce exposure immediately",
            "RUNTIME_CONTRA_LIQ_COLLAPSE",
        )

    if replay_mismatch:
        add(
            ["replay signature mismatch", "prior semantic stability"],
            "replay/live divergence — confidence decay required",
            0.71,
            "verify live behavior before participation upgrade",
            "RUNTIME_CONTRA_REPLAY",
        )

    if entropy >= 0.6 and synthetic_similarity >= 0.55 and edge_strength > 0.35:
        add(
            ["high entropy", "synthetic similarity", "edge present"],
            "noise trader risk — limits to arbitrage",
            0.69,
            "mispricing may widen before correction",
            "RUNTIME_CONTRA_NOISE",
        )

    if distribution_shift >= 0.45 and environment_quality < 0.4:
        add(
            ["distribution shift", "weak edge environment"],
            "cross-regime semantic shift in progress",
            0.67,
            "wait confirmation — regime mutation",
            "RUNTIME_CONTRA_REGIME_SHIFT",
        )

    if contradiction_pressure_prior >= 0.45:
        add(
            ["prior contradiction accumulation", "new runtime signals"],
            "contradiction accumulation — semantic compression required",
            0.64 + min(0.15, contradiction_pressure_prior * 0.2),
            "freeze participation upgrade",
            "RUNTIME_CONTRA_ACCUM",
        )

    # Match research-pack contradiction templates
    for tpl in memory.contradictions[:20]:
        tpl_conflicts = [str(x).lower() for x in tpl.get("observed_conflict") or []]
        if not tpl_conflicts:
            continue
        hits = 0
        if any("liquidity" in c for c in tpl_conflicts) and (environment_quality < 0.4 or not fill_ok):
            hits += 1
        if any("breakout" in c for c in tpl_conflicts) and edge_strength > 0.35 and structure_confidence < 0.45:
            hits += 1
        if any("continuation" in c for c in tpl_conflicts) and instability > 0.55:
            hits += 1
        if any("spread" in c for c in tpl_conflicts) and not spread_ok:
            hits += 1
        if any("replay" in c for c in tpl_conflicts) and replay_mismatch:
            hits += 2
        if any("noise" in c for c in tpl_conflicts) and entropy >= 0.6:
            hits += 1
        if any("slippage" in c or "fill" in c for c in tpl_conflicts) and (not slip_ok or not fill_ok):
            hits += 1
        min_hits = 2 if "replay" not in " ".join(tpl_conflicts) else 1
        if hits >= min_hits:
            prior = float(tpl.get("severity_prior", 0.65))
            records.append(ContradictionRecord(
                contradiction_id=str(tpl.get("contradiction_id", "PACK_CONTRA")),
                observed_conflict=[str(x) for x in tpl.get("observed_conflict") or []],
                interpretation=str(
                    tpl.get("emotional_interpretation")
                    or tpl.get("behavioral_interpretation")
                    or "pattern conflict"
                ),
                severity=min(1.0, prior + hits * 0.04),
                governance_note=str(tpl.get("governance_note") or "reduce trust"),
            ))

    dedup: dict[str, ContradictionRecord] = {}
    for r in records:
        if r.contradiction_id not in dedup or r.severity > dedup[r.contradiction_id].severity:
            dedup[r.contradiction_id] = r
    return sorted(dedup.values(), key=lambda r: r.severity, reverse=True)[:8]


def contradiction_pressure(records: list[ContradictionRecord]) -> float:
    if not records:
        return 0.0
    return min(1.0, sum(r.severity for r in records) / max(1, len(records) + 1))
