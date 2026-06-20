from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .claim_review_pipeline import run_claim_review
from .evaluation import evaluate_csv
from .multimodal_evaluation import evaluate_claim_review_csv
from .pipeline import inspect_contract, run_contract
from .utils import ensure_directory, project_root, stable_json


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hko", description="HackerRank Orchestrate starter CLI"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    demo = subparsers.add_parser("demo", help="Run the built-in demo challenge")
    demo.add_argument("--provider", default="rule-based")
    demo.add_argument("--model", default=None)

    run = subparsers.add_parser("run", help="Run a challenge contract")
    run.add_argument("--contract", required=True)
    run.add_argument("--provider", default="rule-based")
    run.add_argument("--model", default=None)
    run.add_argument("--max-rows", type=int, default=None)

    run_claims = subparsers.add_parser(
        "run-claims",
        help="Run the Multi-Modal Evidence Review pipeline against the configured dataset",
    )
    run_claims.add_argument("--contract", required=True)
    run_claims.add_argument("--max-rows", type=int, default=None)

    inspect = subparsers.add_parser(
        "inspect", help="Inspect retrieval results for a query"
    )
    inspect.add_argument("--contract", required=True)
    inspect.add_argument("--query", required=True)

    evaluate = subparsers.add_parser(
        "evaluate", help="Compare a predicted CSV against an expected CSV"
    )
    evaluate.add_argument("--expected", required=True)
    evaluate.add_argument("--predicted", required=True)
    evaluate.add_argument("--id-column", required=True)

    evaluate_claims = subparsers.add_parser(
        "evaluate-claims",
        help="Evaluate the multimodal claim-review CSV with set-aware comparison",
    )
    evaluate_claims.add_argument("--expected", required=True)
    evaluate_claims.add_argument("--predicted", required=True)
    evaluate_claims.add_argument(
        "--set-columns",
        default="risk_flags,supporting_image_ids",
        help="Comma-separated set-like columns",
    )
    evaluate_claims.add_argument(
        "--identity-columns",
        default="user_id,image_paths,user_claim,claim_object",
        help="Comma-separated row identity columns checked in order",
    )

    kickoff = subparsers.add_parser(
        "kickoff", help="Create a dated decision note for the hackathon"
    )
    kickoff.add_argument("--name", required=True)

    return parser


def _handle_kickoff(name: str) -> Path:
    root = project_root()
    notes_dir = ensure_directory(root / "artifacts" / "notes")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = notes_dir / f"{stamp}-{name}.md"
    content = f"# Decision Note — {name}\n\n- Prompt summary:\n- Required output schema:\n- Baseline architecture choice:\n- Retrieval strategy:\n- Escalation policy:\n- First sample failure mode:\n- Improvement after iteration:\n- Biggest risk before submission:\n"
    path.write_text(content, encoding="utf-8")
    return path


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "demo":
        summary = run_contract(
            "examples/demo_challenge/contract.toml",
            provider_name=args.provider,
            model=args.model,
        )
        print(stable_json(asdict(summary)))
        return

    if args.command == "run":
        summary = run_contract(
            args.contract,
            provider_name=args.provider,
            model=args.model,
            max_rows=args.max_rows,
        )
        print(stable_json(asdict(summary)))
        return

    if args.command == "run-claims":
        summary = run_claim_review(args.contract, max_rows=args.max_rows)
        print(stable_json(asdict(summary)))
        return

    if args.command == "inspect":
        results = inspect_contract(args.contract, args.query)
        print(stable_json(results))
        return

    if args.command == "evaluate":
        report = evaluate_csv(args.expected, args.predicted, id_column=args.id_column)
        print(stable_json(report))
        return

    if args.command == "evaluate-claims":
        set_columns = [
            column for column in args.set_columns.split(",") if column.strip()
        ]
        identity_columns = [
            column for column in args.identity_columns.split(",") if column.strip()
        ]
        report = evaluate_claim_review_csv(
            args.expected,
            args.predicted,
            set_columns=set_columns,
            identity_columns=identity_columns,
        )
        print(stable_json(report))
        return

    if args.command == "kickoff":
        note_path = _handle_kickoff(args.name)
        print(note_path.relative_to(project_root()))
        return

    parser.error("Unknown command")
