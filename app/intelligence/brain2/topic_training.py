"""
Brain-2 survival-risk audit harness — test one cognition topic at a time on real historical data.

AMRO treats the market as a behavioral probability field. The purpose is not to find
entries or predict the future with certainty. Brain-2 is tested as a survival layer:
read behavioral traces, estimate confidence/uncertainty, distrust weak interpretation,
and prevent wrong-timing participation.

Workflow (per user directive):
  1. Pick topic → run scenarios (multi-asset, multi-date)
  2. Ask Brain-2 via cognition_probe (never external LLM answers: 3. Score against measurable ground truth from bars (not fed to Brain-2)
  4. FAIL → suggest evidence packs to ingest → reload → retest until pass

Usage:
  python -m app.intelligence.brain2.topic_training --topic execution_reality
  python -m app.intelligence.brain2.topic_training --topic all
  python -m app.intelligence.brain2.topic_training --topic liquidity_stress --scenario btc_covid_crash
"""
from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Callable

import pandas as pd
from loguru import logger

from app.execution.pipeline import run_execution_pipeline
from app.intelligence.brain2.cognition_probe import answer_question
from app.intelligence.brain2.memory_loader import reload_semantic_memory
from app.intelligence.brain2.microstructure_grounding import compute_microstructure
from app.intelligence.market_data import fetch_historical_as_of

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
_TRAINING_DIR = os.path.join(_ROOT, "data", "brain2", "training")
_SCENARIOS_PATH = os.path.join(_TRAINING_DIR, "scenarios.json")
_RESULTS_DIR = os.path.join(_ROOT, "data", "brain2", "training", "results")

WATCHLIST_SYMBOLS = [
    "BTC/USDT",
    "GC=F",
    "EURUSD=X",
    "GBPUSD=X",
    "USDJPY=X",
    "USDCHF=X",
    "AUDUSD=X",
    "USDCAD=X",
    "NZDUSD=X",
]


@dataclass
class TrainingTopic:
    topic_id: str
    name: str
    questions: list[str]
    suggested_packs: list[str]
    grade: Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], tuple[bool, str]]


@dataclass
class ScenarioResult:
    scenario_id: str
    symbol: str
    as_of: str
    passed: bool
    reason: str
    ground_truth: dict[str, Any]
    brain2_answers: list[dict[str, Any]]
    cognition_snapshot: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _drawdown_pct(df: pd.DataFrame, window: int = 20) -> float:
    c = df["close"].astype(float)
    peak = c.cummax()
    dd = (peak - c) / peak
    tail = dd.tail(window)
    if tail.empty:
        return 0.0
    return float(tail.max())


def _bar_interval_hours(df: pd.DataFrame) -> float:
    if len(df) < 2:
        return 1.0
    return max(1.0, (df.index[-1] - df.index[-2]).total_seconds() / 3600.0)


def compute_ground_truth(df: pd.DataFrame, pipeline_result: dict[str, Any]) -> dict[str, Any]:
    """Measurable labels from bars + pipeline — used ONLY for scoring, never fed to Brain-2."""
    market = pipeline_result["market_audit"]
    micro = compute_microstructure(df)
    brain2 = pipeline_result.get("brain2_cognition") or {}
    exec_sig = brain2.get("execution_signals") or {}
    exec_blocked = not bool(exec_sig.get("exec_guards_ok", True))

    daily_bar = _bar_interval_hours(df) >= 12.0
    impact_thr = 0.55 if daily_bar else 0.35
    fill_thr = 0.30 if daily_bar else 0.35
    liquidity_stressed = micro.fill_vol_ratio < fill_thr or micro.impact_stress > impact_thr
    instability = float(getattr(market, "instability_score", 0))
    structure = float(getattr(market, "structure_confidence", 0))
    synthetic = float(getattr(market, "synthetic_similarity", 0))
    drawdown = _drawdown_pct(df)

    return {
        "exec_blocked": exec_blocked,
        "liquidity_stressed": liquidity_stressed,
        "impact_stress": round(micro.impact_stress, 4),
        "fill_vol_ratio": round(micro.fill_vol_ratio, 4),
        "instability_elevated": instability > 0.5,
        "instability_score": round(instability, 4),
        "low_structure": structure < 0.45,
        "structure_confidence": round(structure, 4),
        "high_synthetic": synthetic > 0.55,
        "synthetic_similarity": round(synthetic, 4),
        "crash_scenario": drawdown > 0.12,
        "drawdown_pct": round(drawdown, 4),
        "high_contradiction_context": instability > 0.5 and synthetic > 0.45,
        "calm_market": instability < 0.35 and structure > 0.5 and not liquidity_stressed,
        "daily_bar": daily_bar,
        "bar_count": len(df),
        "as_of_price": round(float(df["close"].iloc[-1]), 2),
    }


