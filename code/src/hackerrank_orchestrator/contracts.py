from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
import tomllib

from .utils import resolve_path


@dataclass(slots=True)
class OutputField:
    name: str
    description: str
    required: bool = True
    allowed_values: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PromptPaths:
    system: str
    solve: str
    verify: str = ""


@dataclass(slots=True)
class RetrievalSettings:
    top_k: int = 5
    min_score: float = 0.0
    max_chunks: int = 8
    chunk_size: int = 900
    chunk_overlap: int = 120


@dataclass(slots=True)
class RuleSettings:
    escalation_keywords: list[str] = field(default_factory=list)
    min_evidence_score: float = 0.0


@dataclass(slots=True)
class ChallengeContract:
    name: str
    summary: str
    corpus_dir: str
    input_csv: str
    expected_csv: str
    output_csv: str
    id_column: str
    text_columns: list[str]
    passthrough_columns: list[str]
    prompts: PromptPaths
    retrieval: RetrievalSettings
    rules: RuleSettings
    output_fields: list[OutputField]

    def output_header(self) -> list[str]:
        header = list(self.passthrough_columns)
        for field in self.output_fields:
            if field.name not in header:
                header.append(field.name)
        return header

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def field_names(self) -> list[str]:
        return [field.name for field in self.output_fields]

    def find_field(self, name: str) -> OutputField | None:
        lowered = name.lower()
        for field in self.output_fields:
            if field.name.lower() == lowered:
                return field
        return None


@dataclass(slots=True)
class Chunk:
    chunk_id: str
    doc_id: str
    title: str
    source_path: str
    text: str


@dataclass(slots=True)
class RetrievalHit:
    chunk_id: str
    doc_id: str
    title: str
    source_path: str
    text: str
    score: float


@dataclass(slots=True)
class RunSummary:
    run_dir: str
    output_csv: str
    rows_processed: int
    provider: str
    model: str
    evaluation_path: str | None = None


def _validate_contract(contract: ChallengeContract) -> ChallengeContract:
    seen: set[str] = set()
    for name in contract.output_header():
        lowered = name.lower()
        if lowered in seen:
            raise ValueError(f"Duplicate output column detected: {name}")
        seen.add(lowered)
    if contract.id_column not in contract.passthrough_columns:
        contract.passthrough_columns.insert(0, contract.id_column)
    if not contract.text_columns:
        raise ValueError("Contract must declare at least one text column.")
    if not contract.output_fields:
        raise ValueError("Contract must declare at least one output field.")
    return contract


def load_contract(path: str | Path, *, base: Path | None = None) -> ChallengeContract:
    contract_path = resolve_path(path, base)
    data = tomllib.loads(contract_path.read_text(encoding="utf-8"))

    prompts = PromptPaths(**data.get("prompts", {}))
    retrieval = RetrievalSettings(**data.get("retrieval", {}))
    rules = RuleSettings(**data.get("rules", {}))
    output_fields = [OutputField(**item) for item in data.get("output_fields", [])]

    contract = ChallengeContract(
        name=data["name"],
        summary=data.get("summary", ""),
        corpus_dir=data["corpus_dir"],
        input_csv=data["input_csv"],
        expected_csv=data.get("expected_csv", ""),
        output_csv=data.get("output_csv", ""),
        id_column=data["id_column"],
        text_columns=list(data.get("text_columns", [])),
        passthrough_columns=list(data.get("passthrough_columns", [])),
        prompts=prompts,
        retrieval=retrieval,
        rules=rules,
        output_fields=output_fields,
    )
    return _validate_contract(contract)
