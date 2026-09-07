from __future__ import annotations

import re
from typing import Any


def canonical_tag(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return normalized[:100] or "uncategorized"


def audience_tags(value: str) -> list[str]:
    phrases = [part.strip() for part in re.split(r"[,;/]|\band\b", value, flags=re.I)]
    tags: list[str] = []
    for phrase in phrases:
        if phrase:
            tag = canonical_tag(phrase)
            if tag not in tags:
                tags.append(tag)
    return tags[:8] or ["general-professionals"]


def numeric_markers(value: str) -> set[str]:
    return set(re.findall(r"\b\d[\d.,%+\-]*\b", value))


def generated_draft_is_traceable(
    hook: str,
    body: str,
    cta: str,
    claims: list[dict[str, Any]],
    evidence_statements: list[str],
    allowed_context: str,
) -> bool:
    content = "\n\n".join((hook, body, cta))
    allowed_numbers = numeric_markers("\n".join([allowed_context, *evidence_statements]))
    if not numeric_markers(content) <= allowed_numbers:
        return False
    for claim in claims:
        text = str(claim.get("text", "")).strip()
        kind = claim.get("kind")
        indices = claim.get("evidence_indices") or []
        if not text or text not in content:
            return False
        if kind == "SUPPORTED":
            if not indices or any(
                not isinstance(index, int) or index < 1 or index > len(evidence_statements)
                for index in indices
            ):
                return False
            normalized_claim = " ".join(text.split()).casefold()
            if not any(
                normalized_claim == " ".join(evidence_statements[index - 1].split()).casefold()
                for index in indices
            ):
                return False
        elif kind == "OPINION":
            if indices:
                return False
        else:
            return False
    return True


def deterministic_primary_draft(topic: str, angle: str) -> dict[str, Any]:
    return {
        "hook": f"A practical way to think about {topic}:",
        "body": angle,
        "cta": "What has worked in your experience?",
        "claims": [
            {
                "text": angle,
                "kind": "OPINION",
                "evidence_indices": [],
            }
        ],
    }
