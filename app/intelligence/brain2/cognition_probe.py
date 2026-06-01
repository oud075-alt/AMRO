"""
Brain-2 cognition probe — Brain-2 answers from its own state only.

NOT for Cursor/LLM to answer market questions.
Run pipeline → interrogate Brain2CognitionState → return probabilistic answers.
AMRO reads the market as a behavioral probability field, not a prediction oracle.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from app.execution.pipeline import run_execution_pipeline
from app.intelligence.brain2.models import Brain2CognitionState


# Standard cognition test battery — memory-first, survival-risk, non-predictive.
# These questions are for avoiding wrong-timing participation, not for finding entries.
DEFAULT_QUESTIONS: list[str] = [
    "สมองที่2ยึด thinking framework อะไร",
    "market state ตอนนี้คืออะไรในเชิง behavioral probability",
    "environment stable แค่ไหน",
    "behavior ปัจจุบันใกล้เคียง memory pattern ใด",
    "contradiction สะสม support หรือ conflict interpretation",
    "replay/live divergence support หรือขัดแย้งความหมาย",
    "failure memory เตือนอะไรที่ conflict กับ runtime",
    "execution risk บอกว่าควรลด/หลีกเลี่ยง participation ไหม",
    "regime ปัจจุบัน align กับ semantic memory ไหม",
    "liquidity behavior trustworthy แค่ไหน",
    "volatility orderly หรือ chaotic",
    "signal reliability degraded หรือยัง",
    "memory support เพียงพอสำหรับ elevate confidence ไหม",
    "ควร distrust interpretation ระดับไหน",
    "uncertainty level เท่าไร",
    "condition นี้ historically survivable ไหม",
    "อารมณ์ตลาดตอนนี้เป็นยังไง มีความโลภ ตื่นตระหนก หรือความก้าวร้าวมากแค่ไหน",
]


@dataclass
class Brain2ProbeAnswer:
    question: str
    answer: str
    confidence: float
    memory_support: float
    evidence: list[str]
    uncertainty: str
    abstention: bool
    source: str = "brain2_cognition_state"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["confidence"] = round(float(d["confidence"]), 4)
        d["memory_support"] = round(float(d["memory_support"]), 4)
        return d


def _state_from_dict(d: dict[str, Any]) -> dict[str, Any]:
    return d


def answer_question(state: dict[str, Any], question: str) -> Brain2ProbeAnswer:
    """Map question → answer strictly from Brain-2 cognition output."""
    q = question.lower()
    mf = state.get("memory_first_policy") or {}
    retrieval = mf.get("retrieval") or {}
    interps = state.get("interpretations") or []
    contra_p = max(
        float(state.get("contradiction_pressure") or 0),
        float(state.get("accumulated_contradiction_pressure") or 0),
    )
    gov_conf = float(state.get("governance_confidence") or 0)
    abstention = float(state.get("abstention_tendency") or mf.get("abstention_tendency") or 0)
    replay = state.get("replay_divergence") or {}
    mem_support = float(retrieval.get("global_support") or mf.get("avg_memory_support") or 0)
    evidence: list[str] = []
    abstain_flag = abstention >= 0.35 or mem_support < 0.25

    if "thinking framework" in q or "framework" in q or "แนวทาง" in q:
        fw = state.get("thinking_framework") or {}
        ans = (
            f"framework={fw.get('framework_id', 'unknown')}; "
            f"market_model={fw.get('market_model', 'behavioral_probabilistic_runtime_environment')}; "
            f"objective={', '.join(fw.get('final_objective') or [])}; "
            "not_signal_generator_not_prediction_oracle"
        )
        evidence = [fw.get("source", ""), fw.get("core_principle", "")]
        return Brain2ProbeAnswer(question, ans, 1.0, mem_support, [e for e in evidence if e], fw.get("governance_note", ""), False)

    if "market state" in q or "behavioral probability" in q:
        gov = state.get("governance_context") or {}
        emo = state.get("market_emotion") or {}
        risk = state.get("cognition_risk") or {}
        ans = (
            f"market_state={gov.get('market_state', state.get('regime', 'unknown'))}; "
            f"primary_emotion={emo.get('primary_emotion', 'unknown')} "
            f"p={float(emo.get('primary_probability') or 0):.2f}; "
            f"period_risk={emo.get('period_risk_level', 'unknown')} "
            f"({float(emo.get('period_risk_score') or 0):.2f}); "
            f"confidence={gov_conf:.2f}; uncertainty={abstention:.2f}; "
            f"instability={risk.get('instability_level', 'unknown')}"
        )
        return Brain2ProbeAnswer(question, ans, gov_conf, mem_support, list(emo.get("evidence") or [])[:5], state.get("uncertainty_note", ""), abstain_flag)

    if "environment stable" in q or "environment stability" in q:
        risk = state.get("cognition_risk") or {}
        gov = state.get("governance_context") or {}
        stable = (
            str(risk.get("instability_level") or "").lower() not in ("elevated", "critical")
            and abstention < 0.35
            and gov_conf >= 0.12
        )
        ans = (
            f"environment_stable_probability={max(0.0, min(1.0, 1.0 - abstention)):.2f}; "
            f"instability_level={risk.get('instability_level', 'unknown')}; "
            f"liquidity_state={gov.get('liquidity_state', 'unknown')}; "
            f"{'stable enough to monitor' if stable else 'unstable/degraded — survival filter active'}"
        )
        return Brain2ProbeAnswer(question, ans, gov_conf, mem_support, [str(risk.get("instability_level", ""))], state.get("uncertainty_note", ""), not stable)

    if "memory pattern" in q or "คล้าย" in q:
        if not interps:
            ans = "ไม่พบ interpretation ที่ memory validate แล้ว — ไม่สรุป behavior"
            conf = 0.05
        else:
            top = interps[0]
            ans = top.get("meaning", "—")
            conf = float(top.get("confidence") or 0)
            mem_support = float(top.get("memory_support") or mem_support)
            evidence = list(top.get("memory_sources") or []) + list(top.get("evidence") or [])[:3]
        return Brain2ProbeAnswer(question, ans, conf, mem_support, evidence, state.get("uncertainty_note", ""), abstain_flag)

    if "contradiction" in q:
        escalation = mf.get("blocked_unsupported", 0)
        ans = (
            f"contradiction_pressure={contra_p:.2f}; "
            f"accumulated={float(state.get('accumulated_contradiction_pressure') or 0):.2f}; "
            f"{'conflict' if contra_p >= 0.35 else 'partial' if contra_p >= 0.15 else 'low conflict'}"
        )
        contras = state.get("contradictions") or []
        if contras:
            evidence = [c.get("contradiction_id", "") for c in contras[:3]]
        return Brain2ProbeAnswer(question, ans, max(0.05, 1.0 - contra_p), mem_support, evidence, state.get("uncertainty_note", ""), contra_p >= 0.45)

    if "replay" in q or "divergence" in q:
        cum = float(replay.get("cumulative_divergence") or 0)
        distrust = replay.get("distrust_level", "unknown")
        rel = float(replay.get("replay_reliability") or 0.5)
        ans = f"replay_reliability={rel:.2f}; cumulative_divergence={cum:.2f}; distrust={distrust}; {'ขัดแย้ง' if cum >= 0.28 else 'support บางส่วน' if cum < 0.12 else 'neutral'}"
        evidence = [f"fill_delta={replay.get('fill_delta')}", f"spread_delta={replay.get('spread_delta')}"]
        return Brain2ProbeAnswer(question, ans, rel, mem_support, evidence, state.get("uncertainty_note", ""), cum >= 0.35)

    if "failure" in q:
        overrides = int(mf.get("failure_overrides") or 0)
        hits = state.get("memory_hits") or []
        failure_hits = [h for h in hits if "NEG_" in str(h) or "failure" in str(h).lower()]
        conflict_interps = [i for i in interps if i.get("contradiction_status") == "failure_override"]
        if overrides > 0 or conflict_interps:
            ans = f"failure memory override active (count={overrides}); survival bias สูงกว่า runtime lean"
            conf = 0.08
        elif any(i.get("contradiction_status") == "failure_monitor" for i in interps):
            ans = f"failure memory monitor (calm structure); records={', '.join(failure_hits[:2]) or 'none'}; ไม่ override"
            conf = 0.22
        elif failure_hits:
            ans = f"failure memory records ที่ match: {', '.join(failure_hits[:3])}; ยังไม่ override แต่ monitor"
            conf = 0.25
        else:
            ans = "ไม่พบ failure memory conflict โดยตรงกับ runtime ปัจจุบัน"
            conf = 0.35
        return Brain2ProbeAnswer(question, ans, conf, mem_support, failure_hits, state.get("uncertainty_note", ""), overrides > 0)

    if "execution" in q or "participation" in q:
        exec_sig = state.get("execution_signals") or {}
        ok = exec_sig.get("exec_guards_ok", True)
        gov = state.get("governance_context") or {}
        impl = gov.get("governance_implication", "—")
        survival_read = (
            "ควรหลีกเลี่ยง participation"
            if not ok
            else "ควรลด/รอ ไม่เร่งเข้า"
            if "reduce" in str(impl) or "standby" in str(impl)
            else "monitor only — ไม่ใช่ entry signal"
        )
        ans = f"exec_guards_ok={ok}; implication={impl}; survival_read={survival_read}"
        evidence = [exec_sig.get("slip_reason", ""), exec_sig.get("spread_reason", "")]
        return Brain2ProbeAnswer(question, ans, gov_conf, mem_support, [e for e in evidence if e], state.get("uncertainty_note", ""), not ok)

    if "regime" in q or "align" in q:
        regime = state.get("regime", "—")
        prior = retrieval.get("regime_prior", "")
        aligned = [i for i in interps if i.get("regime_alignment") == "aligned"]
        mis = [i for i in interps if i.get("regime_alignment") == "misaligned"]
        ans = f"regime={regime}; prior={prior or 'none'}; aligned_interp={len(aligned)}; misaligned={len(mis)}"
        return Brain2ProbeAnswer(question, ans, gov_conf, mem_support, [regime, prior], state.get("uncertainty_note", ""), len(mis) > len(aligned))

    if "liquidity" in q and ("trustworthy" in q or "trust" in q):
        micro = state.get("microstructure") or {}
        gov = state.get("governance_context") or {}
        impact = float(micro.get("impact_stress") or 0)
        spread = float(micro.get("spread_proxy") or 0)
        trust = max(0.0, min(1.0, 1.0 - max(impact, spread, abstention * 0.75)))
        ans = (
            f"liquidity_trust_probability={trust:.2f}; "
            f"liquidity_state={gov.get('liquidity_state', 'unknown')}; "
            f"impact_stress={impact:.2f}; spread_proxy={spread:.2f}; "
            f"{'trust degraded' if trust < 0.55 else 'trust partial, still probabilistic'}"
        )
        return Brain2ProbeAnswer(question, ans, gov_conf, mem_support, [f"impact={impact:.2f}", f"spread={spread:.2f}"], state.get("uncertainty_note", ""), trust < 0.55)

    if "volatility" in q or "chaotic" in q or "orderly" in q:
        risk = state.get("cognition_risk") or {}
        micro = state.get("microstructure") or {}
        instability = str(risk.get("instability_level") or "unknown")
        accel = float(micro.get("instability_acceleration") or 0)
        chaotic = instability in ("elevated", "critical") or accel > 0.35 or abstention >= 0.35
        ans = (
            f"volatility_state={'chaotic/degraded' if chaotic else 'orderly-to-watch'}; "
            f"instability_level={instability}; instability_acceleration={accel:.2f}; "
            f"abstention_tendency={abstention:.2f}"
        )
        return Brain2ProbeAnswer(question, ans, gov_conf, mem_support, [instability, f"accel={accel:.2f}"], state.get("uncertainty_note", ""), chaotic)

    if "signal reliability" in q or "degraded" in q:
        risk = state.get("cognition_risk") or {}
        degraded = gov_conf < 0.18 or contra_p >= 0.25 or abstention >= 0.35 or mem_support < 0.35
        ans = (
            f"signal_reliability={'degraded' if degraded else 'partial'}; "
            f"confidence={gov_conf:.2f}; memory_support={mem_support:.2f}; "
            f"contradiction={contra_p:.2f}; uncertainty={abstention:.2f}"
        )
        return Brain2ProbeAnswer(question, ans, gov_conf, mem_support, [f"semantic_confidence={risk.get('semantic_confidence')}"], state.get("uncertainty_note", ""), degraded)

    if "memory support" in q or "elevate" in q or "เพียงพอ" in q:
        sufficient = (
            mem_support >= 0.45
            and abstention < 0.25
            and gov_conf >= 0.12
        )
        ans = f"global_memory_support={mem_support:.2f}; abstention_tendency={abstention:.2f}; governance_confidence={gov_conf:.2f}; {'ไม่เพียงพอ — ห้าม elevate' if not sufficient else 'partial support — elevate จำกัด'}"
        return Brain2ProbeAnswer(question, ans, gov_conf, mem_support, state.get("memory_hits") or [], state.get("uncertainty_note", ""), not sufficient)

    if "distrust" in q:
        risk = state.get("cognition_risk") or {}
        ans = (
            f"semantic_confidence={risk.get('semantic_confidence')}; "
            f"replay_distrust={risk.get('replay_live_distrust')}; "
            f"execution_fragility={risk.get('execution_fragility')}; "
            f"abstention_tendency={abstention:.2f}"
        )
        return Brain2ProbeAnswer(question, ans, gov_conf, mem_support, [], state.get("uncertainty_note", ""), abstention >= 0.35)

    if "uncertainty" in q:
        ans = (
            f"uncertainty_level={abstention:.2f}; "
            f"confidence={gov_conf:.2f}; memory_support={mem_support:.2f}; "
            f"contradiction={contra_p:.2f}; "
            f"{'high uncertainty — reduce/avoid participation' if abstention >= 0.35 or gov_conf < 0.12 else 'moderate uncertainty — monitor only'}"
        )
        return Brain2ProbeAnswer(question, ans, gov_conf, mem_support, [], state.get("uncertainty_note", ""), abstention >= 0.35 or gov_conf < 0.12)

    if "historically survivable" in q or "survivable" in q:
        mf = state.get("memory_first_policy") or {}
        overrides = int(mf.get("failure_overrides") or 0)
        survivable_p = max(0.0, min(1.0, mem_support * 0.55 + (1.0 - abstention) * 0.25 + gov_conf * 0.2 - min(0.35, overrides * 0.12)))
        ans = (
            f"historically_survivable_probability={survivable_p:.2f}; "
            f"failure_overrides={overrides}; memory_support={mem_support:.2f}; "
            f"uncertainty={abstention:.2f}; "
            f"{'not survivable enough — filter participation' if survivable_p < 0.45 else 'survivable only with governance filter'}"
        )
        return Brain2ProbeAnswer(question, ans, gov_conf, mem_support, state.get("memory_hits") or [], state.get("uncertainty_note", ""), survivable_p < 0.45)

    if "อารมณ์" in q or "emotion" in q or "โลภ" in q or "ตื่นตระหนก" in q or "โกรธ" in q or "ก้าวร้าว" in q:
        emo = state.get("market_emotion") or {}
        if not emo:
            return Brain2ProbeAnswer(
                question,
                "ไม่มี emotion assessment ใน cognition state — ไม่สรุป",
                0.05,
                mem_support,
                [],
                state.get("uncertainty_note", ""),
                True,
            )
        ans = emo.get("mood_summary_th") or "—"
        detail = (
            f" fear={emo.get('fear', 0):.2f} greed={emo.get('greed', 0):.2f} "
            f"panic={emo.get('panic', 0):.2f} aggression={emo.get('aggression', 0):.2f} "
            f"hesitation={emo.get('hesitation', 0):.2f}; "
            f"period_risk={emo.get('period_risk_level')} ({emo.get('period_risk_score', 0):.2f})"
        )
        ans = f"{ans};{detail}"
        conf = max(0.05, min(gov_conf, float(emo.get("primary_probability") or 0) * 0.85))
        abst = abstention >= 0.35 or float(emo.get("primary_probability") or 0) < 0.28
        return Brain2ProbeAnswer(
            question,
            ans,
            conf,
            mem_support,
            list(emo.get("evidence") or [])[:5],
            emo.get("uncertainty") or state.get("uncertainty_note", ""),
            abst,
        )

    return Brain2ProbeAnswer(
        question,
        "คำถามไม่อยู่ใน cognition test battery — Brain-2 ไม่ตอบนอกขอบเขต memory-first",
        0.0,
        mem_support,
        [],
        state.get("uncertainty_note", ""),
        True,
    )


def run_brain2_probe(
    symbol: str = "BTC/USDT",
    questions: list[str] | None = None,
    *,
    run_context_llm: bool = False,
) -> dict[str, Any]:
    """Run pipeline then let Brain-2 answer each question from its own state."""
    result = run_execution_pipeline(symbol, run_context_llm=run_context_llm, log_decision=False)
    if not result:
        return {"error": "pipeline_no_data", "symbol": symbol}

    state = result.get("brain2_cognition") or {}
    qs = questions or DEFAULT_QUESTIONS
    answers = [answer_question(state, q).to_dict() for q in qs]

    return {
        "symbol": symbol,
        "policy": (state.get("memory_first_policy") or {}).get("policy"),
        "brain2_answers": answers,
        "cognition_risk": state.get("cognition_risk"),
        "thinking_framework": state.get("thinking_framework"),
        "note": "behavioral_probability_field_answers_generated_by_brain2_probe_probability_confidence_uncertainty_not_entry_signal",
    }


if __name__ == "__main__":
    import json
    import sys
    sym = sys.argv[1] if len(sys.argv) > 1 else "BTC/USDT"
    print(json.dumps(run_brain2_probe(sym), indent=2, ensure_ascii=False))
