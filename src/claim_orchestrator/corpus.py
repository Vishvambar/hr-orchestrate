from __future__ import annotations

import re
from pathlib import Path

from .contracts import ChallengeContract, Chunk
from .utils import collapse_whitespace, project_root, resolve_path

_TEXT_SUFFIXES = {".md", ".txt", ".html", ".csv", ".json", ".yaml", ".yml"}
_HEADING_RE = re.compile(r"^#\s+(.*)$", re.MULTILINE)


def _extract_title(path: Path, text: str) -> str:
    match = _HEADING_RE.search(text)
    if match:
        return match.group(1).strip()
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    return first_line or path.stem.replace("_", " ").replace("-", " ").title()


def _split_chunks(text: str, *, chunk_size: int, chunk_overlap: int) -> list[str]:
    normalized = text.strip()
    if not normalized:
        return []
    if len(normalized) <= chunk_size:
        return [normalized]

    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        if end < len(normalized):
            split_at = normalized.rfind("\n\n", start, end)
            if split_at <= start:
                split_at = normalized.rfind(". ", start, end)
            if split_at > start:
                end = split_at + 1
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(normalized):
            break
        start = max(end - chunk_overlap, start + 1)
    return chunks


def load_chunks(contract: ChallengeContract) -> list[Chunk]:
    root = project_root()
    corpus_dir = resolve_path(contract.corpus_dir, root)
    if not corpus_dir.exists():
        raise FileNotFoundError(f"Corpus directory not found: {corpus_dir}")

    chunks: list[Chunk] = []
    for file_path in sorted(
        p
        for p in corpus_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in _TEXT_SUFFIXES
    ):
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        text = text.replace("\r\n", "\n")
        title = _extract_title(file_path, text)
        text = re.sub(r"^#\s+.*$", "", text, count=1, flags=re.MULTILINE)
        text = collapse_whitespace(text)
        doc_id = str(file_path.relative_to(corpus_dir))
        for index, chunk_text in enumerate(
            _split_chunks(
                text,
                chunk_size=contract.retrieval.chunk_size,
                chunk_overlap=contract.retrieval.chunk_overlap,
            )
        ):
            chunks.append(
                Chunk(
                    chunk_id=f"{doc_id}::{index}",
                    doc_id=doc_id,
                    title=title,
                    source_path=str(file_path.relative_to(root)),
                    text=chunk_text,
                )
            )
    return chunks
