from __future__ import annotations

import csv
import shutil
from pathlib import Path

from .artifacts import (
    create_run_dir,
    render_run_transcript,
    write_json,
    write_jsonl,
    write_text,
)
from .contracts import ChallengeContract, RunSummary, load_contract
from .corpus import load_chunks
from .evaluation import evaluate_csv
from .llm import ProviderError, make_provider
from .retrieval import LexicalIndex
from .rules import (
    classify_request_type,
    field_kind,
    finalize_values,
    find_escalation_reasons,
    infer_product_area,
)
from .utils import (
    ensure_directory,
    iso_utc_now,
    load_env_file,
    project_root,
    resolve_path,
    sha256_file,
    sha256_text,
)


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


def build_query(row: dict[str, str], text_columns: list[str]) -> str:
    parts = [
        row.get(column, "").strip()
        for column in text_columns
        if row.get(column, "").strip()
    ]
    return "\n".join(parts)


def _first_allowed_values(contract: ChallengeContract, kind: str) -> list[str]:
    for field in contract.output_fields:
        if field_kind(field.name) == kind:
            return field.allowed_values
    return []


def run_contract(
    contract_path: str | Path,
    *,
    provider_name: str = "rule-based",
    model: str | None = None,
    max_rows: int | None = None,
) -> RunSummary:
    root = project_root()
    load_env_file(root / ".env")
    contract_file = resolve_path(contract_path, root)
    contract = load_contract(contract_file, base=root)

    chunks = load_chunks(contract)
    index = LexicalIndex.build(chunks)
    provider = make_provider(provider_name, model)

    input_path = resolve_path(contract.input_csv, root)
    input_rows = _read_input_rows(input_path)
    if max_rows is not None:
        input_rows = input_rows[:max_rows]

    run_dir = create_run_dir(root / "artifacts" / "runs", contract.name)
    output_path = run_dir / "output.csv"

    output_rows: list[dict[str, str]] = []
    retrieval_rows: list[dict[str, object]] = []
    transcript_rows: list[dict[str, object]] = []

    area_allowed = _first_allowed_values(contract, "product_area")
    request_type_allowed = _first_allowed_values(contract, "request_type")

    for row_number, row in enumerate(input_rows, start=1):
        query = build_query(row, contract.text_columns)
        hits = index.search(
            query,
            top_k=min(contract.retrieval.top_k, contract.retrieval.max_chunks),
            min_score=contract.retrieval.min_score,
        )
        product_area = infer_product_area(query, hits, area_allowed)
        request_type = classify_request_type(query, request_type_allowed)
        escalation_reasons = find_escalation_reasons(query, hits, contract)

        try:
            draft = (
                {}
                if escalation_reasons
                else provider.generate(contract, row, query, hits)
            )
        except ProviderError as exc:
            escalation_reasons = [str(exc)]
            draft = {}

        finalized = finalize_values(
            contract,
            draft,
            query=query,
            hits=hits,
            product_area=product_area,
            request_type=request_type,
            escalation_reasons=escalation_reasons,
        )

        output_row = {
            column: row.get(column, "") for column in contract.passthrough_columns
        }
        output_row.update(finalized)
        output_rows.append(output_row)

        retrieval_rows.append(
            {
                "row_number": row_number,
                "row_id": row.get(contract.id_column, str(row_number)),
                "query": query,
                "hits": [
                    {
                        "chunk_id": hit.chunk_id,
                        "source_path": hit.source_path,
                        "score": hit.score,
                    }
                    for hit in hits
                ],
            }
        )
        transcript_rows.append(
            {
                "row_number": row_number,
                "row_id": row.get(contract.id_column, str(row_number)),
                "query": query,
                "status": output_row.get("status", ""),
                "product_area": output_row.get("product_area", ""),
                "request_type": output_row.get("request_type", ""),
                "top_sources": [Path(hit.source_path).name for hit in hits[:3]],
                "reasons": escalation_reasons,
                "response": output_row.get("response", ""),
                "justification": output_row.get("justification", ""),
            }
        )

    _write_output_csv(output_path, output_rows, contract.output_header())
    if contract.output_csv:
        mirrored_output = resolve_path(contract.output_csv, root)
        ensure_directory(mirrored_output.parent)
        shutil.copyfile(output_path, mirrored_output)

    prompt_hashes = {}
    if contract.prompts.system:
        prompt_hashes["system"] = sha256_file(
            resolve_path(contract.prompts.system, root)
        )
    if contract.prompts.solve:
        prompt_hashes["solve"] = sha256_file(resolve_path(contract.prompts.solve, root))
    if contract.prompts.verify:
        prompt_hashes["verify"] = sha256_file(
            resolve_path(contract.prompts.verify, root)
        )

    manifest = {
        "run_timestamp_utc": iso_utc_now(),
        "contract_name": contract.name,
        "contract_path": str(contract_file.relative_to(root)),
        "provider": provider.name,
        "model": getattr(provider, "model", ""),
        "rows_processed": len(output_rows),
        "chunk_count": len(chunks),
        "input_csv": contract.input_csv,
        "corpus_dir": contract.corpus_dir,
        "output_csv": str(output_path.relative_to(root)),
        "contract_hash": sha256_text(str(contract.to_dict())),
        "prompt_hashes": prompt_hashes,
    }

    write_json(run_dir / "manifest.json", manifest)
    write_jsonl(run_dir / "retrieved_evidence.jsonl", retrieval_rows)
    write_text(
        run_dir / "run_transcript.md",
        render_run_transcript(contract.name, transcript_rows),
    )
    write_text(
        run_dir / "resolved_contract.toml", contract_file.read_text(encoding="utf-8")
    )

    evaluation_path: Path | None = None
    if contract.expected_csv:
        expected_path = resolve_path(contract.expected_csv, root)
        if expected_path.exists():
            evaluation = evaluate_csv(
                expected_path, output_path, id_column=contract.id_column
            )
            evaluation_path = run_dir / "evaluation.json"
            write_json(evaluation_path, evaluation)

    return RunSummary(
        run_dir=str(run_dir.relative_to(root)),
        output_csv=str(output_path.relative_to(root)),
        rows_processed=len(output_rows),
        provider=provider.name,
        model=getattr(provider, "model", ""),
        evaluation_path=str(evaluation_path.relative_to(root))
        if evaluation_path
        else None,
    )


def inspect_contract(contract_path: str | Path, query: str) -> list[dict[str, object]]:
    root = project_root()
    contract = load_contract(contract_path, base=root)
    chunks = load_chunks(contract)
    index = LexicalIndex.build(chunks)
    hits = index.search(
        query,
        top_k=min(contract.retrieval.top_k, contract.retrieval.max_chunks),
        min_score=contract.retrieval.min_score,
    )
    return [
        {
            "rank": index + 1,
            "score": hit.score,
            "source_path": hit.source_path,
            "title": hit.title,
            "preview": hit.text[:240],
        }
        for index, hit in enumerate(hits)
    ]
