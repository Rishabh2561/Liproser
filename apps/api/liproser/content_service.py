from __future__ import annotations

import re


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
