from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

from .utils import collapse_whitespace

DEFAULT_SET_COLUMNS = {"risk_flags", "supporting_image_ids"}
DEFAULT_IDENTITY_COLUMNS = ["user_id", "image_paths", "user_claim", "claim_object"]


def _read_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _normalize_scalar(value: object) -> str:
    return collapse_whitespace(str(value)).lower()


def _normalize_set_field(value: object) -> tuple[str, ...]:
    parts = [
        part.strip().lower()
        for part in str(value).split(";")
        if part.strip() and part.strip().lower() != "none"
    ]
    return tuple(sorted(set(parts)))


def evaluate_claim_review_csv(
    expected_path: str | Path,
    predicted_path: str | Path,
    *,
    set_columns: Iterable[str] | None = None,
    identity_columns: Iterable[str] | None = None,
) -> dict[str, object]:
    expected_rows = _read_rows(expected_path)
    predicted_rows = _read_rows(predicted_path)
    set_columns_normalized = {
        column.strip() for column in (set_columns or DEFAULT_SET_COLUMNS)
    }
    identity = [
        column.strip() for column in (identity_columns or DEFAULT_IDENTITY_COLUMNS)
    ]

    fields = list(expected_rows[0].keys()) if expected_rows else []
    compared_rows = min(len(expected_rows), len(predicted_rows))
    exact_matches = {field: 0 for field in fields}
    normalized_matches = {field: 0 for field in fields}
    row_identity_mismatches: list[int] = []

    for index in range(compared_rows):
        expected = expected_rows[index]
        predicted = predicted_rows[index]

        if identity and any(
            expected.get(column, "") != predicted.get(column, "")
            for column in identity
            if column in expected
        ):
            row_identity_mismatches.append(index + 1)

        for field in fields:
            expected_value = expected.get(field, "")
            predicted_value = predicted.get(field, "")
            if expected_value == predicted_value:
                exact_matches[field] += 1

            if field in set_columns_normalized:
                if _normalize_set_field(expected_value) == _normalize_set_field(
                    predicted_value
                ):
                    normalized_matches[field] += 1
            elif _normalize_scalar(expected_value) == _normalize_scalar(
                predicted_value
            ):
                normalized_matches[field] += 1

    denominator = max(compared_rows, 1)
    normalized_accuracy = {
        field: round(count / denominator, 4)
        for field, count in normalized_matches.items()
    }
    exact_accuracy = {
        field: round(count / denominator, 4) for field, count in exact_matches.items()
    }

    return {
        "expected_rows": len(expected_rows),
        "predicted_rows": len(predicted_rows),
        "compared_rows": compared_rows,
        "row_count_match": len(expected_rows) == len(predicted_rows),
        "row_identity_mismatches": row_identity_mismatches,
        "set_columns": sorted(set_columns_normalized),
        "exact_matches": exact_matches,
        "normalized_matches": normalized_matches,
        "exact_accuracy": exact_accuracy,
        "normalized_accuracy": normalized_accuracy,
        "overall_normalized_accuracy": round(
            sum(normalized_matches.values()) / max(len(fields) * denominator, 1),
            4,
        ),
    }
