from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .utils import ensure_directory, slugify, stable_json


def create_run_dir(root: Path, name: str) -> Path:
    ensure_directory(root)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    base_name = f"{stamp}-{slugify(name)}"
    candidate = root / base_name
    suffix = 1
    while candidate.exists():
        candidate = root / f"{base_name}-{suffix:02d}"
        suffix += 1
    candidate.mkdir(parents=True, exist_ok=False)
    return candidate


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(data), encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            handle.write("\n")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def render_run_transcript(contract_name: str, records: list[dict[str, object]]) -> str:
    lines = [f"# Run Transcript — {contract_name}", ""]
    for record in records:
        lines.append(f"## Row {record['row_number']} — {record['row_id']}")
        lines.append("")
        lines.append(f"- Query: {record['query']}")
        lines.append(f"- Status: {record['status']}")
        lines.append(f"- Product Area: {record['product_area']}")
        lines.append(f"- Request Type: {record['request_type']}")
        lines.append(f"- Top Sources: {', '.join(record['top_sources']) or 'none'}")
        reasons = record.get("reasons", [])
        if reasons:
            lines.append(f"- Escalation Reasons: {', '.join(reasons)}")
        lines.append(f"- Response: {record['response']}")
        lines.append(f"- Justification: {record['justification']}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"
