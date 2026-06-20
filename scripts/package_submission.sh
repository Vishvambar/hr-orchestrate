#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
PY="$ROOT/venv/bin/python"
if [ ! -x "$PY" ]; then
  PY=python3
fi

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
DEST="$ROOT/submissions/$TIMESTAMP"
mkdir -p "$DEST"

OUTPUT_CSV="$ROOT/output.csv"
if [ ! -f "$OUTPUT_CSV" ]; then
  echo "output.csv not found at repo root. Run: python code/main.py" >&2
  exit 1
fi

"$PY" - "$ROOT" <<'PY'
import csv
import sys
from pathlib import Path

root = Path(sys.argv[1])
output_csv = root / "output.csv"
claims_csv = root / "dataset" / "claims.csv"
if claims_csv.exists():
    expected = sum(1 for _ in csv.DictReader(claims_csv.open(newline="", encoding="utf-8")))
    actual = sum(1 for _ in csv.DictReader(output_csv.open(newline="", encoding="utf-8")))
    if actual != expected:
        raise SystemExit(
            f"output.csv has {actual} prediction rows, but dataset/claims.csv has {expected}. "
            "Finish the run before packaging."
        )
PY

LATEST_RUN=$(find "$ROOT/code/artifacts/runs" "$ROOT/artifacts/runs" -mindepth 1 -maxdepth 1 -type d ! -name latest 2>/dev/null | sort | tail -n 1 || true)

CODE_ZIP="$DEST/code.zip"
"$PY" - "$ROOT" "$CODE_ZIP" <<'PY'
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
import sys

root = Path(sys.argv[1])
out = Path(sys.argv[2])
code_dir = root / "code"
if not code_dir.exists():
    raise SystemExit("code/ directory not found. Cannot build submission zip.")

with ZipFile(out, "w", compression=ZIP_DEFLATED) as zf:
    for sub in sorted(p for p in code_dir.rglob("*") if p.is_file()):
        rel_parts = sub.relative_to(code_dir).parts
        if rel_parts and rel_parts[0] in {"artifacts", "dataset", "data", "node_modules", "venv", ".venv"}:
            continue
        if "__pycache__" in sub.parts or ".orchestrate_image_cache" in sub.parts:
            continue
        if sub.name == ".env" or sub.name.endswith(".env"):
            continue
        if sub.suffix in {".pyc", ".pyo"}:
            continue
        zf.write(sub, sub.relative_to(root))
PY

cp "$OUTPUT_CSV" "$DEST/output.csv"
if [ -n "$LATEST_RUN" ]; then
  if [ -f "$LATEST_RUN/manifest.json" ]; then
    cp "$LATEST_RUN/manifest.json" "$DEST/manifest.json"
  fi
  if [ -f "$LATEST_RUN/run_transcript.md" ]; then
    cp "$LATEST_RUN/run_transcript.md" "$DEST/run_transcript.md"
  fi
  if [ -f "$LATEST_RUN/evaluation.json" ]; then
    cp "$LATEST_RUN/evaluation.json" "$DEST/evaluation.json"
  fi
fi

CHAT_LOG="$HOME/claim_orchestrator/log.txt"
if [ -f "$CHAT_LOG" ]; then
  cp "$CHAT_LOG" "$DEST/ai_chat_transcript.log"
fi

echo "Submission package created at: $DEST"