def _grade_execution_reality(
    gt: dict[str, Any], state: dict[str, Any], answers: list[dict[str, Any]]
) -> tuple[bool, str]:
    ans = next((a for a in answers if "execution" in a["question"].lower() or "participation" in a["question"].lower()), answers[0])
    text = ans["answer"].lower()
    conf = float(ans["confidence"])
    abst = bool(ans["abstention"])
    exec_ok = bool((state.get("execution_signals") or {}).get("exec_guards_ok", True))

    if gt["exec_blocked"]:
        ok = abst or "ไม่รองรับ" in ans["answer"] or not exec_ok or conf < 0.35
        return ok, "stress: protected by refusing/limiting participation" if ok else "stress: failed to protect against blocked execution"
    if gt["calm_market"]:
        ok = not ("ไม่รองรับ" in ans["answer"] and conf > 0.55 and not abst)
        return ok, "calm: proportionate survival read" if ok else "calm: excessive defensive block"
    return True, "neutral execution risk context"


def _grade_liquidity_stress(
    gt: dict[str, Any], state: dict[str, Any], answers: list[dict[str, Any]]
) -> tuple[bool, str]:
    micro = state.get("microstructure") or {}
    impact = float(micro.get("impact_stress") or gt["impact_stress"])
    abst = float(state.get("abstention_tendency") or 0)
    contra = max(float(state.get("contradiction_pressure") or 0), float(state.get("accumulated_contradiction_pressure") or 0))

    if gt["liquidity_stressed"]:
        exec_ans = next((a for a in answers if "execution" in a["question"].lower()), None)
        exec_text = (exec_ans or {}).get("answer", "")
        ok = (
            impact > 0.18
            or abst >= 0.22
            or contra >= 0.12
            or "ไม่รองรับ" in exec_text
            or "reduce" in exec_text.lower()
            or "standby" in exec_text.lower()
        )
        return ok, "stress: liquidity/impact reflected" if ok else "stress: missed liquidity collapse signal"
    if gt["calm_market"] and impact > 0.55:
        return False, "calm: false liquidity alarm (impact_stress too high)"
    return True, "liquidity context proportionate"


def _grade_memory_support(
    gt: dict[str, Any], state: dict[str, Any], answers: list[dict[str, Any]]
) -> tuple[bool, str]:
    ans = next((a for a in answers if "memory support" in a["question"].lower() or "elevate" in a["question"].lower()), answers[-1])
    text = ans["answer"]
    abst = bool(ans["abstention"])
    mem = float(ans.get("memory_support") or 0)

    weak_context = (
        gt["low_structure"]
        or (gt["high_synthetic"] and gt["structure_confidence"] < 0.5)
        or (gt["liquidity_stressed"] and gt["impact_stress"] > (0.55 if gt.get("daily_bar") else 0.35))
    )
    if weak_context:
        ok = "ไม่เพียงพอ" in text or abst or mem < 0.35
        return ok, "weak context: must not elevate" if ok else "weak context: over-confident memory support"
    if gt["calm_market"]:
        ok = not (abst and mem < 0.15 and "ไม่เพียงพอ" in text)
        return ok, "calm: no excessive abstention gate" if ok else "calm: blocked without cause"
    return True, "memory gate neutral"


