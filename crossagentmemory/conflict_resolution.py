"""Auto conflict resolution — detect and resolve contradictory memories.

When a new memory contradicts an old one, automatically:
- Detect the contradiction via LLM
- Reduce confidence of the outdated memory
- Or set valid_until to expire the old fact
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .core import MemoryEngine, MemoryEntry
from .llm import LLMClient, get_llm_client
from .semantic import SemanticIndex

SYSTEM_CONFLICT_RESOLVER = (
    "You are a precise technical arbiter. Given two statements about a software project, "
    "determine if they contradict each other and which one is more current/accurate. "
    "Output valid JSON only."
)


def _sanitize_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def find_contradictions_for_memory(
    engine: MemoryEngine,
    new_memory: MemoryEntry,
    threshold: float = 0.25,
    client: LLMClient | None = None,
) -> list[dict[str, Any]]:
    """Find existing memories that may contradict a new memory.

    Returns list of dicts with keys: memory, similarity, contradiction_verdict.
    """
    client = client or get_llm_client()
    if new_memory.id is None:
        return []

    # Find semantically similar memories in the same project
    index = SemanticIndex(engine, new_memory.project, backend="tfidf")
    try:
        results = index.search(new_memory.content, top_k=10)
    except Exception:
        return []
    # Filter by similarity threshold
    results = [(r, s) for r, s in results if s >= threshold]

    contradictions: list[dict[str, Any]] = []
    content_map: dict[int, str] = {}

    for related, score in results:
        if related.id == new_memory.id or related.id is None:
            continue
        content_map[related.id] = related.content
        # Quick keyword overlap check to avoid obvious non-contradictions
        contradictions.append({
            "memory": related,
            "similarity": score,
            "contradiction_verdict": None,
        })

    if not contradictions or not client.is_available():
        return contradictions

    # LLM verification in batches
    for item in contradictions:
        mem = item["memory"]
        verdict = _llm_resolve_conflict(new_memory.content, mem.content, client)
        item["contradiction_verdict"] = verdict

    # Only keep actual contradictions
    return [
        item
        for item in contradictions
        if item["contradiction_verdict"]
        and item["contradiction_verdict"].get("is_contradiction", False)
    ]


def _llm_resolve_conflict(
    text_a: str, text_b: str, client: LLMClient
) -> dict[str, Any] | None:
    """Ask LLM to arbitrate between two statements.

    Returns {"is_contradiction": bool, "outdated": "a"|"b"|"both"|"none", "reason": str}
    """
    prompt = (
        "Analyze these two statements about a software project.\n\n"
        f"A: {text_a}\n\n"
        f"B: {text_b}\n\n"
        "Return valid JSON with exactly these keys:\n"
        "- is_contradiction (boolean): do they contradict?\n"
        "- outdated (string): 'a', 'b', 'both', or 'none' — which is outdated?\n"
        "- reason (string): one-sentence explanation\n"
        "Be conservative: only flag true contradictions, not minor differences."
    )

    resp = client.chat(prompt, system=SYSTEM_CONFLICT_RESOLVER)
    raw = _sanitize_json(resp.text)

    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            return None
        return {
            "is_contradiction": bool(data.get("is_contradiction", False)),
            "outdated": str(data.get("outdated", "none")),
            "reason": str(data.get("reason", "")),
        }
    except (json.JSONDecodeError, ValueError, TypeError):
        return None


def auto_resolve_conflicts(
    engine: MemoryEngine,
    new_memory: MemoryEntry,
    strategy: str = "decay",
    decay_amount: float = 0.3,
    client: LLMClient | None = None,
) -> list[dict[str, Any]]:
    """Automatically resolve conflicts for a newly captured memory.

    Args:
        engine: MemoryEngine instance
        new_memory: The memory just captured (must have id set)
        strategy: "decay" (reduce confidence), "expire" (set valid_until), or "both"
        decay_amount: How much to reduce confidence (0.0-1.0)
        client: Optional LLM client

    Returns:
        List of resolution actions taken
    """
    if new_memory.id is None:
        return []

    contradictions = find_contradictions_for_memory(
        engine, new_memory, client=client
    )
    actions: list[dict[str, Any]] = []

    for item in contradictions:
        mem = item["memory"]
        verdict = item["contradiction_verdict"]
        if not verdict:
            continue

        outdated = verdict.get("outdated", "none")
        if outdated not in ("a", "b"):
            continue

        # 'a' is the new memory, 'b' is the existing one
        target_id = mem.id if outdated == "b" else new_memory.id
        is_new_outdated = outdated == "a"

        action: dict[str, Any] = {
            "memory_id": target_id,
            "outdated": is_new_outdated,
            "reason": verdict.get("reason", ""),
            "strategy": strategy,
            "changes": {},
        }

        if strategy in ("decay", "both") and not is_new_outdated:
            # Reduce confidence of old memory
            old_confidence = mem.confidence
            new_confidence = max(0.0, old_confidence - decay_amount)
            engine.update_memory(mem.id, {"confidence": round(new_confidence, 4)})
            action["changes"]["confidence"] = {
                "from": old_confidence,
                "to": new_confidence,
            }

        if strategy in ("expire", "both") and not is_new_outdated:
            # Expire the old memory
            engine.update_memory(mem.id, {"valid_until": _now_iso()})
            action["changes"]["valid_until"] = _now_iso()

        actions.append(action)

    return actions


def scan_and_resolve_project(
    engine: MemoryEngine,
    project: str,
    strategy: str = "decay",
    decay_amount: float = 0.3,
    client: LLMClient | None = None,
) -> list[dict[str, Any]]:
    """Scan all memories in a project and resolve any contradictions found.

    This is useful for backfilling conflict resolution on existing data.
    """
    client = client or get_llm_client()
    memories = engine.recall(project=project, limit=100)
    all_actions: list[dict[str, Any]] = []

    # Check each decision/fact against later memories
    for i, older in enumerate(memories):
        if older.id is None:
            continue
        for newer in memories[i + 1 :]:
            if newer.id is None:
                continue
            verdict = _llm_resolve_conflict(older.content, newer.content, client)
            if not verdict or not verdict.get("is_contradiction"):
                continue
            outdated = verdict.get("outdated", "none")
            if outdated == "a":
                target = older
            elif outdated == "b":
                target = newer
            else:
                continue

            action: dict[str, Any] = {
                "memory_id": target.id,
                "reason": verdict.get("reason", ""),
                "strategy": strategy,
                "changes": {},
            }

            if strategy in ("decay", "both"):
                old_confidence = target.confidence
                new_confidence = max(0.0, old_confidence - decay_amount)
                engine.update_memory(target.id, {"confidence": round(new_confidence, 4)})
                action["changes"]["confidence"] = {
                    "from": old_confidence,
                    "to": new_confidence,
                }

            if strategy in ("expire", "both"):
                engine.update_memory(target.id, {"valid_until": _now_iso()})
                action["changes"]["valid_until"] = _now_iso()

            all_actions.append(action)

    return all_actions
