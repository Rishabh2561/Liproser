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


def deterministic_regeneration_draft(
    topic: str,
    angle: str,
    categories: list[str],
    evidence_statements: list[str],
) -> dict[str, Any]:
    hook = f"A practical way to think about {topic}:"
    cta = "What has worked in your experience?"
    if "HOOK" in categories or "CLARITY" in categories:
        hook = f"{topic}, stated plainly:"
    elif "TONE" in categories:
        hook = f"A practical observation about {topic}:"
    if "CTA" in categories:
        cta = "Which part would you make explicit first?"
    body = evidence_statements[0] if "EVIDENCE" in categories and evidence_statements else angle
    kind = "SUPPORTED" if body in evidence_statements else "OPINION"
    evidence_indices = [evidence_statements.index(body) + 1] if kind == "SUPPORTED" else []
    return {
        "hook": hook,
        "body": body,
        "cta": cta,
        "claims": [{"text": body, "kind": kind, "evidence_indices": evidence_indices}],
    }


def user_edit_claims(content_parts: list[str], evidence_statements: list[str]) -> list[dict[str, Any]]:
    evidence_lookup = {
        " ".join(statement.split()).casefold(): index
        for index, statement in enumerate(evidence_statements, start=1)
    }
    claims: list[dict[str, Any]] = []
    for text in content_parts:
        normalized = " ".join(text.split()).casefold()
        evidence_index = evidence_lookup.get(normalized)
        claims.append(
            {
                "text": text,
                "kind": "SUPPORTED" if evidence_index else "CONFIRMED_PERSONAL",
                "evidence_indices": [evidence_index] if evidence_index else [],
            }
        )
    return claims


def evaluate_revision_checks(
    content: str,
    claims: list[dict[str, Any]],
    allowed_context: str,
    evidence_statements: list[str],
    prohibited_phrases: list[str],
) -> list[dict[str, Any]]:
    allowed_numbers = numeric_markers("\n".join([allowed_context, *evidence_statements]))
    unexpected_numbers = sorted(numeric_markers(content) - allowed_numbers)
    blocked_phrases = sorted(
        phrase for phrase in prohibited_phrases if phrase.casefold() in content.casefold()
    )
    words = re.findall(r"\b[\w'-]+\b", content)
    sentences = [part for part in re.split(r"[.!?]+", content) if part.strip()]
    average_sentence_words = round(len(words) / max(len(sentences), 1), 1)
    paragraphs = [part.strip() for part in content.split("\n\n") if part.strip()]
    longest_paragraph = max((len(part) for part in paragraphs), default=0)
    letters = [char for char in content if char.isalpha()]
    uppercase_ratio = round(
        sum(char.isupper() for char in letters) / max(len(letters), 1), 3
    )
    has_claims = bool(claims) and all(claim.get("kind") != "UNSUPPORTED" for claim in claims)
    claim_passed = not unexpected_numbers and has_claims
    readability_passed = average_sentence_words <= 30
    accessibility_passed = longest_paragraph <= 500 and uppercase_ratio <= 0.35
    return [
        {
            "check_type": "CLAIM_TRACEABILITY",
            "severity": "BLOCKING",
            "passed": claim_passed,
            "message": (
                "Claims and numeric details are traceable to confirmed input."
                if claim_passed
                else "Confirm or remove unsupported numeric details before approval."
            ),
            "details": {"unexpected_numbers": unexpected_numbers, "claim_count": len(claims)},
        },
        {
            "check_type": "PROHIBITED_PHRASES",
            "severity": "BLOCKING",
            "passed": not blocked_phrases,
            "message": (
                "No prohibited voice phrases were found."
                if not blocked_phrases
                else "Remove prohibited voice phrases before approval."
            ),
            "details": {"matched_phrases": blocked_phrases},
        },
        {
            "check_type": "READABILITY",
            "severity": "WARNING",
            "passed": readability_passed,
            "message": (
                "Sentence length is easy to scan."
                if readability_passed
                else "Consider shortening sentences for faster scanning."
            ),
            "details": {"average_sentence_words": average_sentence_words},
        },
        {
            "check_type": "ACCESSIBILITY",
            "severity": "WARNING",
            "passed": accessibility_passed,
            "message": (
                "Paragraph length and capitalization pass the accessibility check."
                if accessibility_passed
                else "Break up long paragraphs or reduce all-caps text."
            ),
            "details": {
                "longest_paragraph_characters": longest_paragraph,
                "uppercase_ratio": uppercase_ratio,
            },
        },
    ]
