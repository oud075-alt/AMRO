"""Runtime semantic compression — prevent memory explosion before it starts."""
from __future__ import annotations

from typing import Any


def compress_persistent_state(state: dict[str, Any], *, bar_index: int, max_contra: int = 80, max_mutations: int = 40) -> dict[str, Any]:
    state["contradiction_log"] = _compress_contradictions(
        state.get("contradiction_log") or [],
        bar_index=bar_index,
        cap=max_contra,
    )
    state["semantic_mutations"] = _dedupe_mutations(state.get("semantic_mutations") or [], cap=max_mutations)
    state["sequence_log"] = _dedupe_sequence(state.get("sequence_log") or [], cap=30)
    state["contradiction_log"] = _failure_priority_retain(state["contradiction_log"], bar_index)
    return state


def _compress_contradictions(log: list[dict[str, Any]], *, bar_index: int, cap: int) -> list[dict[str, Any]]:
    if not log:
        return log
    merged: dict[str, dict[str, Any]] = {}
    for entry in log:
        age = bar_index - int(entry.get("bar", bar_index))
        sev = float(entry.get("severity", 0))
        if age > 120 and sev < 0.25:
            continue
        key = f"{entry.get('cluster', entry.get('id', ''))}:{entry.get('regime', '')}"
        prev = merged.get(key)
        if prev is None or sev > float(prev.get("severity", 0)):
            merged[key] = entry
    out = sorted(merged.values(), key=lambda x: int(x.get("bar", 0)))
    if len(out) > cap:
        high = sorted(out, key=lambda x: float(x.get("severity", 0)), reverse=True)[: cap // 3]
        recent = out[-(cap - len(high)) :]
        seen: set[str] = set()
        combined: list[dict[str, Any]] = []
        for item in high + recent:
            kid = str(item.get("id", id(item)))
            if kid in seen:
                continue
            seen.add(kid)
            combined.append(item)
        out = sorted(combined, key=lambda x: int(x.get("bar", 0)))[-cap:]
    return out


def _dedupe_mutations(log: list[dict[str, Any]], *, cap: int) -> list[dict[str, Any]]:
    if not log:
        return log
    seen: dict[str, dict[str, Any]] = {}
    for entry in log:
        key = f"{entry.get('behavior')}:{entry.get('phase')}"
        seen[key] = entry
    out = list(seen.values())
    return out[-cap:]


def _dedupe_sequence(log: list[dict[str, Any]], *, cap: int) -> list[dict[str, Any]]:
    if not log:
        return log
    out: list[dict[str, Any]] = []
    last_key = ""
    for entry in log:
        key = str(entry.get("key", ""))
        if key == last_key:
            continue
        out.append(entry)
        last_key = key
    return out[-cap:]


def _failure_priority_retain(log: list[dict[str, Any]], bar_index: int) -> list[dict[str, Any]]:
    """Keep high-severity / recent contradictions; prune semantic entropy."""
    if len(log) <= 60:
        return log
    scored = []
    for entry in log:
        age = bar_index - int(entry.get("bar", bar_index))
        sev = float(entry.get("severity", 0))
        entropy_prune = age > 80 and sev < 0.35
        if entropy_prune:
            continue
        score = sev * 0.7 + max(0, 1.0 - age / 200.0) * 0.3
        scored.append((score, entry))
    scored.sort(key=lambda x: x[0], reverse=True)
    kept = [e for _, e in scored[:80]]
    kept.sort(key=lambda x: int(x.get("bar", 0)))
    return kept
