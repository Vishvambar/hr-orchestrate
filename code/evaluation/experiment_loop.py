from __future__ import annotations

import argparse
import os
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

from evaluation.main import _sample_contract_text  # noqa: E402
from main import _find_dataset_dir  # noqa: E402

from hackerrank_orchestrator.claim_review_pipeline import run_claim_review  # noqa: E402
from hackerrank_orchestrator.utils import stable_json  # noqa: E402

VARIANTS: dict[str, dict[str, str]] = {
    "baseline": {
        "ORCH_USE_FEW_SHOT": "false",
        "ORCH_IMAGE_DETAIL": "auto",
    },
    "few_shot": {
        "ORCH_USE_FEW_SHOT": "true",
        "ORCH_IMAGE_DETAIL": "auto",
    },
    "high_detail": {
        "ORCH_USE_FEW_SHOT": "false",
        "ORCH_IMAGE_DETAIL": "high",
    },
    "few_shot_high_detail": {
        "ORCH_USE_FEW_SHOT": "true",
        "ORCH_IMAGE_DETAIL": "high",
    },
}


def _run_variant(
    name: str, env_updates: dict[str, str], max_rows: int | None
) -> dict[str, object]:
    previous = {key: os.environ.get(key) for key in env_updates}
    try:
        os.environ.update(env_updates)
        os.environ.setdefault("ORCH_RESUME_OUTPUT", "false")
        dataset_dir = _find_dataset_dir()
        output_path = (
            CODE_ROOT.parent / "code" / "evaluation" / "experiments" / f"{name}.csv"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_dir = Path(tempfile.mkdtemp(prefix=f"orchestrate_experiment_{name}_"))
        contract_path = temp_dir / "contract.toml"
        contract_path.write_text(
            _sample_contract_text(dataset_dir, output_path.resolve()), encoding="utf-8"
        )
        summary = run_claim_review(contract_path, max_rows=max_rows)
        return asdict(summary)
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run small sample_claims.csv prompt/parameter experiments. Uses model quota only with --execute."
    )
    parser.add_argument(
        "--variants",
        default="baseline,few_shot,high_detail",
        help="Comma-separated variants. Available: " + ", ".join(sorted(VARIANTS)),
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=3,
        help="Sample rows per variant. Keep small for quota-safe iteration.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually run models. Without this flag, only prints the planned experiments.",
    )
    args = parser.parse_args()

    selected = [item.strip() for item in args.variants.split(",") if item.strip()]
    unknown = [item for item in selected if item not in VARIANTS]
    if unknown:
        raise SystemExit(f"Unknown variants: {', '.join(unknown)}")

    plan = {
        "execute": args.execute,
        "max_rows_per_variant": args.max_rows,
        "estimated_successful_calls": len(selected) * (args.max_rows or 20),
        "variants": {name: VARIANTS[name] for name in selected},
    }
    print(stable_json(plan))

    if not args.execute:
        print("Dry run only. Add --execute to spend model quota on these experiments.")
        return

    results = []
    for name in selected:
        print(f"\n[experiment] running {name}", flush=True)
        results.append(
            {
                "variant": name,
                "summary": _run_variant(name, VARIANTS[name], args.max_rows),
            }
        )
    print(stable_json({"results": results}))


if __name__ == "__main__":
    main()
