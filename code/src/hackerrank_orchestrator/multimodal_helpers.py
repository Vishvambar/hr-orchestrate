from __future__ import annotations

import csv
from pathlib import Path

from .image_utils import split_image_paths
from .retrieval import tokenize
from .utils import collapse_whitespace

ISSUE_TYPE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "glass_shatter": (
        "shattered glass",
        "glass shattered",
        "shattered",
        "spiderweb crack",
    ),
    "water_damage": ("water damage", "wet", "soaked", "liquid spill", "spill"),
    "crushed_packaging": ("crushed", "smashed box", "collapsed box", "flattened"),
    "torn_packaging": ("torn", "ripped", "opened seal", "split packaging"),
    "missing_part": ("missing", "fell off", "gone", "not there"),
    "broken_part": ("broken", "snapped", "detached", "hanging"),
    "crack": ("crack", "cracked"),
    "scratch": ("scratch", "scratched", "scuff"),
    "dent": ("dent", "dented", "ding"),
    "stain": ("stain", "stained", "mark", "discoloration"),
}

OBJECT_PART_KEYWORDS: dict[str, dict[str, tuple[str, ...]]] = {
    "car": {
        "front_bumper": ("front bumper",),
        "rear_bumper": ("rear bumper", "back bumper"),
        "door": ("door", "driver door", "passenger door"),
        "hood": ("hood",),
        "windshield": ("windshield", "front glass"),
        "side_mirror": ("mirror", "side mirror"),
        "headlight": ("headlight",),
        "taillight": ("taillight", "tail light"),
        "fender": ("fender",),
        "quarter_panel": ("quarter panel",),
        "body": ("body", "panel", "exterior"),
    },
    "laptop": {
        "screen": ("screen", "display", "monitor"),
        "keyboard": ("keyboard", "keys"),
        "trackpad": ("trackpad", "touchpad"),
        "hinge": ("hinge",),
        "lid": ("lid", "top cover"),
        "corner": ("corner",),
        "port": ("port", "usb port", "charging port"),
        "base": ("base", "bottom"),
        "body": ("body", "chassis"),
    },
    "package": {
        "box": ("box", "package"),
        "package_corner": ("corner",),
        "package_side": ("side",),
        "seal": ("seal", "tape"),
        "label": ("label", "shipping label"),
        "contents": ("contents", "inside"),
        "item": ("item", "product"),
    },
}


def load_csv_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_user_history_map(path: str | Path) -> dict[str, dict[str, str]]:
    rows = load_csv_rows(path)
    return {row["user_id"]: row for row in rows if row.get("user_id")}


def load_evidence_requirements(path: str | Path) -> list[dict[str, str]]:
    return load_csv_rows(path)


def parse_claim_issue_type(user_claim: str) -> str:
    text = user_claim.lower()
    for issue_type, keywords in ISSUE_TYPE_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return issue_type
    if "no damage" in text or "not damaged" in text:
        return "none"
    return "unknown"


def parse_object_part(claim_object: str, user_claim: str) -> str:
    object_keywords = OBJECT_PART_KEYWORDS.get(claim_object.lower(), {})
    text = user_claim.lower()
    for object_part, keywords in object_keywords.items():
        if any(keyword in text for keyword in keywords):
            return object_part
    return "unknown"


def derive_issue_family(issue_type: str) -> str:
    issue_type = issue_type.lower()
    if issue_type in {"dent", "scratch"}:
        return "dent or scratch"
    if issue_type in {"crack", "glass_shatter"}:
        return "crack or shattered glass"
    if issue_type in {"torn_packaging", "crushed_packaging"}:
        return "package damage"
    if issue_type in {"broken_part", "missing_part"}:
        return "broken or missing part"
    if issue_type == "water_damage":
        return "water damage"
    if issue_type == "stain":
        return "stain"
    return "general"


def filter_relevant_requirements(
    requirements: list[dict[str, str]],
    *,
    claim_object: str,
    issue_type: str,
    object_part: str,
    claim_text: str,
) -> list[dict[str, str]]:
    family = derive_issue_family(issue_type)
    query_tokens = set(
        tokenize(f"{claim_object} {issue_type} {object_part} {claim_text}")
    )

    scored: list[tuple[int, dict[str, str]]] = []
    for row in requirements:
        applies_object = row.get("claim_object", "").strip().lower()
        if applies_object not in {"all", claim_object.lower()}:
            continue
        requirement_text = collapse_whitespace(
            f"{row.get('applies_to', '')} {row.get('minimum_image_evidence', '')}"
        )
        score = 0
        lowered_requirement = requirement_text.lower()
        if family != "general" and family in lowered_requirement:
            score += 5
        score += len(query_tokens & set(tokenize(requirement_text)))
        scored.append((score, row))

    scored.sort(key=lambda item: (-item[0], item[1].get("requirement_id", "")))
    return [row for score, row in scored if score > 0][:5]


def normalize_risk_flags(raw_flags: str | list[str]) -> str:
    if isinstance(raw_flags, str):
        parts = [part.strip() for part in raw_flags.split(";") if part.strip()]
    else:
        parts = [str(part).strip() for part in raw_flags if str(part).strip()]
    unique = sorted({part for part in parts if part and part.lower() != "none"})
    return ";".join(unique) if unique else "none"


def supporting_image_ids(raw_value: str) -> str:
    image_ids = sorted(
        dict.fromkeys(Path(path).stem for path in split_image_paths(raw_value))
    )
    return ";".join(image_ids) if image_ids else "none"


def history_risk_flags(history_row: dict[str, str] | None) -> list[str]:
    if not history_row:
        return []

    flags: list[str] = []
    try:
        past_claim_count = int(history_row.get("past_claim_count", "0") or "0")
        recent_claim_count = int(
            history_row.get("last_90_days_claim_count", "0") or "0"
        )
        manual_review_claim = int(history_row.get("manual_review_claim", "0") or "0")
        rejected_claim = int(history_row.get("rejected_claim", "0") or "0")
    except ValueError:
        past_claim_count = 0
        recent_claim_count = 0
        manual_review_claim = 0
        rejected_claim = 0

    if (
        past_claim_count >= 6
        or recent_claim_count >= 3
        or manual_review_claim >= 2
        or rejected_claim >= 2
    ):
        flags.append("user_history_risk")
    if history_row.get("history_flags"):
        flags.append("manual_review_required")
    return sorted(dict.fromkeys(flags))