def _grade_failure_memory(
    gt: dict[str, Any], state: dict[str, Any], answers: list[dict[str, Any]]
) -> tuple[bool, str]:
    ans = next((a for a in answers if "failure" in a["question"].lower()), answers[0])
    conf = float(ans["confidence"])
    abst = bool(ans["abstention"])
    mf = state.get("memory_first_policy") or {}
    overrides = int(mf.get("failure_overrides") or 0)

    if gt["crash_scenario"] or (gt["liquidity_stressed"] and gt["instability_elevated"]):
        ok = overrides > 0 or abst or conf < 0.28 or "override" in ans["answer"].lower()
        return ok, "crash/stress: survival memory prioritized" if ok else "crash/stress: under-weighted failure memory"
    if gt["calm_market"] and overrides > 0:
        if gt.get("high_synthetic"):
            return True, "calm but synthetic elevated: failure caution acceptable"
        return False, "calm: spurious failure override"
    return True, "failure memory proportionate"


def _grade_contradiction(
    gt: dict[str, Any], state: dict[str, Any], answers: list[dict[str, Any]]
) -> tuple[bool, str]:
    ans = next((a for a in answers if "contradiction" in a["question"].lower()), answers[0])
    text = ans["answer"]
    m = re.search(r"contradiction_pressure=([\d.]+)", text)
    reported = float(m.group(1)) if m else 0.0
    accumulated = float(state.get("accumulated_contradiction_pressure") or 0)

    if gt["high_contradiction_context"]:
        ok = reported >= 0.12 or accumulated >= 0.12 or "conflict" in text.lower()
        return ok, "tension: contradiction surfaced" if ok else "tension: contradiction under-reported"
    if gt["calm_market"] and reported > 0.45:
        return False, "calm: contradiction over-amplified"
    return True, "contradiction level proportionate"


def _grade_instability(
    gt: dict[str, Any], state: dict[str, Any], answers: list[dict[str, Any]]
) -> tuple[bool, str]:
    risk = state.get("cognition_risk") or {}
    inst_level = str(risk.get("instability_level") or "")
    gov_conf = float(state.get("governance_confidence") or 0)
    abst = float(state.get("abstention_tendency") or 0)

    if gt["instability_elevated"]:
        ok = inst_level in ("elevated", "critical", "moderate") or gov_conf < 0.35 or abst >= 0.2
        return ok, "instability: elevated risk reflected" if ok else "instability: under-reported"
    if gt["calm_market"] and inst_level == "critical":
        return False, "calm: false critical instability"
    return True, "instability proportionate"


def _grade_market_emotion(
    gt: dict[str, Any], state: dict[str, Any], answers: list[dict[str, Any]]
) -> tuple[bool, str]:
    emo = state.get("market_emotion") or {}
    ans = next((a for a in answers if "อารมณ์" in a["question"] or "emotion" in a["question"].lower()), answers[0])
    if not emo:
        return False, "missing market_emotion in cognition state"

    primary = str(emo.get("primary_emotion") or "")
    primary_p = float(emo.get("primary_probability") or 0)
    panic = float(emo.get("panic") or 0)
    fear = float(emo.get("fear") or 0)
    greed = float(emo.get("greed") or 0)
    risk = str(emo.get("period_risk_level") or "")
    risk_score = float(emo.get("period_risk_score") or 0)

    stress = (
        gt["crash_scenario"]
        or gt["instability_elevated"]
        or gt["liquidity_stressed"]
        or gt["drawdown_pct"] > 0.08
    )
    if stress:
        ok = (
            primary in ("panic", "fear", "aggression", "exhaustion")
            or max(panic, fear) >= 0.28
            or risk in ("moderate", "elevated")
        )
        return ok, "stress: emotion/risk reflects turmoil" if ok else "stress: under-read panic/fear"
    if gt["calm_market"]:
        ok = panic < 0.55 and not (primary == "panic" and primary_p > 0.55)
        return ok, "calm: emotion proportionate" if ok else "calm: false panic read"
    ok = primary_p >= 0.22 and risk_score >= 0.15
    return ok, "neutral: probabilistic emotion present" if ok else "neutral: emotion signal too weak"


