"""Persistent contradiction accumulation — aging, clustering, escalation."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from app.intelligence.brain2.models import ContradictionRecord


@dataclass
class ContradictionAccumulationState:
    bar_pressure: float
    accumulated_pressure: float
    escalation_level: str
    active_count: int
    cluster_count: int
    recurrence_rate: float
    aged_entries: int

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        for k in ("bar_pressure", "accumulated_pressure", "recurrence_rate"):
            d[k] = round(float(d[k]), 4)
        return d


def _cluster_key(contra_id: str) -> str:
    if contra_id.startswith("RUNTIME_"):
        parts = contra_id.split("_")
        return parts[2] if len(parts) > 2 else contra_id
    return contra_id.split("_")[0]


def update_contradiction_accumulation(
    persistent: dict[str, Any],
    *,
    bar_index: int,
    regime: str,
    records: list[ContradictionRecord],
    max_log: int = 120,
    decay_per_bar: float = 0.012,
) -> ContradictionAccumulationState:
    log: list[dict[str, Any]] = list(persistent.get("contradiction_log") or [])
    bar_pressure = 0.0
    if records:
        bar_pressure = min(1.0, sum(r.severity for r in records) / max(1, len(records)))

    for r in records:
        log.append({
            "bar": bar_index,
            "regime": regime,
            "id": r.contradiction_id,
            "cluster": _cluster_key(r.contradiction_id),
            "severity": round(r.severity, 4),
        })

    if len(log) > max_log:
        log = log[-max_log:]

    # Age: decay severity by bars elapsed
    accumulated = 0.0
    clusters: set[str] = set()
    active = 0
    for entry in log:
        age = max(0, bar_index - int(entry.get("bar", bar_index)))
        sev = float(entry.get("severity", 0)) * max(0.05, 1.0 - age * decay_per_bar)
        if sev >= 0.15:
            active += 1
            accumulated += sev
            clusters.add(str(entry.get("cluster", "")))

    accumulated = min(1.0, accumulated / max(1, active + 2))
    combined = min(1.0, bar_pressure * 0.45 + accumulated * 0.55)

    # Recurrence: same cluster appearing across regime boundaries
    recent = log[-20:]
    cluster_hits: dict[str, int] = {}
    regimes_seen: dict[str, set[str]] = {}
    for e in recent:
        c = str(e.get("cluster", ""))
        cluster_hits[c] = cluster_hits.get(c, 0) + 1
        regimes_seen.setdefault(c, set()).add(str(e.get("regime", "")))
    recurring = sum(1 for c, n in cluster_hits.items() if n >= 2 and len(regimes_seen.get(c, set())) >= 1)
    recurrence_rate = min(1.0, recurring / max(1, len(cluster_hits)))

    if combined >= 0.72 or (combined >= 0.55 and recurrence_rate >= 0.4):
        escalation = "critical"
    elif combined >= 0.48 or recurrence_rate >= 0.35:
        escalation = "elevated"
    elif combined >= 0.25:
        escalation = "watch"
    else:
        escalation = "normal"

    persistent["contradiction_log"] = log
    persistent["accumulated_contradiction_pressure"] = round(combined, 4)

    return ContradictionAccumulationState(
        bar_pressure=bar_pressure,
        accumulated_pressure=combined,
        escalation_level=escalation,
        active_count=active,
        cluster_count=len(clusters),
        recurrence_rate=recurrence_rate,
        aged_entries=len(log),
    )
