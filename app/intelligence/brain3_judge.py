"""
Brain 3 — GPT Judge (OPENAI_API_KEY_JUDGE)
Explains constitutional governance verdict only. Cannot override governance engine.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from typing import Any

from loguru import logger
from openai import OpenAI

from app.intelligence import brain_stack
from app.governance.runtime_constitution.governance_engine import GovernanceDecision
from app.intelligence.brain2.models import Brain2CognitionState
from app.intelligence.brain2_analyst import Brain2AnalystReport
from app.intelligence.context.context_state import ContextState
from app.intelligence.market_runtime.structure.market_structure import MarketStructureState

@dataclass
class Brain3JudgeReport:
    symbol: str
    verdict_echo: str
    judge_summary: str
    participation_stance: str
    model: str = brain_stack.BRAIN3_MODEL
    active: bool = False
    aligned_with_governance: bool = True
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_brain3_judge(
    symbol: str,
    context: ContextState,
    market: MarketStructureState,
    brain2: Brain2CognitionState,
    governance: GovernanceDecision,
    analyst: Brain2AnalystReport | None = None,
) -> Brain3JudgeReport:
    api_key = brain_stack.brain3_api_key()
    if not brain_stack.brain3_active():
        return Brain3JudgeReport(
            symbol=symbol,
            verdict_echo=governance.verdict.value,
            judge_summary="Brain 3 inactive — set OPENAI_API_KEY_JUDGE for judge layer.",
            participation_stance="governance_only",
            active=False,
            error="no_key_or_disabled",
        )

    gov_verdict = governance.verdict.value
    gov_approved = governance.approved
    payload = {
        "symbol": symbol,
        "governance_verdict": gov_verdict,
        "governance_approved": gov_approved,
        "governance_reason": governance.reason,
        "risk_mode": governance.risk_mode,
        "market_tradable": market.tradable,
        "structure_confidence": market.structure_confidence,
        "brain2_governance_confidence": brain2.governance_confidence,
        "brain2_abstention_tendency": brain2.abstention_tendency,
        "context_event_risk": context.event_risk,
        "analyst_summary": (analyst.analyst_summary if analyst else "")[:500],
    }

    system = (
        "You are AMRO Brain 3 Judge. Explain the EXISTING governance verdict — do not change it. "
        f"Required verdict_echo exactly: {gov_verdict}. "
        f"Approved flag is {gov_approved}. "
        "Output JSON: verdict_echo, judge_summary (Thai-friendly short English), "
        "participation_stance (blocked|limited|permitted|abstain). "
        "FORBIDDEN: contradicting verdict_echo, BUY/SELL orders, guaranteed outcomes."
    )
    user = f"Explain this governance state to the operator:\n{json.dumps(payload, default=str)[:10000]}"

    try:
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=brain_stack.BRAIN3_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.15,
            max_tokens=450,
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content.strip())
        echo = str(data.get("verdict_echo", gov_verdict)).upper()
        aligned = echo == gov_verdict.upper()
        if not aligned:
            logger.warning(f"[Brain 3 Judge] verdict mismatch {echo} != {gov_verdict}; forcing echo")
            echo = gov_verdict.upper()
        report = Brain3JudgeReport(
            symbol=symbol,
            verdict_echo=echo,
            judge_summary=str(data.get("judge_summary", ""))[:600],
            participation_stance=str(data.get("participation_stance", "abstain"))[:80],
            active=True,
            aligned_with_governance=aligned,
        )
        logger.info(f"[Brain 3 Judge] {symbol} echo={report.verdict_echo}")
        return report
    except Exception as e:
        logger.error(f"[Brain 3 Judge] {symbol}: {e}")
        return Brain3JudgeReport(
            symbol=symbol,
            verdict_echo=gov_verdict,
            judge_summary=governance.reason[:500] or "Governance verdict only (judge LLM unavailable).",
            participation_stance="blocked" if not gov_approved else "limited",
            active=False,
            error=str(e),
        )