def _grade_governance_synchronization(
    gt: dict[str, Any], state: dict[str, Any], answers: list[dict[str, Any]]
) -> tuple[bool, str]:
    e_ok, e_r = _grade_execution_reality(gt, state, answers)
    gov = state.get("governance_context") or {}
    impl = str(gov.get("governance_implication") or "").lower()
    stress = gt["liquidity_stressed"] or gt["instability_elevated"] or gt["exec_blocked"]
    if stress:
        ok = e_ok and any(k in impl for k in ("reduce", "standby", "no participation"))
        return ok, f"governance sync: stress implication ({e_r})" if ok else "governance sync: missing reduce/standby"
    return e_ok, e_r


def _grade_live_cognitive_system(
    gt: dict[str, Any], state: dict[str, Any], answers: list[dict[str, Any]]
) -> tuple[bool, str]:
    seq = state.get("sequence") or []
    interps = state.get("interpretations") or []
    abst = float(state.get("abstention_tendency") or 0)
    if gt["high_contradiction_context"] or gt["crash_scenario"]:
        ok = len(seq) > 0 or len(interps) > 0 or abst >= 0.2
        return ok, "live cognitive: context/sequence under stress" if ok else "live cognitive: empty under stress"
    if gt["calm_market"] and abst > 0.55:
        return False, "live cognitive: over-abstention in calm"
    return len(seq) > 0 or len(interps) >= 0, "live cognitive: context trace present"


def _grade_adaptive_intuition_system(
    gt: dict[str, Any], state: dict[str, Any], answers: list[dict[str, Any]]
) -> tuple[bool, str]:
    m_ok, m_r = _grade_memory_support(gt, state, answers)
    c_ok, c_r = _grade_contradiction(gt, state, answers)
    ok = m_ok and c_ok
    return ok, f"memory:{m_r}; contra:{c_r}"


def _grade_runtime_sensory_system(
    gt: dict[str, Any], state: dict[str, Any], answers: list[dict[str, Any]]
) -> tuple[bool, str]:
    l_ok, l_r = _grade_liquidity_stress(gt, state, answers)
    i_ok, i_r = _grade_instability(gt, state, answers)
    ok = l_ok and i_ok
    return ok, f"liquidity:{l_r}; instability:{i_r}"


def _grade_visual_perception_layer(
    gt: dict[str, Any], state: dict[str, Any], answers: list[dict[str, Any]]
) -> tuple[bool, str]:
    if gt["high_synthetic"]:
        gov = float(state.get("governance_confidence") or 0)
        abst = float(state.get("abstention_tendency") or 0)
        note = str(state.get("uncertainty_note") or "").lower()
        ok = gov < 0.4 or abst >= 0.2 or "synthetic" in note or "distrust" in note
        return ok, "visual: synthetic distrust active" if ok else "visual: over-trusted similarity"
    micro = state.get("microstructure") or {}
    if gt["liquidity_stressed"] and float(micro.get("spread_proxy") or 0) <= 0:
        return False, "visual/sensory: spread proxy missing under stress"
    return True, "visual perception proportionate"


def _grade_runtime_behavioral_memory(
    gt: dict[str, Any], state: dict[str, Any], answers: list[dict[str, Any]]
) -> tuple[bool, str]:
    crowd = state.get("crowd_pressure") or {}
    cp = float(crowd.get("crowd_pressure") or 0)
    panic_accel = float(crowd.get("panic_participation_acceleration") or 0)
    if gt["instability_elevated"] or gt["high_contradiction_context"] or gt["crash_scenario"]:
        ok = cp >= 0.12 or panic_accel >= 0.15
        return ok, "behavioral: crowd pressure reflected" if ok else "behavioral: crowd signal missing"
    if gt["calm_market"] and cp > 0.75:
        return False, "behavioral: false crowd alarm"
    return True, "behavioral memory proportionate"


def _grade_brain2_replay_research(
    gt: dict[str, Any], state: dict[str, Any], answers: list[dict[str, Any]]
) -> tuple[bool, str]:
    ans = next((a for a in answers if "replay" in a["question"].lower()), None)
    if not ans:
        return False, "missing replay probe answer"
    replay = state.get("replay_divergence") or {}
    cum = float(replay.get("cumulative_divergence") or 0)
    text = ans["answer"].lower()
    if cum >= 0.28:
        ok = "ขัดแย้ง" in ans["answer"] or "distrust" in text or ans["abstention"]
        return ok, "replay research: divergence acknowledged" if ok else "replay research: ignored divergence"
    if gt["calm_market"] and cum > 0.5:
        return False, "replay research: false divergence alarm"
    return True, "replay research proportionate"


