from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Iterable

from .contracts import ChallengeContract, OutputField, RetrievalHit
from .retrieval import tokenize
from .utils import split_sentences

_STATUS_NAMES = {"status", "decision", "route"}
_AREA_NAMES = {"product_area", "category", "area", "domain"}
_REQUEST_TYPE_NAMES = {"request_type", "issue_type", "type"}
_RESPONSE_NAMES = {"response", "answer", "reply"}
_JUSTIFICATION_NAMES = {"justification", "rationale", "reason"}

_FEATURE_HINTS = ("feature", "can you add", "would love", "wishlist", "request")
_BUG_HINTS = ("bug", "error", "broken", "crash", "charged twice", "duplicate charge")
_INVALID_HINTS = ("test", "asdf", "ignore this")
_MANUAL_REVIEW_HINTS = (
    "manual review",
    "manual investigation",
    "should be escalated",
    "escalated to",
)


def field_kind(field_name: str) -> str:
    lowered = field_name.lower()
    if lowered in _STATUS_NAMES:
        return "status"
    if lowered in _AREA_NAMES or lowered.endswith("_area"):
        return "product_area"
    if lowered in _REQUEST_TYPE_NAMES or "request_type" in lowered:
        return "request_type"
    if lowered in _RESPONSE_NAMES or lowered.endswith("response"):
        return "response"
    if lowered in _JUSTIFICATION_NAMES or lowered.endswith("justification"):
        return "justification"
    return "other"


def _canonical_allowed(allowed_values: list[str], candidate: str) -> str:
    if not allowed_values:
        return candidate.strip()
    if not candidate.strip():
        return allowed_values[0]

    lowered_map = {value.lower(): value for value in allowed_values}
    candidate_lower = candidate.strip().lower()
    if candidate_lower in lowered_map:
        return lowered_map[candidate_lower]

    for allowed in allowed_values:
        allowed_lower = allowed.lower()
        if candidate_lower in allowed_lower or allowed_lower in candidate_lower:
            return allowed

    candidate_tokens = set(tokenize(candidate))
    best_value = allowed_values[0]
    best_score = -1
    for allowed in allowed_values:
        score = len(candidate_tokens & set(tokenize(allowed)))
        if score > best_score:
            best_score = score
            best_value = allowed
    return best_value


def classify_request_type(text: str, allowed_values: list[str]) -> str:
    if not allowed_values:
        return ""
    text_lower = text.lower()
    if any(hint in text_lower for hint in _FEATURE_HINTS) and any(
        value.lower() == "feature_request" for value in allowed_values
    ):
        return _canonical_allowed(allowed_values, "feature_request")
    if any(hint in text_lower for hint in _BUG_HINTS) and any(
        value.lower() == "bug" for value in allowed_values
    ):
        return _canonical_allowed(allowed_values, "bug")
    if any(hint in text_lower for hint in _INVALID_HINTS) and any(
        value.lower() == "invalid" for value in allowed_values
    ):
        return _canonical_allowed(allowed_values, "invalid")
    if any(value.lower() == "product_issue" for value in allowed_values):
        return _canonical_allowed(allowed_values, "product_issue")
    return allowed_values[0]


def infer_product_area(
    text: str, hits: list[RetrievalHit], allowed_values: list[str]
) -> str:
    if not allowed_values:
        return ""
    evidence = text.lower()
    if hits:
        top_hit = hits[0]
        evidence += (
            " " + f"{top_hit.title} {top_hit.source_path} {top_hit.text}".lower()
        )
    evidence_tokens = Counter(tokenize(evidence))

    best_value = allowed_values[0]
    best_score = -1
    for value in allowed_values:
        tokens = tokenize(value)
        score = sum(evidence_tokens[token] for token in tokens)
        if value.lower() in evidence:
            score += 3
        if score > best_score:
            best_score = score
            best_value = value
    if best_score <= 0 and any(value.lower() == "general" for value in allowed_values):
        return _canonical_allowed(allowed_values, "general")
    return best_value


def _scored_sentences(query: str, text: str) -> list[tuple[int, int, str]]:
    query_terms = Counter(tokenize(query))
    scored: list[tuple[int, int, str]] = []
    for index, sentence in enumerate(split_sentences(text)):
        sentence_terms = Counter(tokenize(sentence))
        score = sum(
            min(query_terms[token], sentence_terms[token]) for token in query_terms
        )
        if score > 0:
            scored.append((score, index, sentence))
    return scored


def best_supporting_sentences(
    query: str, hit: RetrievalHit, *, limit: int = 2
) -> list[str]:
    scored = _scored_sentences(query, hit.text)
    if not scored:
        return split_sentences(hit.text)[:limit]
    selected = sorted(
        sorted(scored, key=lambda item: (-item[0], item[1]))[:limit],
        key=lambda item: item[1],
    )
    return [sentence for _, _, sentence in selected]


def best_manual_review_sentence(query: str, hits: list[RetrievalHit]) -> str | None:
    if not hits:
        return None
    for sentence in split_sentences(hits[0].text):
        sentence_lower = sentence.lower()
        if any(hint in sentence_lower for hint in _MANUAL_REVIEW_HINTS):
            overlap = set(tokenize(query)) & set(tokenize(sentence))
            if overlap:
                return sentence
    return None


