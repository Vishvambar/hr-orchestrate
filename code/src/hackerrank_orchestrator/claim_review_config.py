from __future__ import annotations

import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .contracts import OutputField
from .utils import resolve_path


@dataclass(slots=True)
class MultimodalPromptPaths:
    system: str
    review: str
    verify: str = ""


@dataclass(slots=True)
class VisionSettings:
    max_images_per_row: int = 6
    max_tokens: int = 1200
    image_detail: str = "auto"


@dataclass(slots=True)
class ClaimReviewRuleSettings:
    history_claim_count_risk_threshold: int = 6
    history_last_90_days_risk_threshold: int = 3
    require_explicit_supporting_image_ids: bool = True


@dataclass(slots=True)
class ClaimReviewConfig:
    name: str
    summary: str
    input_csv: str
    expected_csv: str
    output_csv: str
    user_history_csv: str
    evidence_requirements_csv: str
    images_base_dir: str
    image_paths_column: str
    claim_text_column: str
    claim_object_column: str
    user_id_column: str
    identity_columns: list[str]
    set_columns: list[str]
    prompts: MultimodalPromptPaths
    vision: VisionSettings
    rules: ClaimReviewRuleSettings
    output_fields: list[OutputField]

    def output_header(self) -> list[str]:
        return [field.name for field in self.output_fields]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def find_field(self, name: str) -> OutputField | None:
        lowered = name.lower()
        for field in self.output_fields:
            if field.name.lower() == lowered:
                return field
        return None


REQUIRED_COLUMNS = {
    "user_id",
    "image_paths",
    "user_claim",
    "claim_object",
    "evidence_standard_met",
    "evidence_standard_met_reason",
    "risk_flags",
    "issue_type",
    "object_part",
    "claim_status",
    "claim_status_justification",
    "supporting_image_ids",
    "valid_image",
    "severity",
}


def _validate_config(config: ClaimReviewConfig) -> ClaimReviewConfig:
    header = config.output_header()
    lowered = [column.lower() for column in header]
    if len(lowered) != len(set(lowered)):
        raise ValueError("Duplicate output fields detected in claim-review config.")
    missing = [column for column in REQUIRED_COLUMNS if column not in header]
    if missing:
        raise ValueError(
            f"Missing required output fields: {', '.join(sorted(missing))}"
        )
    return config


def load_claim_review_config(
    path: str | Path,
    *,
    base: Path | None = None,
) -> ClaimReviewConfig:
    config_path = resolve_path(path, base)
    data = tomllib.loads(config_path.read_text(encoding="utf-8"))

    prompts = MultimodalPromptPaths(**data.get("prompts", {}))
    vision = VisionSettings(**data.get("vision", {}))
    rules = ClaimReviewRuleSettings(**data.get("rules", {}))
    output_fields = [OutputField(**item) for item in data.get("output_fields", [])]

    config = ClaimReviewConfig(
        name=data["name"],
        summary=data.get("summary", ""),
        input_csv=data["input_csv"],
        expected_csv=data.get("expected_csv", ""),
        output_csv=data.get("output_csv", ""),
        user_history_csv=data["user_history_csv"],
        evidence_requirements_csv=data["evidence_requirements_csv"],
        images_base_dir=data.get("images_base_dir", "."),
        image_paths_column=data.get("image_paths_column", "image_paths"),
        claim_text_column=data.get("claim_text_column", "user_claim"),
        claim_object_column=data.get("claim_object_column", "claim_object"),
        user_id_column=data.get("user_id_column", "user_id"),
        identity_columns=list(data.get("identity_columns", [])),
        set_columns=list(data.get("set_columns", [])),
        prompts=prompts,
        vision=vision,
        rules=rules,
        output_fields=output_fields,
    )
    return _validate_config(config)