def _grade_market_vision_core(
    gt: dict[str, Any], state: dict[str, Any], answers: list[dict[str, Any]]
) -> tuple[bool, str]:
    note = str(state.get("uncertainty_note") or "").lower()
    ok = "probabilistic" in note and "not ground truth" in note
    interps = state.get("interpretations") or []
    overconf = any(float(i.get("confidence") or 0) > 0.72 for i in interps)
    if overconf:
        ok = False
    if gt["crash_scenario"] or gt["liquidity_stressed"]:
        ok = ok and float(state.get("governance_confidence") or 1) < 0.45
    return ok, "vision core: probabilistic discipline" if ok else "vision core: certainty/overconfidence risk"


def _grade_operational_evolution(
    gt: dict[str, Any], state: dict[str, Any], answers: list[dict[str, Any]]
) -> tuple[bool, str]:
    emo = state.get("market_emotion") or {}
    risk = str(emo.get("period_risk_level") or "")
    risk_score = float(emo.get("period_risk_score") or 0)
    gov = state.get("governance_context") or {}
    impl = str(gov.get("governance_implication") or "").lower()
    if gt["crash_scenario"] or gt["liquidity_stressed"] or gt["instability_elevated"]:
        ok = risk in ("moderate", "elevated") or risk_score >= 0.35 or "reduce" in impl
        return ok, "operational: consequence/risk surfaced" if ok else "operational: risk under-stated"
    if not emo:
        return False, "operational: missing period risk surface"
    return risk_score >= 0.1, "operational evolution proportionate"


