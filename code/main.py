from __future__ import annotations

import argparse
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

CODE_ROOT = Path(__file__).resolve().parent
SRC_ROOT = CODE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from hackerrank_orchestrator.claim_review_pipeline import run_claim_review
from hackerrank_orchestrator.utils import stable_json


def _find_dataset_dir() -> Path:
    candidates = [
        CODE_ROOT.parent / "dataset",
        CODE_ROOT / "dataset",
        CODE_ROOT.parent / "challenge" / "current" / "dataset",
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            return candidate
    raise FileNotFoundError(
        "Could not find dataset directory. Expected one of: ../dataset, code/dataset, or ../challenge/current/dataset"
    )


def _pick_existing(path_candidates: list[Path]) -> Path:
    for candidate in path_candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    raise FileNotFoundError(
        "None of the expected files were found: "
        + ", ".join(str(candidate) for candidate in path_candidates)
    )


def _default_contract_text(dataset_dir: Path, output_path: Path) -> str:
    sample_csv = _pick_existing(
        [
            dataset_dir / "sample_claims.csv",
            dataset_dir / "sample.csv",
        ]
    )
    test_csv = _pick_existing(
        [
            dataset_dir / "test.csv",
            dataset_dir / "claims.csv",
        ]
    )
    user_history_csv = _pick_existing(
        [
            dataset_dir / "user_history.csv",
        ]
    )
    requirements_csv = _pick_existing(
        [
            dataset_dir / "evidence_requirements.csv",
        ]
    )

    # The CSVs contain paths like "images/test/case_001/img_1.jpg";
    # those are relative to dataset_dir itself, so images_base_dir = dataset_dir.
    images_base_dir = dataset_dir

    def _rel(p: Path) -> str:
        try:
            return str(p.relative_to(CODE_ROOT.parent))
        except ValueError:
            return str(p)

    return f"""name = "multi_modal_evidence_review"
summary = "Verify damage claims using images as the primary source of truth, plus user conversation, user history, and minimum evidence requirements."
input_csv = "../{_rel(test_csv)}"
expected_csv = "../{_rel(sample_csv)}"
output_csv = "../{_rel(output_path)}"
user_history_csv = "../{_rel(user_history_csv)}"
evidence_requirements_csv = "../{_rel(requirements_csv)}"
images_base_dir = "../{_rel(images_base_dir)}"
image_paths_column = "image_paths"
claim_text_column = "user_claim"
claim_object_column = "claim_object"
user_id_column = "user_id"
identity_columns = ["user_id", "image_paths", "user_claim", "claim_object"]
set_columns = ["risk_flags", "supporting_image_ids"]

[prompts]
system = "configs/prompts/multimodal_system.md"
review = "configs/prompts/multimodal_review.md"
verify = "configs/prompts/multimodal_verify.md"

[vision]
max_images_per_row = 6
max_tokens = 1200
image_detail = "auto"

[rules]
history_claim_count_risk_threshold = 6
history_last_90_days_risk_threshold = 3
require_explicit_supporting_image_ids = true

[[output_fields]]
name = "user_id"
description = "Passthrough user identifier"
required = true
allowed_values = []

[[output_fields]]
name = "image_paths"
description = "Passthrough image path list"
required = true
allowed_values = []

[[output_fields]]
name = "user_claim"
description = "Passthrough conversation transcript"
required = true
allowed_values = []

[[output_fields]]
name = "claim_object"
description = "Passthrough claim object"
required = true
allowed_values = ["car", "laptop", "package"]

[[output_fields]]
name = "evidence_standard_met"
description = "Whether the image set is sufficient to evaluate the claim"
required = true
allowed_values = ["true", "false"]

[[output_fields]]
name = "evidence_standard_met_reason"
description = "Short reason for the evidence decision"
required = true
allowed_values = []

[[output_fields]]
name = "risk_flags"
description = "Semicolon-separated risk flags or none"
required = true
allowed_values = ["none", "blurry_image", "cropped_or_obstructed", "low_light_or_glare", "wrong_angle", "wrong_object", "wrong_object_part", "damage_not_visible", "claim_mismatch", "possible_manipulation", "non_original_image", "text_instruction_present", "user_history_risk", "manual_review_required"]

[[output_fields]]
name = "issue_type"
description = "Visible issue type"
required = true
allowed_values = ["dent", "scratch", "crack", "glass_shatter", "broken_part", "missing_part", "torn_packaging", "crushed_packaging", "water_damage", "stain", "none", "unknown"]

[[output_fields]]
name = "object_part"
description = "Relevant object part"
required = true
allowed_values = ["front_bumper", "rear_bumper", "door", "hood", "windshield", "side_mirror", "headlight", "taillight", "fender", "quarter_panel", "body", "screen", "keyboard", "trackpad", "hinge", "lid", "corner", "port", "base", "box", "package_corner", "package_side", "seal", "label", "contents", "item", "unknown"]

[[output_fields]]
name = "claim_status"
description = "Final decision"
required = true
allowed_values = ["supported", "contradicted", "not_enough_information"]

[[output_fields]]
name = "claim_status_justification"
description = "Concise image-grounded explanation"
required = true
allowed_values = []

[[output_fields]]
name = "supporting_image_ids"
description = "Semicolon-separated image IDs or none"
required = true
allowed_values = []

[[output_fields]]
name = "valid_image"
description = "Whether the image set is usable for automated review"
required = true
allowed_values = ["true", "false"]

[[output_fields]]
name = "severity"
description = "Estimated severity"
required = true
allowed_values = ["none", "low", "medium", "high", "unknown"]
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the Multi-Modal Evidence Review agent from the submission-ready code/ directory."
    )
    parser.add_argument(
        "--contract", default=None, help="Optional explicit contract path"
    )
    parser.add_argument("--max-rows", type=int, default=None)
    parser.add_argument(
        "--output",
        default="output.csv",
        help="Output CSV path relative to the repo root",
    )
    args = parser.parse_args()

    if args.contract:
        contract_path = Path(args.contract)
    else:
        dataset_dir = _find_dataset_dir()
        output_path = (CODE_ROOT.parent / args.output).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        contract_text = _default_contract_text(dataset_dir, output_path)
        temp_dir = Path(tempfile.mkdtemp(prefix="orchestrate_contract_"))
        contract_path = temp_dir / "contract.toml"
        contract_path.write_text(contract_text, encoding="utf-8")

    summary = run_claim_review(contract_path, max_rows=args.max_rows)
    print(stable_json(asdict(summary)))


if __name__ == "__main__":
    main()
