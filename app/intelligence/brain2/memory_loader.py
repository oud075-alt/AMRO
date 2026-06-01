"""Load research packs into contextual semantic memory (not static archive)."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from loguru import logger

_PACKS_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "data",
    "brain2",
    "packs",
)


@dataclass
class MemoryEntry:
    entry_id: str
    source: str
    kind: str
    payload: dict[str, Any]
    confidence: float = 0.5
    recurrence: int = 0
    contradiction_count: int = 0
    decay: float = 1.0


@dataclass
class SemanticMemoryStore:
    relations: list[dict[str, Any]] = field(default_factory=list)
    contradictions: list[dict[str, Any]] = field(default_factory=list)
    sequences: list[dict[str, Any]] = field(default_factory=list)
    narratives: list[dict[str, Any]] = field(default_factory=list)
    governance_templates: list[dict[str, Any]] = field(default_factory=list)
    failure_memories: list[dict[str, Any]] = field(default_factory=list)
    entries: list[MemoryEntry] = field(default_factory=list)
    loaded_files: int = 0

    @property
    def available(self) -> bool:
        return self.loaded_files > 0


def _load_json_file(path: str) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _walk_packs(root: str) -> list[str]:
    if not os.path.isdir(root):
        return []
    out: list[str] = []
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            if name.endswith(".json"):
                out.append(os.path.join(dirpath, name))
    return out


def _classify_file(rel: str, data: Any) -> str:
    low = rel.lower()
    if "contradiction" in low:
        return "contradiction"
    if "negative_outcome" in low or "failure" in low and "mode" in low:
        return "failure_memory"
    if "sequence" in low or "transition" in low or "emotion_sequence" in low or "collapse" in low:
        return "sequence"
    if "narrative" in low:
        return "narrative"
    if "governance" in low or "confidence_governance" in low:
        return "governance"
    if "pathology" in low or "microstructure" in low or "uncertainty" in low:
        return "relation"
    if isinstance(data, list) and data and isinstance(data[0], dict):
        row = data[0]
        if "observed_conflict" in row:
            return "contradiction"
        if "failure_id" in row or "failure_mode" in row and "negative_outcome" in row:
            return "failure_memory"
        if "state_flow" in row or "visual_signals" in row:
            return "sequence"
        if "market_story" in row:
            return "narrative"
        if "governance_implication" in row and "from_behavior" not in row:
            return "governance"
        if "from_behavior" in row and "to_behavior" in row:
            return "relation"
    return "relation"


def reload_semantic_memory() -> SemanticMemoryStore:
    """Clear cache after pack ingest — required post-audit expansion."""
    load_semantic_memory.cache_clear()
    return load_semantic_memory()


@lru_cache(maxsize=1)
def load_semantic_memory() -> SemanticMemoryStore:
    store = SemanticMemoryStore()
    if not os.path.isdir(_PACKS_ROOT):
        logger.warning(f"[Brain2Memory] packs root missing: {_PACKS_ROOT}")
        return store

    for path in _walk_packs(_PACKS_ROOT):
        rel = os.path.relpath(path, _PACKS_ROOT)
        try:
            data = _load_json_file(path)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(f"[Brain2Memory] skip {rel}: {exc}")
            continue

        store.loaded_files += 1
        kind = _classify_file(rel, data)
        rows = data if isinstance(data, list) else [data]

        for i, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            entry_id = str(
                row.get("contradiction_id")
                or row.get("sequence_id")
                or row.get("relation_id")
                or row.get("failure_id")
                or row.get("narrative_id")
                or row.get("context_id")
                or f"{rel}:{i}"
            )
            conf = float(row.get("semantic_weight") or row.get("confidence") or 0.5)
            decay = float(row.get("decay") or row.get("decay_half_life_bars", 100))
            entry = MemoryEntry(
                entry_id=entry_id,
                source=rel,
                kind=kind,
                payload=row,
                confidence=min(1.0, max(0.05, conf)),
                decay=min(1.0, max(0.1, 1.0 / max(1.0, decay / 50.0))),
            )
            store.entries.append(entry)
            if kind == "contradiction":
                store.contradictions.append(row)
            elif kind == "sequence":
                store.sequences.append(row)
            elif kind == "narrative":
                store.narratives.append(row)
            elif kind == "governance":
                store.governance_templates.append(row)
            elif kind == "failure_memory":
                store.failure_memories.append(row)
            else:
                store.relations.append(row)

    logger.info(
        f"[Brain2Memory] loaded files={store.loaded_files} "
        f"relations={len(store.relations)} contradictions={len(store.contradictions)} "
        f"sequences={len(store.sequences)} failures={len(store.failure_memories)}"
    )
    return store
