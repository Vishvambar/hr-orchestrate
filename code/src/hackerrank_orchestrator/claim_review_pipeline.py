from __future__ import annotations

import csv
import json
import os
import shutil
import time
from pathlib import Path
from typing import Any

from .artifacts import create_run_dir, write_json, write_jsonl, write_text
from .claim_review_config import ClaimReviewConfig, load_claim_review_config
from .contracts import RunSummary
from .image_utils import image_ids_from_raw, split_image_paths
from .multimodal_evaluation import evaluate_claim_review_csv
from .multimodal_helpers import (
    filter_relevant_requirements,
    history_risk_flags,
    load_evidence_requirements,
    load_user_history_map,
    normalize_risk_flags,
    parse_claim_issue_type,
    parse_object_part,
)
from .prompts import read_prompt
from .utils import (
    ensure_directory,
    iso_utc_now,
    load_env_file,
    project_root,
    resolve_path,
    sha256_file,
    sha256_text,
    stable_json,
)

OBJECT_PARTS_BY_OBJECT = {
    "car": {
        "front_bumper",
        "rear_bumper",
        "door",
        "hood",
        "windshield",
        "side_mirror",
        "headlight",
        "taillight",
        "fender",
        "quarter_panel",
        "body",
        "unknown",
    },
    "laptop": {
        "screen",
        "keyboard",
        "trackpad",
        "hinge",
        "lid",
        "corner",
        "port",
        "base",
        "body",
        "unknown",
    },
    "package": {
        "box",
        "package_corner",
        "package_side",
        "seal",
        "label",
        "contents",
        "item",
        "unknown",
    },
}


def _read_input_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_output_csv(
    path: Path, rows: list[dict[str, str]], header: list[str]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)


def _load_resume_rows(
    *,
    path: Path,
    input_rows: list[dict[str, str]],
    header: list[str],
    identity_columns: list[str],
) -> list[dict[str, str]]:
    if not path.exists() or not os.getenv("ORCH_RESUME_OUTPUT", "true").lower() in {
        "1",
        "true",
        "yes",
    }:
        return []
    try:
        existing_rows = _read_input_rows(path)
    except Exception:  # noqa: BLE001
        return []
    if not existing_rows:
        return []
    if any(column not in existing_rows[0] for column in header):
        return []

    resume_rows: list[dict[str, str]] = []
    for index, existing in enumerate(existing_rows[: len(input_rows)]):
        expected_input = input_rows[index]
        identity_matches = all(
            existing.get(column, "") == expected_input.get(column, "")
            for column in identity_columns
        )
        if not identity_matches:
            break
        resume_rows.append({column: existing.get(column, "") for column in header})
    return resume_rows


def _resolve_image_paths(
    config: ClaimReviewConfig, raw_image_paths: str
) -> tuple[list[str], list[Path], list[str]]:
    root = project_root()
    base_dir = resolve_path(config.images_base_dir, root)
    relative_paths = split_image_paths(raw_image_paths)
    existing_paths: list[Path] = []
    missing_paths: list[str] = []
    for relative_path in relative_paths:
        joined = (
            (base_dir / relative_path)
            if not Path(relative_path).is_absolute()
            else Path(relative_path)
        )
        if joined.exists():
            existing_paths.append(joined)
        else:
            fallback = resolve_path(relative_path, root)
            if fallback.exists():
                existing_paths.append(fallback)
            else:
                missing_paths.append(relative_path)
    return relative_paths, existing_paths, missing_paths


def _format_requirements_text(requirements: list[dict[str, str]]) -> str:
    if not requirements:
        return "No matching requirement rows were found."
    lines = []
    for row in requirements:
        lines.append(
            f"- {row.get('requirement_id', 'unknown')}: applies_to={row.get('applies_to', '')}; minimum_image_evidence={row.get('minimum_image_evidence', '')}"
        )
    return "\n".join(lines)


