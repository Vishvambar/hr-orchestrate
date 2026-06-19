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

LATEST_RUN=$(find "$ROOT/artifacts/runs" -mindepth 1 -maxdepth 1 -type d ! -name latest | sort | tail -n 1 || true)
if [ -z "$LATEST_RUN" ] || [ ! -f "$LATEST_RUN/manifest.json" ]; then
  echo "No completed run directory found under artifacts/runs. Run the agent first." >&2
  exit 1
fi

CODE_ZIP="$DEST/code.zip"
"$PY" - "$ROOT" "$CODE_ZIP" <<'PY'
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
import sys

root = Path(sys.argv[1])
out = Path(sys.argv[2])
include = [
    "src",
    "configs",
    "docs",
    "scripts",
    "tests",
    "README.md",
    "pyproject.toml",
    "AGENTS.md",
    ".env.example",
    "Makefile",
]
with ZipFile(out, "w", compression=ZIP_DEFLATED) as zf:
    for item in include:
        path = root / item
        if not path.exists():
            continue
        if path.is_dir():
            for sub in sorted(p for p in path.rglob("*") if p.is_file()):
                zf.write(sub, sub.relative_to(root))
        else:
            zf.write(path, path.relative_to(root))
PY

cp "$LATEST_RUN/output.csv" "$DEST/output.csv"
cp "$LATEST_RUN/manifest.json" "$DEST/manifest.json"
cp "$LATEST_RUN/run_transcript.md" "$DEST/run_transcript.md"
if [ -f "$LATEST_RUN/evaluation.json" ]; then
  cp "$LATEST_RUN/evaluation.json" "$DEST/evaluation.json"
fi

CHAT_LOG="$HOME/hackerrank_orchestrator/log.txt"
if [ -f "$CHAT_LOG" ]; then
  cp "$CHAT_LOG" "$DEST/ai_chat_transcript.log"
fi

echo "Submission package created at: $DEST"