def find_escalation_reasons(
    query: str, hits: list[RetrievalHit], contract: ChallengeContract
) -> list[str]:
    reasons: list[str] = []
    query_lower = query.lower()

    for keyword in contract.rules.escalation_keywords:
        if keyword.lower() in query_lower:
            reasons.append(f"matched keyword '{keyword}'")

    if not hits or hits[0].score < contract.rules.min_evidence_score:
        reasons.append("evidence was below the confidence threshold")

    if any(hint in query_lower for hint in _FEATURE_HINTS):
        top_hit_text = hits[0].text.lower() if hits else ""
        if "feature" not in top_hit_text and "request" not in top_hit_text:
            reasons.append("evidence was below the confidence threshold")

    manual_review_sentence = best_manual_review_sentence(query, hits)
    if manual_review_sentence:
        reasons.append("the evidence indicates manual review is required")

    deduped: list[str] = []
    seen: set[str] = set()
    for reason in reasons:
        if reason not in seen:
            deduped.append(reason)
            seen.add(reason)
    return deduped


def _status_default(allowed_values: list[str], *, escalated: bool) -> str:
    for preferred in (
        ["escalated", "reply", "replied"]
        if escalated
        else ["replied", "reply", "resolved"]
    ):
        for value in allowed_values:
            if preferred in value.lower():
                return value
    return (
        allowed_values[0]
        if allowed_values
        else ("escalated" if escalated else "replied")
    )


def build_direct_response(query: str, hits: list[RetrievalHit]) -> str:
    if not hits:
        return "No grounded evidence was retrieved for this request."
    sentences = best_supporting_sentences(query, hits[0], limit=2)
    return " ".join(sentences)


def build_direct_justification(hits: list[RetrievalHit]) -> str:
    if not hits:
        return "Answered without a strong supporting source."
    return f"Answered from {Path(hits[0].source_path).name} because it directly covers the request."


def build_escalation_response(
    query: str, hits: list[RetrievalHit], reasons: Iterable[str]
) -> str:
    reason_set = list(reasons)
    manual_review_sentence = best_manual_review_sentence(query, hits)
    if manual_review_sentence:
        return f"Escalated for manual review. {manual_review_sentence}"
    if "evidence was below the confidence threshold" in reason_set:
        return "Escalated for manual review. The available corpus does not contain grounded guidance for this request."
    return "Escalated for manual review based on the available evidence."


def build_escalation_justification(
    hits: list[RetrievalHit], reasons: Iterable[str]
) -> str:
    reason_list = list(reasons)
    if hits and "the evidence indicates manual review is required" in reason_list:
        return f"Escalated because the evidence indicates manual review is required. Grounded in {Path(hits[0].source_path).name}."
    if "evidence was below the confidence threshold" in reason_list:
        return "Escalated because evidence was below the confidence threshold."
    if reason_list:
        return f"Escalated because {reason_list[0]}."
    return "Escalated for manual review."


def finalize_values(
    contract: ChallengeContract,
    draft: dict[str, str],
    *,
    query: str,
    hits: list[RetrievalHit],
    product_area: str,
    request_type: str,
    escalation_reasons: list[str],
) -> dict[str, str]:
    finalized: dict[str, str] = {}
    escalated = bool(escalation_reasons)

    for field in contract.output_fields:
        kind = field_kind(field.name)
        candidate = str(draft.get(field.name, "")).strip()

        if not candidate:
            if kind == "status":
                candidate = _status_default(field.allowed_values, escalated=escalated)
            elif kind == "product_area":
                if (
                    escalated
                    and any(
                        value.lower() == "general" for value in field.allowed_values
                    )
                    and "evidence was below the confidence threshold"
                    in escalation_reasons
                ):
                    candidate = _canonical_allowed(field.allowed_values, "general")
                else:
                    candidate = product_area
            elif kind == "request_type":
                candidate = request_type
            elif kind == "response":
                candidate = (
                    build_escalation_response(query, hits, escalation_reasons)
                    if escalated
                    else build_direct_response(query, hits)
                )
            elif kind == "justification":
                candidate = (
                    build_escalation_justification(hits, escalation_reasons)
                    if escalated
                    else build_direct_justification(hits)
                )
            elif field.allowed_values:
                candidate = field.allowed_values[0]

        if field.allowed_values:
            if kind == "status":
                candidate = _status_default(field.allowed_values, escalated=escalated)
            elif kind == "product_area" and product_area:
                if (
                    escalated
                    and any(
                        value.lower() == "general" for value in field.allowed_values
                    )
                    and "evidence was below the confidence threshold"
                    in escalation_reasons
                ):
                    candidate = _canonical_allowed(field.allowed_values, "general")
                else:
                    candidate = _canonical_allowed(field.allowed_values, product_area)
            elif kind == "request_type" and request_type:
                candidate = _canonical_allowed(field.allowed_values, request_type)
            else:
                candidate = _canonical_allowed(field.allowed_values, candidate)

        finalized[field.name] = candidate
    return finalized