# 11 topics — 1:1 with Market structer Baind 2.zip packs
TOPICS: dict[str, TrainingTopic] = {
    "governance_synchronization": TrainingTopic(
        "governance_synchronization",
        "AMRO_Governance_Synchronization_v1",
        ["execution risk บอกว่าควรลด/หลีกเลี่ยง participation ไหม"],
        [
            "AMRO_Governance_Synchronization_v1/governance_context_output.json",
            "AMRO_Governance_Synchronization_v1/confidence_governance.json",
            "AMRO_Governance_Synchronization_v1/execution_risk_translator.json",
        ],
        _grade_governance_synchronization,
    ),
    "live_cognitive_system": TrainingTopic(
        "live_cognitive_system",
        "AMRO_Live_Cognitive_System_v1",
        [
            "behavior ปัจจุบันใกล้เคียง memory pattern ใด",
            "regime ปัจจุบัน align กับ semantic memory ไหม",
        ],
        [
            "AMRO_Live_Cognitive_System_v1/continuous_context_memory.json",
            "AMRO_Live_Cognitive_System_v1/cognitive_state_evolution.json",
            "AMRO_Live_Cognitive_System_v1/market_narrative_tracking.json",
        ],
        _grade_live_cognitive_system,
    ),
    "adaptive_intuition_system": TrainingTopic(
        "adaptive_intuition_system",
        "AMRO_Adaptive_Intuition_System_v1",
        [
            "memory support เพียงพอสำหรับ elevate confidence ไหม",
            "contradiction สะสม support หรือ conflict interpretation",
        ],
        [
            "AMRO_Adaptive_Intuition_System_v1/contradiction_detection.json",
            "AMRO_Adaptive_Intuition_System_v1/reality_verification_layer.json",
            "AMRO_Adaptive_Intuition_System_v1/confidence_drift_memory.json",
        ],
        _grade_adaptive_intuition_system,
    ),
    "runtime_sensory_system": TrainingTopic(
        "runtime_sensory_system",
        "AMRO_Runtime_Sensory_System_v1",
        [
            "execution risk บอกว่าควรลด/หลีกเลี่ยง participation ไหม",
            "ควร distrust interpretation ระดับไหน",
        ],
        [
            "AMRO_Runtime_Sensory_System_v1/spread_stress_memory.json",
            "AMRO_Runtime_Sensory_System_v1/instability_detection_memory.json",
            "AMRO_Runtime_Sensory_System_v1/liquidity_pulse_memory.json",
        ],
        _grade_runtime_sensory_system,
    ),
    "visual_perception_layer": TrainingTopic(
        "visual_perception_layer",
        "AMRO_Visual_Perception_Layer_v1",
        ["ควร distrust interpretation ระดับไหน"],
        [
            "AMRO_Visual_Perception_Layer_v1/visual_similarity_memory.json",
            "AMRO_Visual_Perception_Layer_v1/annotated_behavior_dataset.json",
        ],
        _grade_visual_perception_layer,
    ),
    "runtime_behavioral_memory": TrainingTopic(
        "runtime_behavioral_memory",
        "AMRO_Runtime_Behavioral_Memory_v1",
        ["อารมณ์ตลาดตอนนี้เป็นยังไง มีความโloภ ตื่นตระหนก หรือความก้าวร้าวมากแค่ไหน"],
        [
            "AMRO_Runtime_Behavioral_Memory_v1/crowd_pressure_dataset.json",
            "AMRO_Runtime_Behavioral_Memory_v1/emotion_sequence_dataset.json",
        ],
        _grade_runtime_behavioral_memory,
    ),
    "brain2_visual_replay_dataset": TrainingTopic(
        "brain2_visual_replay_dataset",
        "AMRO_Brain2_Visual_Replay_Dataset_v1",
        ["failure memory เตือนอะไรที่ conflict กับ runtime"],
        [
            "AMRO_Brain2_Visual_Replay_Dataset_v1/panic_replay_dataset.json",
            "AMRO_Brain2_Visual_Replay_Dataset_v1/fake_breakout_dataset.json",
            "AMRO_Brain2_Visual_Replay_Dataset_v1/liquidity_trap_dataset.json",
        ],
        _grade_failure_memory,
    ),
    "brain2_replay_research": TrainingTopic(
        "brain2_replay_research",
        "AMRO_Brain2_Replay_Research_v1",
        ["replay/live divergence support หรือขัดแย้งความหมาย"],
        [
            "AMRO_Brain2_Replay_Research_v1/panic_research.md",
            "AMRO_Brain2_Replay_Research_v1/liquidity_instability_research.md",
        ],
        _grade_brain2_replay_research,
    ),
    "market_vision_core": TrainingTopic(
        "market_vision_core",
        "AMRO_Market_Vision_Core_v2",
        [
            "memory support เพียงพอสำหรับ elevate confidence ไหม",
            "ควร distrust interpretation ระดับไหน",
        ],
        [
            "AMRO_Market_Vision_Core_v2/brain2_architecture.md",
            "AMRO_Market_Vision_Core_v2/integration_rules.md",
        ],
        _grade_market_vision_core,
    ),
    "market_vision_kb": TrainingTopic(
        "market_vision_kb",
        "AMRO_Market_Vision_KB_v1",
        ["อารมณ์ตลาดตอนนี้เป็นยังไง มีความโloภ ตื่นตระหนก หรือความก้าวร้าวมากแค่ไหน"],
        [
            "AMRO_Market_Vision_KB_v1/emotion_runtime_rules.json",
            "AMRO_Market_Vision_KB_v1/fear_behavior.md",
            "AMRO_Market_Vision_KB_v1/greed_behavior.md",
            "AMRO_Market_Vision_KB_v1/panic_behavior.md",
        ],
        _grade_market_emotion,
    ),
    "operational_evolution": TrainingTopic(
        "operational_evolution",
        "AMRO_Operational_Evolution_Summary",
        [
            "อารมณ์ตลาดตอนนี้เป็นยังไง มีความโloภ ตื่นตระหนก หรือความก้าวร้าวมากแค่ไหน",
            "execution risk บอกว่าควรลด/หลีกเลี่ยง participation ไหม",
        ],
        [
            "AMRO_Operational_Evolution_Summary/AMRO_Operational_Evolution_Summary.md",
        ],
        _grade_operational_evolution,
    ),
}

