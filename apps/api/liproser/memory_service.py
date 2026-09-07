from __future__ import annotations

import hashlib
import math
import re
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, aliased

from .database import (
    BOOTSTRAP_WORKSPACE_ID,
    EMBEDDING_DIMENSIONS,
    ContentIdea,
    Post,
    PostRevision,
    Review,
    RevisionEmbedding,
    RevisionMemoryEligibility,
    RevisionRetrieval,
)

EMBEDDING_VERSION = "hash-embedding@1"


def embed_text(value: str) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMENSIONS
    for token in re.findall(r"[a-z0-9]+", value.casefold()):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSIONS
        vector[index] += -1.0 if digest[4] & 1 else 1.0
    norm = math.sqrt(sum(item * item for item in vector))
    return [item / norm for item in vector] if norm else vector


def cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


def upsert_memory_status(
    db: Session, revision: PostRevision, *, eligible: bool, reason: str
) -> None:
    status = db.get(RevisionMemoryEligibility, revision.id)
    if status is None:
        status = RevisionMemoryEligibility(
            revision_id=revision.id, eligible=eligible, reason=reason
        )
        db.add(status)
    else:
        status.eligible = eligible
        status.reason = reason
        status.evaluated_at = datetime.now(UTC)
    if eligible:
        embedding = db.get(RevisionEmbedding, revision.id)
        content_hash = hashlib.sha256(revision.content.encode("utf-8")).hexdigest()
        if embedding is None:
            db.add(
                RevisionEmbedding(
                    revision_id=revision.id,
                    embedding_version=EMBEDDING_VERSION,
                    content_hash=content_hash,
                    embedding=embed_text(revision.content),
                )
            )
        elif embedding.content_hash != content_hash:
            embedding.content_hash = content_hash
            embedding.embedding_version = EMBEDDING_VERSION
            embedding.embedding = embed_text(revision.content)


def eligible_revisions(
    db: Session, *, taxonomy_version: str | None = None
) -> list[tuple[PostRevision, Post, ContentIdea, RevisionEmbedding]]:
    candidate_revision = aliased(PostRevision)
    latest_revision_number = (
        select(func.max(candidate_revision.revision_number))
        .where(candidate_revision.post_id == Post.id)
        .correlate(Post)
        .scalar_subquery()
    )
    statement = (
        select(PostRevision, Post, ContentIdea, RevisionEmbedding)
        .join(Post, Post.id == PostRevision.post_id)
        .join(ContentIdea, ContentIdea.id == Post.content_idea_id)
        .join(
            RevisionMemoryEligibility,
            RevisionMemoryEligibility.revision_id == PostRevision.id,
        )
        .join(RevisionEmbedding, RevisionEmbedding.revision_id == PostRevision.id)
        .outerjoin(
            Review,
            (Review.revision_id == PostRevision.id) & (Review.action == "APPROVE"),
        )
        .where(
            RevisionMemoryEligibility.workspace_id == BOOTSTRAP_WORKSPACE_ID,
            RevisionMemoryEligibility.eligible.is_(True),
            Post.workspace_id == BOOTSTRAP_WORKSPACE_ID,
            or_(
                RevisionMemoryEligibility.reason == "PUBLISHED_REVISION",
                and_(
                    Post.state.in_(["APPROVED", "SCHEDULED", "PUBLISH_ACTION_REQUIRED"]),
                    PostRevision.revision_number == latest_revision_number,
                    Review.id.is_not(None),
                ),
            ),
        )
    )
    if taxonomy_version:
        statement = statement.where(PostRevision.taxonomy_version == taxonomy_version)
    return list(db.execute(statement.order_by(PostRevision.created_at.desc())).all())


def retrieve_memory(
    db: Session, *, query: str, taxonomy_version: str, exclude_post_id: str | None = None
) -> list[dict]:
    query_vector = embed_text(query)
    ranked = []
    for revision, post, idea, embedding in eligible_revisions(
        db, taxonomy_version=taxonomy_version
    ):
        if post.id == exclude_post_id:
            continue
        ranked.append(
            {
                "revision_id": revision.id,
                "post_id": post.id,
                "pillar": idea.pillar,
                "topic": idea.topic,
                "similarity_score": round(cosine(query_vector, list(embedding.embedding)), 6),
                "embedding_version": embedding.embedding_version,
                "taxonomy_version": revision.taxonomy_version,
                "features": structural_features(revision),
            }
        )
    ranked.sort(key=lambda item: (-item["similarity_score"], item["revision_id"]))
    return ranked[:3]


def record_retrievals(db: Session, revision: PostRevision, references: list[dict]) -> None:
    revision.retrieved_revision_ids = [item["revision_id"] for item in references]
    for rank, item in enumerate(references, start=1):
        db.add(
            RevisionRetrieval(
                id=str(uuid4()),
                generated_revision_id=revision.id,
                reference_revision_id=item["revision_id"],
                similarity_score=item["similarity_score"],
                embedding_version=item["embedding_version"],
                taxonomy_version=item["taxonomy_version"],
                rank=rank,
            )
        )


def structural_features(revision: PostRevision) -> dict:
    words = re.findall(r"[A-Za-z0-9']+", revision.content)
    return {
        "hook_style": "QUESTION" if revision.hook.rstrip().endswith("?") else "STATEMENT",
        "word_count": len(words),
        "paragraph_count": len([part for part in revision.content.split("\n\n") if part]),
        "cta_style": "QUESTION" if revision.cta.rstrip().endswith("?") else "STATEMENT",
    }


def lexical_similarity(left: str, right: str) -> float:
    def shingles(value: str) -> set[tuple[str, ...]]:
        words = re.findall(r"[a-z0-9]+", value.casefold())
        width = 3 if len(words) >= 3 else 1
        return {tuple(words[index : index + width]) for index in range(len(words) - width + 1)}

    a, b = shingles(left), shingles(right)
    return len(a & b) / len(a | b) if a or b else 0.0


def memory_checks(content: str, hook: str, references: list[dict], db: Session) -> list[dict]:
    comparisons = []
    repeated_hooks = 0
    del references  # Retrieval context is bounded; checks cover the full eligible corpus.
    for reference, _post, _idea, _embedding in eligible_revisions(db):
        score = round(lexical_similarity(content, reference.content), 4)
        comparisons.append({"revision_id": reference.id, "similarity": score})
        repeated_hooks += int(reference.hook.casefold() == hook.casefold())
    maximum = max((item["similarity"] for item in comparisons), default=0.0)
    return [
        {
            "check_type": "ORIGINALITY",
            "severity": "BLOCKING",
            "passed": maximum < 0.82,
            "message": "Draft is distinct from eligible first-party memory." if maximum < 0.82 else "Rewrite passages that are too close to an approved post.",
            "details": {"maximum_similarity": maximum, "comparisons": comparisons},
        },
        {
            "check_type": "DIVERSITY",
            "severity": "WARNING",
            "passed": repeated_hooks == 0,
            "message": "Hook structure adds variety." if repeated_hooks == 0 else "The hook exactly repeats an approved post; consider a different opening.",
            "details": {"exact_hook_repetitions": repeated_hooks},
        },
    ]
