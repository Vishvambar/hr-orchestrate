from __future__ import annotations

import json
from pathlib import Path

from .contracts import ChallengeContract, RetrievalHit
from .utils import resolve_path


def read_prompt(path_like: str, *, base: Path) -> str:
    return resolve_path(path_like, base).read_text(encoding="utf-8")


def build_output_schema(contract: ChallengeContract) -> str:
    lines: list[str] = []
    for field in contract.output_fields:
        allowed = f" Allowed values: {', '.join(field.allowed_values)}." if field.allowed_values else ""
        lines.append(f"- {field.name}: {field.description}.{allowed}")
    return "\n".join(lines)


def build_evidence_block(hits: list[RetrievalHit]) -> str:
    if not hits:
        return "No evidence found."
    sections: list[str] = []
    for index, hit in enumerate(hits, start=1):
        sections.append(
            f"[{index}] score={hit.score} source={hit.source_path}\n{hit.text}"
        )
    return "\n\n".join(sections)


def build_messages(
    contract: ChallengeContract,
    row: dict[str, str],
    query: str,
    hits: list[RetrievalHit],
    *,
    base: Path,
) -> tuple[str, str]:
    system_prompt = read_prompt(contract.prompts.system, base=base)
    solve_prompt = read_prompt(contract.prompts.solve, base=base)
    user_prompt = solve_prompt.format(
        contract_summary=contract.summary,
        output_schema=build_output_schema(contract),
        row_json=json.dumps(row, ensure_ascii=False, sort_keys=True),
        query=query,
        evidence_block=build_evidence_block(hits),
        output_field_names=json.dumps(contract.field_names()),
    )
    return system_prompt, user_prompt