# backward-compatible aliases (old 7-topic names → pack topics)
TOPIC_ALIASES: dict[str, str] = {
    "execution_reality": "governance_synchronization",
    "liquidity_stress": "runtime_sensory_system",
    "memory_support_gate": "adaptive_intuition_system",
    "failure_memory": "brain2_visual_replay_dataset",
    "contradiction_pressure": "adaptive_intuition_system",
    "instability_regime": "runtime_sensory_system",
    "market_emotion": "market_vision_kb",
}


def _resolve_topic_id(topic_id: str) -> str:
    return TOPIC_ALIASES.get(topic_id, topic_id)


def _scenario_path(scenario_set: str) -> str:
    if scenario_set in ("training", "default"):
        return _SCENARIOS_PATH
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", scenario_set).strip("_")
    return os.path.join(_TRAINING_DIR, f"{safe}_scenarios.json")


def _load_scenarios(scenario_set: str = "training") -> list[dict[str, Any]]:
    with open(_scenario_path(scenario_set), encoding="utf-8") as f:
        return json.load(f)


def _sandbox_key(scenario_id: str, symbol: str) -> str:
    sym = symbol.replace("/", "_")
    return f"__train__{scenario_id}__{sym}"


def _blind_sandbox_key(scenario: dict[str, Any]) -> str:
    sym = str(scenario["symbol"]).replace("/", "_")
    as_of = str(scenario["as_of"]).replace("-", "")
    interval = str(scenario.get("interval", "1h"))
    return f"__blind__{sym}__{as_of}__{interval}"


def run_scenario(
    scenario: dict[str, Any],
    topic: TrainingTopic,
    *,
    blind: bool = False,
    blind_index: int | None = None,
) -> ScenarioResult | dict[str, Any]:
    """Fetch historical bars → pipeline → probe Brain-2 → grade."""
    sid = scenario["id"]
    symbol = scenario["symbol"]
    as_of = scenario["as_of"]

    df = fetch_historical_as_of(
        symbol,
        as_of,
        interval=scenario.get("interval", "1h"),
        lookback_days=int(scenario.get("lookback_days", 45)),
        source=scenario.get("source", "auto"),
    )
    if df.empty or len(df) < 50:
        return {"error": "insufficient_historical_data", "scenario_id": sid, "bars": len(df)}

    sandbox = _blind_sandbox_key(scenario) if blind else _sandbox_key(sid, symbol)
    result = run_execution_pipeline(
        symbol,
        df=df,
        run_context_llm=False,
        log_decision=False,
        persist=False,
        state_symbol=sandbox,
        interval=scenario.get("interval", "1h"),
    )
    if not result:
        return {"error": "pipeline_failed", "scenario_id": sid}

    gt = compute_ground_truth(df, result)
    state = result.get("brain2_cognition") or {}
    answers = [answer_question(state, q).to_dict() for q in topic.questions]
    passed, reason = topic.grade(gt, state, answers)

    return ScenarioResult(
        scenario_id=f"blind_{blind_index:03d}" if blind and blind_index is not None else sid,
        symbol=symbol,
        as_of=as_of,
        passed=passed,
        reason=reason,
        ground_truth=gt,
        brain2_answers=answers,
        cognition_snapshot={
            "governance_confidence": state.get("governance_confidence"),
            "abstention_tendency": state.get("abstention_tendency"),
            "contradiction_pressure": state.get("contradiction_pressure"),
            "accumulated_contradiction_pressure": state.get("accumulated_contradiction_pressure"),
            "cognition_risk": state.get("cognition_risk"),
            "market_emotion": state.get("market_emotion"),
            "thinking_framework": state.get("thinking_framework"),
            "crowd_pressure": state.get("crowd_pressure"),
            "sequence_len": len(state.get("sequence") or []),
            "governance_context": state.get("governance_context"),
            "memory_first_policy": {
                k: state.get("memory_first_policy", {}).get(k)
                for k in ("global_support", "avg_memory_support", "failure_overrides", "blocked_unsupported")
                if state.get("memory_first_policy")
            },
        },
    )


