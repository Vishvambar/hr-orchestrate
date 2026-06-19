from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import log
import re

from .contracts import Chunk, RetrievalHit

_TOKEN_RE = re.compile(r"[a-z0-9_]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


@dataclass(slots=True)
class LexicalIndex:
    chunks: list[Chunk]
    term_frequencies: list[Counter[str]]
    document_frequency: Counter[str]
    average_length: float

    @classmethod
    def build(cls, chunks: list[Chunk]) -> "LexicalIndex":
        term_frequencies: list[Counter[str]] = []
        document_frequency: Counter[str] = Counter()
        total_length = 0
        for chunk in chunks:
            tokens = tokenize(chunk.text)
            frequencies = Counter(tokens)
            term_frequencies.append(frequencies)
            total_length += len(tokens)
            for token in frequencies:
                document_frequency[token] += 1
        average_length = (total_length / len(chunks)) if chunks else 1.0
        return cls(
            chunks=chunks,
            term_frequencies=term_frequencies,
            document_frequency=document_frequency,
            average_length=average_length,
        )

    def search(self, query: str, *, top_k: int = 5, min_score: float = 0.0) -> list[RetrievalHit]:
        query_tokens = tokenize(query)
        if not query_tokens:
            return []
        query_terms = Counter(query_tokens)
        total_docs = max(len(self.chunks), 1)
        k1 = 1.5
        b = 0.75

        hits: list[RetrievalHit] = []
        for chunk, frequencies in zip(self.chunks, self.term_frequencies, strict=True):
            chunk_length = sum(frequencies.values()) or 1
            score = 0.0
            for term, q_freq in query_terms.items():
                tf = frequencies.get(term, 0)
                if not tf:
                    continue
                df = self.document_frequency.get(term, 0)
                idf = log(((total_docs - df + 0.5) / (df + 0.5)) + 1.0)
                numerator = tf * (k1 + 1.0)
                denominator = tf + k1 * (1.0 - b + b * (chunk_length / self.average_length))
                score += q_freq * idf * (numerator / denominator)
            if score >= min_score:
                hits.append(
                    RetrievalHit(
                        chunk_id=chunk.chunk_id,
                        doc_id=chunk.doc_id,
                        title=chunk.title,
                        source_path=chunk.source_path,
                        text=chunk.text,
                        score=round(score, 6),
                    )
                )
        hits.sort(key=lambda hit: (-hit.score, hit.source_path, hit.chunk_id))
        return hits[:top_k]
