from __future__ import annotations

import csv
from pathlib import Path

from .utils import collapse_whitespace


def _normalize(value: str) -> str:
    return collapse_whitespace(value).lower()


def _read_rows(path: str | Path, id_column: str) -> dict[str, dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return {row[id_column]: row for row in reader}


def evaluate_csv(
    expected_path: str | Path, predicted_path: str | Path, *, id_column: str
) -> dict[str, object]:
    expected_rows = _read_rows(expected_path, id_column)
    predicted_rows = _read_rows(predicted_path, id_column)

    fields = (
        [
            field
            for field in next(iter(expected_rows.values())).keys()
            if field != id_column
        ]
        if expected_rows
        else []
    )
    exact_matches = {field: 0 for field in fields}
    normalized_matches = {field: 0 for field in fields}
    missing_ids = sorted(set(expected_rows) - set(predicted_rows))
    extra_ids = sorted(set(predicted_rows) - set(expected_rows))

    compared_rows = 0
    for row_id, expected in expected_rows.items():
        predicted = predicted_rows.get(row_id)
        if predicted is None:
            continue
        compared_rows += 1
        for field in fields:
            expected_value = expected.get(field, "")
            predicted_value = predicted.get(field, "")
            if expected_value == predicted_value:
                exact_matches[field] += 1
            if _normalize(expected_value) == _normalize(predicted_value):
                normalized_matches[field] += 1

    denominator = max(compared_rows, 1)
    normalized_accuracy = {
        field: round(count / denominator, 4)
        for field, count in normalized_matches.items()
    }

    return {
        "compared_rows": compared_rows,
        "missing_ids": missing_ids,
        "extra_ids": extra_ids,
        "exact_matches": exact_matches,
        "normalized_matches": normalized_matches,
        "normalized_accuracy": normalized_accuracy,
        "overall_normalized_accuracy": round(
            sum(normalized_matches.values()) / max(len(fields) * denominator, 1),
            4,
        ),
    }
