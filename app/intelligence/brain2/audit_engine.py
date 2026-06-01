"""Brain-2 data sufficiency self-audit — measurable gaps only, not quantity claims."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

from app.intelligence.brain2.memory_loader import SemanticMemoryStore


@dataclass
class DomainGap:
    domain: str
    coverage_score: float
    status: str  # weak | partial | covered
    measurable_gap: str
    operational_gap: str
    semantic_gap: str
    runtime_gap: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Brain2AuditReport:
    sufficient_for_behavioral_semantics: bool
    overall_coverage: float
    domain_gaps: list[DomainGap] = field(default_factory=list)
    blind_spots: list[str] = field(default_factory=list)
    weak_semantic_areas: list[str] = field(default_factory=list)
    overfit_risks: list[str] = field(default_factory=list)
    hallucination_risks: list[str] = field(default_factory=list)
    replay_live_gaps: list[str] = field(default_factory=list)
    structural_misunderstanding_risks: list[str] = field(default_factory=list)
    recommended_ingest_domains: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sufficient_for_behavioral_semantics": self.sufficient_for_behavioral_semantics,
            "overall_coverage": round(self.overall_coverage, 4),
            "domain_gaps": [d.to_dict() for d in self.domain_gaps],
            "blind_spots": self.blind_spots,
            "weak_semantic_areas": self.weak_semantic_areas,
            "overfit_risks": self.overfit_risks,
            "hallucination_risks": self.hallucination_risks,
            "replay_live_gaps": self.replay_live_gaps,
            "structural_misunderstanding_risks": self.structural_misunderstanding_risks,
            "recommended_ingest_domains": self.recommended_ingest_domains,
        }


_DOMAIN_SPECS: list[dict[str, Any]] = [
    {
        "domain": "market_microstructure",
        "keywords": ["adverse_selection", "bid_ask", "price_impact", "kyle", "amihud", "microstructure"],
        "runtime_keys": ["spread", "slippage", "fill"],
        "min_pack_hits": 3,
    },
    {
        "domain": "execution_degradation",
        "keywords": ["implementation_shortfall", "delay_cost", "execution_degradation", "slippage_escalation"],
        "runtime_keys": ["slippage", "latency", "fill_degradation"],
        "min_pack_hits": 2,
    },
    {
        "domain": "liquidity_collapse",
        "keywords": ["liquidity_stress", "liquidity_collapse", "thin_book", "illiquidity"],
        "runtime_keys": ["spread", "volume", "liquidity"],
        "min_pack_hits": 2,
    },
    {
        "domain": "contradiction_accumulation",
        "keywords": ["contradiction", "observed_conflict", "false_confidence"],
        "runtime_keys": ["contradiction_pressure"],
        "min_pack_hits": 4,
    },
    {
        "domain": "semantic_mutation",
        "keywords": ["regime_mutation", "narrative_drift", "distribution_shift"],
        "runtime_keys": ["distribution_shift", "synthetic_similarity"],
        "min_pack_hits": 2,
    },
    {
        "domain": "replay_live_divergence",
        "keywords": ["replay", "signature_mismatch", "live_divergence"],
        "runtime_keys": ["replay_mismatch", "replay_validation"],
        "min_pack_hits": 2,
    },
    {
        "domain": "market_physics",
        "keywords": ["volatility", "impact", "resiliency", "order_flow"],
        "runtime_keys": ["instability", "entropy"],
        "min_pack_hits": 2,
    },
    {
        "domain": "cross_regime_semantic_shift",
        "keywords": ["regime", "transition", "cross_regime"],
        "runtime_keys": ["regime"],
        "min_pack_hits": 2,
    },
    {
        "domain": "behavioral_progression",
        "keywords": ["sequence", "state_flow", "progression", "phase"],
        "runtime_keys": ["sequence_memory"],
        "min_pack_hits": 3,
    },
    {
        "domain": "negative_outcome_memory",
        "keywords": ["failure_mode", "negative_outcome", "catastrophic", "pathology"],
        "runtime_keys": ["failure"],
        "min_pack_hits": 2,
    },
    {
        "domain": "execution_pathology",
        "keywords": ["execution_pathology", "urgency_dilemma", "market_impact"],
        "runtime_keys": ["execution_guard", "spread_spike", "slippage_spike"],
        "min_pack_hits": 2,
    },
    {
        "domain": "adaptive_adversarial_behavior",
        "keywords": ["adversarial", "informed_trader", "pick_off", "adaptive"],
        "runtime_keys": ["edge_survival", "synthetic_similarity"],
        "min_pack_hits": 1,
    },
    {
        "domain": "uncertainty_propagation",
        "keywords": ["uncertainty", "noise_trader", "confidence_decay", "probabilistic"],
        "runtime_keys": ["semantic_confidence", "uncertainty"],
        "min_pack_hits": 2,
    },
    {
        "domain": "crowd_positioning_behavior",
        "keywords": ["crowd", "positioning", "herding", "sentiment"],
        "runtime_keys": ["ecology", "crowd"],
        "min_pack_hits": 1,
    },
    {
        "domain": "volatility_liquidity_interaction",
        "keywords": ["volatility_expansion", "liquidity_thinning", "spread_widening"],
        "runtime_keys": ["instability", "spread"],
        "min_pack_hits": 2,
    },
    {
        "domain": "semantic_compression",
        "keywords": ["compression", "governance_context", "cognitive_risk_compression"],
        "runtime_keys": ["governance_context"],
        "min_pack_hits": 1,
    },
    {
        "domain": "memory_pruning",
        "keywords": ["pruning", "decay", "forget"],
        "runtime_keys": ["confidence_decay"],
        "min_pack_hits": 1,
    },
    {
        "domain": "cognitive_collapse_patterns",
        "keywords": ["collapse", "overload", "cognitive", "freeze"],
        "runtime_keys": ["abstention", "runtime_health"],
        "min_pack_hits": 1,
    },
]


def _pack_text_blob(store: SemanticMemoryStore) -> str:
    parts: list[str] = []
    for e in store.entries:
        parts.append(e.source.lower())
        parts.append(str(e.payload).lower())
    return " ".join(parts)


def _count_keyword_hits(blob: str, keywords: list[str]) -> int:
    return sum(1 for k in keywords if k in blob)


def _runtime_hits(runtime_flags: dict[str, bool], keys: list[str]) -> int:
    return sum(1 for k in keys if runtime_flags.get(k))


def run_sufficiency_audit(
    store: SemanticMemoryStore,
    *,
    runtime_flags: dict[str, bool] | None = None,
    relation_count: int = 0,
    contradiction_template_count: int = 0,
    sequence_count: int = 0,
) -> Brain2AuditReport:
    flags = runtime_flags or {}
    blob = _pack_text_blob(store)
    domain_gaps: list[DomainGap] = []

    for spec in _DOMAIN_SPECS:
        pack_hits = _count_keyword_hits(blob, spec["keywords"])
        rt_hits = _runtime_hits(flags, spec["runtime_keys"])
        min_hits = int(spec["min_pack_hits"])
        pack_score = min(1.0, pack_hits / max(1, min_hits))
        rt_score = min(1.0, rt_hits / max(1, len(spec["runtime_keys"])))
        coverage = pack_score * 0.55 + rt_score * 0.45

        if coverage >= 0.72:
            status = "covered"
        elif coverage >= 0.38:
            status = "partial"
        else:
            status = "weak"

        domain_gaps.append(DomainGap(
            domain=spec["domain"],
            coverage_score=round(coverage, 4),
            status=status,
            measurable_gap=(
                f"pack_keyword_hits={pack_hits}/{min_hits} "
                f"runtime_signal_hits={rt_hits}/{len(spec['runtime_keys'])}"
            ),
            operational_gap=(
                f"missing operational hooks for {spec['domain']} "
                f"when pack_hits<{min_hits} or runtime unbound"
            ) if status != "covered" else "operational hooks present at partial level",
            semantic_gap=(
                f"semantic relations for {spec['domain']} not grounded in measurable proxies"
            ) if pack_score < 0.5 else "partial semantic grounding via pack keywords",
            runtime_gap=(
                f"runtime does not emit/consume {spec['runtime_keys']} for {spec['domain']}"
            ) if rt_score < 0.34 else "runtime signals partially wired",
        ))

    weak = [d.domain for d in domain_gaps if d.status == "weak"]
    partial = [d.domain for d in domain_gaps if d.status == "partial"]
    overall = sum(d.coverage_score for d in domain_gaps) / max(1, len(domain_gaps))

    blind_spots: list[str] = []
    if not flags.get("execution_guard_wired"):
        blind_spots.append("execution guards computed after Brain-2 cognition — pathology arrives late")
    if not flags.get("replay_mismatch_wired"):
        blind_spots.append("replay signature mismatch not fed into contradiction engine pre-governance")
    if sequence_count < 6:
        blind_spots.append(f"sequence memory depth={sequence_count} — behavioral progression shallow")
    if contradiction_template_count < 8:
        blind_spots.append(
            f"contradiction templates={contradiction_template_count} — accumulation patterns under-modeled"
        )
    if relation_count < 20:
        blind_spots.append(f"behavior graph relations={relation_count} — semantic propagation narrow")
    if store.loaded_files > 0 and len(store.entries) / max(1, store.loaded_files) < 1.2:
        blind_spots.append("pack entries are stub-density — high file count, low semantic payload per file")

    weak_semantic = weak + [d for d in partial if d not in weak][:6]

    overfit_risks = [
        "OHLC range proxies used for spread/slippage — not exchange-level microstructure",
        "edge_strength × structure_confidence trap heuristic may overfit ranging crypto regimes",
    ]
    if flags.get("synthetic_similarity_high"):
        overfit_risks.append("synthetic_similarity elevated — narrative_drift relation may misfire on real flow")

    hallucination_risks = [
        "semantic interpretations lack order-book verification — meaning can outrun evidence",
        "pack emotion_mapping fields are metaphorical — must not be treated as ground truth",
    ]
    if overall < 0.5:
        hallucination_risks.append(
            "low overall coverage — graph propagation can invent implied behaviors without pack support"
        )

    replay_live_gaps = [
        "prior snapshot stores replay_signature only — no fill-quality or spread state in replay chain",
        "replay_supported=bool(prior) does not measure live/replay divergence magnitude",
    ]
    if not flags.get("replay_validation_wired"):
        replay_live_gaps.append("validate_replay output not consumed by Brain-2 confidence decay")

    structural_risks = [
        "liquidity_thinning inferred from market_state label — not from Amihud/Kyle-style impact metrics",
        "continuation_probability mixes structure_confidence and environment_quality without adverse-selection term",
    ]

    sufficient = (
        overall >= 0.82
        and len(weak) <= 1
        and flags.get("execution_guard_wired", False)
        and not flags.get("synthetic_similarity_high", False)
    )

    return Brain2AuditReport(
        sufficient_for_behavioral_semantics=sufficient,
        overall_coverage=overall,
        domain_gaps=sorted(domain_gaps, key=lambda d: d.coverage_score),
        blind_spots=blind_spots,
        weak_semantic_areas=weak_semantic,
        overfit_risks=overfit_risks,
        hallucination_risks=hallucination_risks,
        replay_live_gaps=replay_live_gaps,
        structural_misunderstanding_risks=structural_risks,
        recommended_ingest_domains=weak[:8],
    )