def _build_review_prompt(
    config: ClaimReviewConfig,
    row: dict[str, str],
    *,
    claim_parse: dict[str, str],
    history_row: dict[str, str] | None,
    requirements: list[dict[str, str]],
    image_ids: list[str],
) -> str:
    base = project_root()
    system_prompt = read_prompt(config.prompts.system, base=base)
    review_prompt = read_prompt(config.prompts.review, base=base)
    body = review_prompt.format(
        task_summary=config.summary,
        row_json=json.dumps(row, ensure_ascii=False, sort_keys=True),
        claim_parse_json=json.dumps(claim_parse, ensure_ascii=False, sort_keys=True),
        history_json=json.dumps(history_row or {}, ensure_ascii=False, sort_keys=True),
        requirements_text=_format_requirements_text(requirements),
    )
    image_manifest = "Image IDs available for this row: " + (
        ", ".join(image_ids) if image_ids else "none"
    )
    return system_prompt + "\n\n" + image_manifest + "\n\n" + body


def _bool_string(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    lowered = str(value).strip().lower()
    return "true" if lowered in {"true", "1", "yes"} else "false"


def _normalize_allowed(value: Any, allowed_values: list[str], fallback: str) -> str:
    if not allowed_values:
        return str(value).strip() if str(value).strip() else fallback
    lowered_map = {item.lower(): item for item in allowed_values}
    candidate = str(value).strip().lower()
    if candidate in lowered_map:
        return lowered_map[candidate]
    for item in allowed_values:
        item_lower = item.lower()
        if candidate and (candidate in item_lower or item_lower in candidate):
            return item
    return fallback


def _normalize_supporting_image_ids(value: Any, available_ids: list[str]) -> str:
    if isinstance(value, list):
        candidates = [str(item).strip() for item in value]
    else:
        candidates = [part.strip() for part in str(value).split(";") if part.strip()]
    valid_ids = [
        candidate for candidate in candidates if candidate in set(available_ids)
    ]
    unique = sorted(dict.fromkeys(valid_ids))
    return ";".join(unique) if unique else "none"


def _infer_issue_type_from_text(text: str) -> str:
    lowered = text.lower()
    if "shatter" in lowered or "smashed glass" in lowered:
        return "glass_shatter"
    if "crack" in lowered:
        return "crack"
    if "scratch" in lowered or "scrape" in lowered or "scuff" in lowered:
        return "scratch"
    if "dent" in lowered or "deform" in lowered or "dented" in lowered:
        return "dent"
    if "broken" in lowered or "snapped" in lowered:
        return "broken_part"
    if "missing" in lowered or "absent" in lowered:
        return "missing_part"
    if "torn" in lowered or "tear" in lowered or "ripped" in lowered:
        return "torn_packaging"
    if "crushed" in lowered or "collapsed" in lowered:
        return "crushed_packaging"
    if "water" in lowered or "wet" in lowered or "soaked" in lowered:
        return "water_damage"
    if "stain" in lowered or "stained" in lowered:
        return "stain"
    return "unknown"


def _risk_flags_to_list(value: str) -> list[str]:
    if value == "none":
        return []
    return [part for part in value.split(";") if part and part != "none"]


def _join_risk_flags(flags: list[str]) -> str:
    unique = sorted(dict.fromkeys(flags))
    return ";".join(unique) if unique else "none"


def _claim_review_fallback(
    row: dict[str, str],
    *,
    config: ClaimReviewConfig,
    history_flags: list[str],
    parsed_issue_type: str,
    parsed_object_part: str,
    reason: str,
    valid_image: str,
) -> dict[str, str]:
    risk_flags = normalize_risk_flags(history_flags + ["manual_review_required"])
    issue_type = (
        parsed_issue_type
        if parsed_issue_type
        in {
            "dent",
            "scratch",
            "crack",
            "glass_shatter",
            "broken_part",
            "missing_part",
            "torn_packaging",
            "crushed_packaging",
            "water_damage",
            "stain",
            "none",
        }
        else "unknown"
    )
    claim_object = row.get(config.claim_object_column, "").strip().lower()
    allowed_parts = OBJECT_PARTS_BY_OBJECT.get(claim_object, {"unknown"})
    object_part = (
        parsed_object_part if parsed_object_part in allowed_parts else "unknown"
    )
    return {
        "user_id": row.get(config.user_id_column, ""),
        "image_paths": row.get(config.image_paths_column, ""),
        "user_claim": row.get(config.claim_text_column, ""),
        "claim_object": row.get(config.claim_object_column, ""),
        "evidence_standard_met": "false",
        "evidence_standard_met_reason": reason,
        "risk_flags": risk_flags,
        "issue_type": issue_type,
        "object_part": object_part,
        "claim_status": "not_enough_information",
        "claim_status_justification": reason,
        "supporting_image_ids": "none",
        "valid_image": valid_image,
        "severity": "unknown",
    }


def _normalize_claim_review_output(
    model_output: dict[str, Any],
    row: dict[str, str],
    *,
    config: ClaimReviewConfig,
    available_image_ids: list[str],
    history_flags: list[str],
    parsed_issue_type: str,
    parsed_object_part: str,
    provider_error: str | None = None,
    missing_paths: list[str] | None = None,
) -> dict[str, str]:
    missing_paths = missing_paths or []
    claim_text = row.get(config.claim_text_column, "")
    claim_object = row.get(config.claim_object_column, "").strip().lower()
    allowed_issue_types = (
        config.find_field("issue_type").allowed_values
        if config.find_field("issue_type")
        else []
    )
    allowed_claim_status = (
        config.find_field("claim_status").allowed_values
        if config.find_field("claim_status")
        else []
    )
    allowed_severity = (
        config.find_field("severity").allowed_values
        if config.find_field("severity")
        else []
    )
    allowed_parts = OBJECT_PARTS_BY_OBJECT.get(claim_object, {"unknown"})

    risk_flags_raw = model_output.get("risk_flags", [])
    if provider_error:
        if isinstance(risk_flags_raw, list):
            risk_flags_raw.append("manual_review_required")
        else:
            risk_flags_raw = str(risk_flags_raw) + ";manual_review_required"
    if missing_paths:
        if isinstance(risk_flags_raw, list):
            risk_flags_raw.append("manual_review_required")
        else:
            risk_flags_raw = str(risk_flags_raw) + ";manual_review_required"
    risk_flags = normalize_risk_flags(
        list(history_flags)
        + (
            [risk_flags_raw]
            if isinstance(risk_flags_raw, str)
            else list(risk_flags_raw)
        )
    )

    valid_image = _bool_string(
        model_output.get("valid_image", "false" if missing_paths else True)
    )
    supporting_ids = _normalize_supporting_image_ids(
        model_output.get("supporting_image_ids", []),
        available_image_ids,
    )
    evidence_standard_met = _bool_string(
        model_output.get(
            "evidence_standard_met", valid_image == "true" and supporting_ids != "none"
        )
    )
    issue_type = _normalize_allowed(
        model_output.get("issue_type", parsed_issue_type),
        allowed_issue_types,
        parsed_issue_type if parsed_issue_type in allowed_issue_types else "unknown",
    )
    object_part = (
        str(model_output.get("object_part", parsed_object_part)).strip().lower()
    )
    if object_part not in allowed_parts:
        object_part = (
            parsed_object_part if parsed_object_part in allowed_parts else "unknown"
        )
    claim_status = _normalize_allowed(
        model_output.get("claim_status", "not_enough_information"),
        allowed_claim_status,
        "not_enough_information",
    )
    severity = _normalize_allowed(
        model_output.get("severity", "unknown"),
        allowed_severity,
        "unknown",
    )

    if valid_image == "false":
        evidence_standard_met = "false"
        claim_status = "not_enough_information"
        supporting_ids = "none"
        severity = "unknown" if severity == "none" else severity
    if evidence_standard_met == "false":
        claim_status = "not_enough_information"
    if (
        config.rules.require_explicit_supporting_image_ids
        and claim_status in {"supported", "contradicted"}
        and supporting_ids == "none"
    ):
        evidence_standard_met = "false"
        claim_status = "not_enough_information"
        risk_flags = normalize_risk_flags([risk_flags, "manual_review_required"])

    evidence_reason = str(model_output.get("evidence_standard_met_reason", "")).strip()
    if not evidence_reason:
        evidence_reason = (
            "The submitted images are sufficient to evaluate the claim."
            if evidence_standard_met == "true"
            else "The submitted images do not provide enough clear evidence to evaluate the claim."
        )
    justification = str(model_output.get("claim_status_justification", "")).strip()
    if not justification:
        justification = evidence_reason

    combined_text = " ".join([claim_text, evidence_reason, justification])
    inferred_visible_issue = _infer_issue_type_from_text(combined_text)
    if inferred_visible_issue != "unknown":
        issue_mentions = {
            "dent": ["dent", "deform", "dented"],
            "scratch": ["scratch", "scrape", "scuff"],
            "crack": ["crack"],
            "glass_shatter": ["shatter", "smashed glass"],
            "broken_part": ["broken", "snapped"],
            "missing_part": ["missing", "absent"],
            "torn_packaging": ["torn", "tear", "ripped"],
            "crushed_packaging": ["crushed", "collapsed"],
            "water_damage": ["water", "wet", "soaked"],
            "stain": ["stain", "stained"],
        }
        visible_words = issue_mentions.get(issue_type, [])
        if issue_type in {"unknown", "none"} or not any(
            word in combined_text.lower() for word in visible_words
        ):
            issue_type = inferred_visible_issue

    if claim_status == "supported" and severity in {"none", "unknown"}:
        lowered = combined_text.lower()
        severity = (
            "medium"
            if any(word in lowered for word in ["deep", "shatter", "crushed", "broken"])
            else "low"
        )

    risk_list = _risk_flags_to_list(risk_flags)
    high_review_risks = {
        "possible_manipulation",
        "non_original_image",
        "text_instruction_present",
        "wrong_object",
        "wrong_object_part",
        "claim_mismatch",
    }
    if (
        "manual_review_required" in risk_list
        and claim_status in {"supported", "contradicted"}
        and evidence_standard_met == "true"
        and valid_image == "true"
        and not high_review_risks.intersection(risk_list)
    ):
        risk_list = [flag for flag in risk_list if flag != "manual_review_required"]
        risk_flags = _join_risk_flags(risk_list)

    return {
        "user_id": row.get(config.user_id_column, ""),
        "image_paths": row.get(config.image_paths_column, ""),
        "user_claim": row.get(config.claim_text_column, ""),
        "claim_object": row.get(config.claim_object_column, ""),
        "evidence_standard_met": evidence_standard_met,
        "evidence_standard_met_reason": evidence_reason,
        "risk_flags": risk_flags,
        "issue_type": issue_type,
        "object_part": object_part,
        "claim_status": claim_status,
        "claim_status_justification": justification,
        "supporting_image_ids": supporting_ids,
        "valid_image": valid_image,
        "severity": severity,
    }


def _render_claim_review_transcript(
    contract_name: str, rows: list[dict[str, Any]]
) -> str:
    lines = [f"# Run Transcript — {contract_name}", ""]
    for row in rows:
        lines.append(f"## Row {row['row_number']} — {row['row_key']}")
        lines.append("")
        lines.append(f"- Claim object: {row['claim_object']}")
        lines.append(f"- Parsed issue guess: {row['parsed_issue_type']}")
        lines.append(f"- Parsed object part guess: {row['parsed_object_part']}")
        lines.append(f"- Image IDs: {row['image_ids']}")
        lines.append(f"- Provider used: {row['provider']}")
        lines.append(f"- Model used: {row['model']}")
        lines.append(f"- Claim status: {row['claim_status']}")
        lines.append(f"- Risk flags: {row['risk_flags']}")
        lines.append(f"- Justification: {row['claim_status_justification']}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _estimate_tokens_from_text(text: str) -> int:
    return max(1, len(text) // 4)


def _display_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _update_evaluation_report(
    *,
    root: Path,
    config: ClaimReviewConfig,
    rows_processed: int,
    image_count: int,
    stats: dict[str, Any],
    evaluation: dict[str, Any] | None,
    runtime_seconds: float,
) -> None:
    report_lines = [
        "# Evaluation Report — Multi-Modal Evidence Review",
        "",
        "Auto-generated summary from the latest run. Update manually if you want more narrative detail before submission.",
        "",
        "## 1. System summary",
        "",
        f"- Primary provider actually used: {stats.get('primary_provider', 'unknown')}",
        f"- Successful providers: {', '.join(stats.get('successful_providers', [])) or 'none'}",
        "- Images as primary evidence: yes",
        "- User history used only for risk context: yes",
        "- Evidence requirements used in decisioning: yes",
        "",
        "## 2. Evaluation data",
        "",
        f"- Sample CSV path: {config.expected_csv or 'not configured'}",
        f"- Number of rows processed in this run: {rows_processed}",
        f"- Number of images processed in this run: {image_count}",
        f"- Any rows without usable images: {stats.get('rows_without_usable_images', 0)}",
        "",
        "## 3. Field-level quality",
        "",
    ]
    if evaluation:
        report_lines.append("| Field | Exact Accuracy | Normalized Accuracy |")
        report_lines.append("| --- | --- | --- |")
        for field in sorted(evaluation.get("normalized_accuracy", {}).keys()):
            report_lines.append(
                f"| `{field}` | {evaluation.get('exact_accuracy', {}).get(field, '')} | {evaluation.get('normalized_accuracy', {}).get(field, '')} |"
            )
    else:
        report_lines.append("No labeled sample evaluation was available for this run.")
    report_lines.extend(
        [
            "",
            "## 4. Operational analysis",
            "",
            f"- Approximate number of model calls for sample + test processing in this run: {stats.get('provider_calls_total', 0)}",
            f"- Approximate input tokens observed or estimated: {stats.get('prompt_tokens_total', 0)}",
            f"- Approximate output tokens observed or estimated: {stats.get('completion_tokens_total', 0)}",
            f"- Number of images processed: {image_count}",
            f"- Approximate runtime: {round(runtime_seconds, 2)} seconds",
            f"- Provider attempts by name: {stable_json(stats.get('provider_attempts', {}))}",
            "- Pricing assumptions: fill in with your chosen provider's current pricing before final submission.",
            "- TPM/RPM considerations: sequential failover with per-row delay and bounded retries.",
            "- Batching / throttling / caching / retry strategy: one multimodal review call per row, sequential provider failover, bounded cooldown and conservative fallback.",
            "",
            "## 5. Final decision notes",
            "",
            "- Why this architecture was chosen: image-first prompt with deterministic post-processing and provider failover.",
            "- What tradeoff was intentionally made: reliability and schema control were prioritized over aggressive parallelism.",
            "- What would be improved with more time: task-specific image adjudication and richer per-field calibration.",
            "",
        ]
    )
    write_text(root / "evaluation" / "evaluation_report.md", "\n".join(report_lines))


def run_claim_review(
    contract_path: str | Path,
    *,
    max_rows: int | None = None,
) -> RunSummary:
    from .vision_failover import VisionProviderError, make_sequential_vision_router

    root = project_root()
    load_env_file(root / ".env")
    contract_file = resolve_path(contract_path, root)
    config = load_claim_review_config(contract_file, base=root)

    input_rows = _read_input_rows(resolve_path(config.input_csv, root))
    if max_rows is not None:
        input_rows = input_rows[:max_rows]

    history_map = load_user_history_map(resolve_path(config.user_history_csv, root))
    requirements = load_evidence_requirements(
        resolve_path(config.evidence_requirements_csv, root)
    )
    router = make_sequential_vision_router(max_tokens=config.vision.max_tokens)

    started = time.perf_counter()
    run_dir = create_run_dir(root / "artifacts" / "runs", config.name)
    output_path = run_dir / "output.csv"
    resume_source = (
        resolve_path(config.output_csv, root) if config.output_csv else output_path
    )
    output_rows: list[dict[str, str]] = _load_resume_rows(
        path=resume_source,
        input_rows=input_rows,
        header=config.output_header(),
        identity_columns=config.identity_columns,
    )
    if output_rows:
        _write_output_csv(output_path, output_rows, config.output_header())
        if config.output_csv:
            mirrored_output = resolve_path(config.output_csv, root)
            ensure_directory(mirrored_output.parent)
            shutil.copyfile(output_path, mirrored_output)
        print(
            f"[claim-review] resumed {len(output_rows)}/{len(input_rows)} rows from {resume_source}",
            flush=True,
        )
    review_rows: list[dict[str, Any]] = []
    transcript_rows: list[dict[str, Any]] = []

    stats: dict[str, Any] = {
        "provider_calls_total": 0,
        "provider_attempts": {},
        "successful_providers": [],
        "prompt_tokens_total": 0,
        "completion_tokens_total": 0,
        "rows_without_usable_images": 0,
    }
    image_count = 0
    row_delay_seconds = float(os.getenv("ORCH_ROW_DELAY_SECONDS", "3"))

    for row_number, row in enumerate(
        input_rows[len(output_rows) :], start=len(output_rows) + 1
    ):
        user_id = row.get(config.user_id_column, "")
        raw_image_paths = row.get(config.image_paths_column, "")
        relative_paths, image_paths, missing_paths = _resolve_image_paths(
            config, raw_image_paths
        )
        image_ids = image_ids_from_raw(raw_image_paths)
        image_count += len(relative_paths)
        history_row = history_map.get(user_id)
        history_flags = history_risk_flags(history_row)
        claim_text = row.get(config.claim_text_column, "")
        claim_object = row.get(config.claim_object_column, "")
        parsed_issue_type = parse_claim_issue_type(claim_text)
        parsed_object_part = parse_object_part(claim_object, claim_text)
        relevant_requirements = filter_relevant_requirements(
            requirements,
            claim_object=claim_object,
            issue_type=parsed_issue_type,
            object_part=parsed_object_part,
            claim_text=claim_text,
        )
        claim_parse = {
            "issue_type_guess": parsed_issue_type,
            "object_part_guess": parsed_object_part,
            "image_ids": image_ids,
        }

        if not image_paths:
            stats["rows_without_usable_images"] += 1
            output_row = _claim_review_fallback(
                row,
                config=config,
                history_flags=history_flags,
                parsed_issue_type=parsed_issue_type,
                parsed_object_part=parsed_object_part,
                reason="No readable images were available for automated review.",
                valid_image="false",
            )
            provider_name = "none"
            model_name = "none"
            attempt_data: list[dict[str, Any]] = []
        else:
            prompt_text = _build_review_prompt(
                config,
                row,
                claim_parse=claim_parse,
                history_row=history_row,
                requirements=relevant_requirements,
                image_ids=image_ids,
            )
            try:
                result = router.review(prompt_text, image_paths)
                provider_name = result.provider
                model_name = result.model
                stats["provider_calls_total"] += len(result.attempts)
                for attempt in result.attempts:
                    stats["provider_attempts"].setdefault(attempt.provider, 0)
                    stats["provider_attempts"][attempt.provider] += 1
                if provider_name not in stats["successful_providers"]:
                    stats["successful_providers"].append(provider_name)
                stats["prompt_tokens_total"] += (
                    result.prompt_tokens or _estimate_tokens_from_text(prompt_text)
                )
                stats["completion_tokens_total"] += (
                    result.completion_tokens
                    or _estimate_tokens_from_text(result.raw_text)
                )
                output_row = _normalize_claim_review_output(
                    result.parsed,
                    row,
                    config=config,
                    available_image_ids=image_ids,
                    history_flags=history_flags,
                    parsed_issue_type=parsed_issue_type,
                    parsed_object_part=parsed_object_part,
                    missing_paths=missing_paths,
                )
                attempt_data = result.to_dict()["attempts"]
            except VisionProviderError as exc:
                provider_name = "failover_error"
                model_name = "none"
                stats["rows_without_usable_images"] += 1
                output_row = _claim_review_fallback(
                    row,
                    config=config,
                    history_flags=history_flags,
                    parsed_issue_type=parsed_issue_type,
                    parsed_object_part=parsed_object_part,
                    reason=f"Vision review failed after sequential provider fallback: {exc}",
                    valid_image="false",
                )
                attempt_data = router.last_attempts_as_dicts()
                stats["provider_calls_total"] += len(attempt_data)
                for attempt in attempt_data:
                    stats["provider_attempts"].setdefault(attempt["provider"], 0)
                    stats["provider_attempts"][attempt["provider"]] += 1

        output_rows.append(output_row)
        _write_output_csv(output_path, output_rows, config.output_header())
        if config.output_csv:
            mirrored_output = resolve_path(config.output_csv, root)
            ensure_directory(mirrored_output.parent)
            shutil.copyfile(output_path, mirrored_output)
        print(
            f"[claim-review] row {row_number}/{len(input_rows)} "
            f"provider={provider_name} model={model_name} "
            f"status={output_row.get('claim_status', '')}",
            flush=True,
        )
        review_rows.append(
            {
                "row_number": row_number,
                "row_key": user_id or str(row_number),
                "provider": provider_name,
                "model": model_name,
                "image_ids": image_ids,
                "missing_paths": missing_paths,
                "parsed_issue_type": parsed_issue_type,
                "parsed_object_part": parsed_object_part,
                "requirements": relevant_requirements,
                "output": output_row,
                "attempts": attempt_data,
            }
        )
        transcript_rows.append(
            {
                "row_number": row_number,
                "row_key": user_id or str(row_number),
                "claim_object": claim_object,
                "parsed_issue_type": parsed_issue_type,
                "parsed_object_part": parsed_object_part,
                "image_ids": ";".join(image_ids) or "none",
                "provider": provider_name,
                "model": model_name,
                "claim_status": output_row.get("claim_status", ""),
                "risk_flags": output_row.get("risk_flags", ""),
                "claim_status_justification": output_row.get(
                    "claim_status_justification", ""
                ),
            }
        )

        if row_delay_seconds > 0 and row_number < len(input_rows):
            time.sleep(row_delay_seconds)

    _write_output_csv(output_path, output_rows, config.output_header())
    if config.output_csv:
        mirrored_output = resolve_path(config.output_csv, root)
        ensure_directory(mirrored_output.parent)
        shutil.copyfile(output_path, mirrored_output)

    prompt_hashes = {
        "system": sha256_file(resolve_path(config.prompts.system, root)),
        "review": sha256_file(resolve_path(config.prompts.review, root)),
    }
    if config.prompts.verify:
        prompt_hashes["verify"] = sha256_file(resolve_path(config.prompts.verify, root))

    manifest = {
        "run_timestamp_utc": iso_utc_now(),
        "contract_name": config.name,
        "contract_path": _display_path(contract_file, root),
        "rows_processed": len(output_rows),
        "images_processed": image_count,
        "output_csv": _display_path(output_path, root),
        "provider_stats": stats,
        "contract_hash": sha256_text(stable_json(config.to_dict())),
        "prompt_hashes": prompt_hashes,
    }
    if stats["successful_providers"]:
        manifest["primary_provider"] = stats["successful_providers"][0]

    write_json(run_dir / "manifest.json", manifest)
    write_jsonl(run_dir / "claim_reviews.jsonl", review_rows)
    write_text(
        run_dir / "run_transcript.md",
        _render_claim_review_transcript(config.name, transcript_rows),
    )
    write_text(
        run_dir / "resolved_contract.toml", contract_file.read_text(encoding="utf-8")
    )

    evaluation_path: Path | None = None
    evaluation: dict[str, Any] | None = None
    if config.expected_csv:
        expected_path = resolve_path(config.expected_csv, root)
        if expected_path.exists():
            evaluation = evaluate_claim_review_csv(
                expected_path,
                output_path,
                set_columns=config.set_columns,
                identity_columns=config.identity_columns,
            )
            evaluation_path = run_dir / "evaluation.json"
            write_json(evaluation_path, evaluation)

    runtime_seconds = time.perf_counter() - started
    if stats["successful_providers"]:
        stats["primary_provider"] = stats["successful_providers"][0]
    _update_evaluation_report(
        root=root,
        config=config,
        rows_processed=len(output_rows),
        image_count=image_count,
        stats=stats,
        evaluation=evaluation,
        runtime_seconds=runtime_seconds,
    )

    return RunSummary(
        run_dir=_display_path(run_dir, root),
        output_csv=_display_path(output_path, root),
        rows_processed=len(output_rows),
        provider="vision_failover",
        model=stats.get("primary_provider", "dynamic"),
        evaluation_path=_display_path(evaluation_path, root)
        if evaluation_path
        else None,
    )
