from __future__ import annotations

import re
from io import BytesIO

from pypdf import PdfReader

from .schemas import ProfileSections

SECTION_NAMES = {
    "headline": "headline",
    "about": "about",
    "summary": "about",
    "experience": "experience",
    "skills": "skills",
    "featured": "featured",
}

EMPTY_SECTION_TEMPLATES = {
    "headline": "[Target role] | [Core expertise] | [Outcome you help create]",
    "about": (
        "I help [target audience] achieve [outcome] through [skills or approach].\n\n"
        "My experience includes [verified responsibility or achievement].\n\n"
        "I am currently focused on [goal, domain, or opportunity]."
    ),
    "experience": (
        "[Role] — [Company or organization]\n"
        "[Start date]–[End date or Present]\n"
        "• [What you owned]\n"
        "• [What you changed and how]\n"
        "• [Verified result or scale]"
    ),
    "skills": "[Primary skill] · [Supporting skill] · [Tool or platform] · [Domain knowledge]",
    "featured": "[Project, article, or portfolio item] — [What it demonstrates or achieved]",
}


def extract_pdf(content: bytes) -> tuple[ProfileSections, dict[str, float]]:
    if not content.startswith(b"%PDF-"):
        raise ValueError("File is not a PDF")
    if any(marker in content for marker in (b"/JavaScript", b"/JS", b"/OpenAction", b"/Launch")):
        raise ValueError("PDF contains active content and was rejected")
    reader = PdfReader(BytesIO(content))
    if reader.is_encrypted:
        raise ValueError("Encrypted PDFs are not supported")
    text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    if not text:
        raise ValueError("The PDF contains no extractable text")

    buckets: dict[str, list[str]] = {name: [] for name in ProfileSections.model_fields}
    current = "about"
    recognized = 0
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        normalized = re.sub(r"[^a-z]", "", line.lower())
        match = next((target for name, target in SECTION_NAMES.items() if normalized == name), None)
        if match:
            current = match
            recognized += 1
            continue
        buckets[current].append(line)

    sections = ProfileSections(**{key: "\n".join(value) for key, value in buckets.items()})
    base = 0.85 if recognized >= 3 else 0.55
    confidence = {key: (base if value else 0.0) for key, value in sections.model_dump().items()}
    return sections, confidence


def score_sections(sections: ProfileSections) -> tuple[float, dict]:
    criteria: dict[str, dict] = {}
    weights = {"headline": 20, "about": 25, "experience": 30, "skills": 15, "featured": 10}
    total = 0.0
    for name, maximum in weights.items():
        text = getattr(sections, name).strip()
        if not text:
            score = 0.0
            reasons = ["Section is missing"]
        else:
            length_factor = min(
                len(text)
                / {"headline": 80, "about": 500, "experience": 600, "skills": 100, "featured": 120}[
                    name
                ],
                1,
            )
            specificity = 1.0 if re.search(r"\b\d+(?:%|\b)", text) else 0.65
            readability = 1.0 if len(text.split()) / max(text.count(".") + 1, 1) <= 35 else 0.75
            score = maximum * (0.45 * length_factor + 0.35 * specificity + 0.20 * readability)
            reasons = [
                "Length/completeness measured",
                "Specificity measured without inventing facts",
                "Readability measured",
            ]
        total += score
        criteria[name] = {
            "score": round(score, 1),
            "maximum": maximum,
            "reasons": reasons,
            "confidence": 1.0,
        }
    return round(total, 1), criteria


def safe_suggestion(section: str, before: str) -> tuple[str, str, list[str], list[str], float]:
    text = before.strip()
    if not text:
        return (
            EMPTY_SECTION_TEMPLATES[section],
            "Fill in this structure with verified details. Bracketed prompts are guidance, not claims.",
            [],
            [],
            0.4,
        )
    preserved = [line.strip() for line in text.splitlines() if line.strip()][:20]
    if section == "headline":
        after = re.sub(r"\s*\|\s*", " · ", text)
        rationale = "Uses a cleaner separator while preserving every supplied term."
    elif section in {"about", "experience"}:
        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
        after = "\n\n".join(sentences)
        rationale = "Improves scanability without adding achievements or personal facts."
    elif section == "skills":
        terms = [part.strip() for part in re.split(r"[,|\n]", text) if part.strip()]
        after = " · ".join(dict.fromkeys(terms))
        rationale = "Removes duplicate skills and makes the list easier to scan."
    else:
        after = text
        rationale = "Preserves the supplied content; add a descriptive label or outcome after confirming it."
    return after, rationale, preserved, [], 0.95


def factual_markers(text: str) -> set[str]:
    numbers = re.findall(r"\b\d[\d.,%+\-]*\b", text)
    named = re.findall(r"\b[A-Z][A-Za-z0-9+#.\-]{1,}\b", text)
    ordinary_starts = {
        "a",
        "an",
        "as",
        "at",
        "built",
        "created",
        "developed",
        "i",
        "implemented",
        "in",
        "led",
        "my",
        "our",
        "the",
        "we",
    }
    return {
        value.casefold()
        for value in [*numbers, *named]
        if value.casefold() not in ordinary_starts
    }


def provider_suggestion_is_safe(before: str, after: str, proposed_claims: list[str]) -> bool:
    if proposed_claims or not after.strip():
        return False
    before_markers = factual_markers(before)
    after_markers = factual_markers(after)
    return before_markers <= after_markers and after_markers <= before_markers


def contains_template_placeholders(text: str) -> bool:
    return bool(re.search(r"\[[^\]]+\]", text))
