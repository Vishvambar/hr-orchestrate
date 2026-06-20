from __future__ import annotations

import argparse
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

CODE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = CODE_ROOT / "src"
if str(CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from main import _default_contract_text, _find_dataset_dir  # noqa: E402

from claim_orchestrator.claim_review_pipeline import run_claim_review  # noqa: E402
from claim_orchestrator.utils import stable_json  # noqa: E402


def _sample_contract_text(dataset_dir: Path, output_path: Path) -> str:
    """Build a contract that uses sample_claims.csv as both input and labels."""
    contract_text = _default_contract_text(dataset_dir, output_path)
    expected_line = next(
        line
        for line in contract_text.splitlines()
        if line.startswith("expected_csv = ")
    )
    sample_path_literal = expected_line.split("=", 1)[1].strip()
    lines = []
    for line in contract_text.splitlines():
        if line.startswith("input_csv = "):
            lines.append(f"input_csv = {sample_path_literal}")
        else:
            lines.append(line)
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate the Multi-Modal Evidence Review pipeline on dataset/sample_claims.csv."
    )
    parser.add_argument("--max-rows", type=int, default=None)
    parser.add_argument(
        "--output",
        default="code/evaluation/sample_predictions.csv",
        help="Sample prediction CSV path relative to the repo root.",
    )
    args = parser.parse_args()

    dataset_dir = _find_dataset_dir()
    output_path = (CODE_ROOT.parent / args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    temp_dir = Path(tempfile.mkdtemp(prefix="orchestrate_sample_contract_"))
    contract_path = temp_dir / "contract.toml"
    contract_path.write_text(
        _sample_contract_text(dataset_dir, output_path), encoding="utf-8"
    )

    summary = run_claim_review(contract_path, max_rows=args.max_rows)
    print(stable_json(asdict(summary)))


if __name__ == "__main__":
    main()