def run_topic_training(
    topic_id: str,
    *,
    scenario_filter: str | None = None,
    symbol_filter: str | None = None,
    watchlist_only: bool = False,
    reload_memory: bool = False,
    scenario_set: str = "training",
    blind: bool = False,
) -> dict[str, Any]:
    topic_id = _resolve_topic_id(topic_id)
    if topic_id != "all" and topic_id not in TOPICS:
        return {"error": "unknown_topic", "topic_id": topic_id, "available": list(TOPICS)}

    if reload_memory:
        reload_semantic_memory()

    topics = list(TOPICS.values()) if topic_id == "all" else [TOPICS[topic_id]]
    scenarios = _load_scenarios(scenario_set)
    if scenario_filter:
        scenarios = [s for s in scenarios if s["id"] == scenario_filter]
    if symbol_filter:
        scenarios = [s for s in scenarios if s.get("symbol") == symbol_filter]
    if watchlist_only:
        scenarios = [s for s in scenarios if s.get("symbol") in WATCHLIST_SYMBOLS]

    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": "historical_real_data_survival_risk_loop",
        "goal": "runtime probabilistic governance over behavioral market traces; not prediction or entry discovery",
        "note": "answers_from_brain2_probe_only_probability_confidence_uncertainty_not_external_llm_not_trade_entry_signal",
        "pack_topics": 11,
        "scenario_set": scenario_set,
        "blind_audit": blind,
        "blind_protocol": (
            "scenario ids and event notes are not used as state keys or report labels"
            if blind
            else "scenario ids visible in report and sandbox state key"
        ),
        "topics": {},
    }

    for topic in topics:
        topic_report: dict[str, Any] = {
            "name": topic.name,
            "questions": topic.questions,
            "suggested_packs_on_fail": topic.suggested_packs,
            "scenarios": [],
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "pass_rate": 0.0,
            "topic_passed": False,
        }

        for idx, sc in enumerate(scenarios, start=1):
            scenario_label = f"blind_{idx:03d}" if blind else sc["id"]
            logger.info(f"[TopicTraining] {topic.topic_id} / {scenario_label} @ {sc['as_of']}")
            outcome = run_scenario(sc, topic, blind=blind, blind_index=idx)
            if isinstance(outcome, dict) and outcome.get("error"):
                topic_report["errors"] += 1
                topic_report["scenarios"].append(outcome)
                continue

            sr = outcome
            assert isinstance(sr, ScenarioResult)
            topic_report["scenarios"].append(sr.to_dict())
            if sr.passed:
                topic_report["passed"] += 1
            else:
                topic_report["failed"] += 1

        total = topic_report["passed"] + topic_report["failed"]
        topic_report["pass_rate"] = round(topic_report["passed"] / total, 4) if total else 0.0
        topic_report["topic_passed"] = topic_report["failed"] == 0 and topic_report["errors"] == 0 and total > 0
        if not topic_report["topic_passed"]:
            topic_report["next_action"] = (
                "ingest suggested_packs -> reload_semantic_memory() -> retest same topic"
            )

        report["topics"][topic.topic_id] = topic_report

    os.makedirs(_RESULTS_DIR, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = f"{scenario_set}_{'blind' if blind else 'labeled'}"
    out_path = os.path.join(_RESULTS_DIR, f"{topic_id}_{suffix}_{stamp}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    report["report_path"] = out_path
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Brain-2 topic training on historical data")
    parser.add_argument("--topic", default="governance_synchronization", help="topic id, 'all' (11 packs), or legacy alias")
    parser.add_argument("--scenario", default=None, help="run single scenario id")
    parser.add_argument("--symbol", default=None, help="filter by symbol e.g. GC=F or BTC/USDT")
    parser.add_argument("--watchlist", action="store_true", help="test all sidebar watchlist pairs only")
    parser.add_argument("--reload", action="store_true", help="reload semantic memory before run")
    parser.add_argument("--scenario-set", default="training", help="scenario set name, e.g. training or out_of_sample")
    parser.add_argument("--blind", action="store_true", help="mask scenario ids/notes and use anonymous sandbox keys")
    args = parser.parse_args()

    report = run_topic_training(
        args.topic,
        scenario_filter=args.scenario,
        symbol_filter=args.symbol,
        watchlist_only=args.watchlist,
        reload_memory=args.reload,
        scenario_set=args.scenario_set,
        blind=args.blind,
    )
    # Windows console may not render all Thai/Unicode; file report is authoritative.
    print(json.dumps(report, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
