# AI Judge Interview Cheat Sheet

Use this as a live prep sheet and customize it during the hackathon.

## 1. Explain the architecture in one minute

Suggested shape:

- The pipeline is terminal-first and contract-driven.
- I load the local corpus, chunk it deterministically, and index it with lexical retrieval.
- For each input row, I build a search query from the configured text fields.
- I retrieve evidence, apply an explicit escalation gate, then generate structured outputs.
- Every run saves artifacts: manifest, retrieval evidence, output CSV, and a run transcript.

## 2. Why this retrieval strategy?

Suggested answer:

> I started with lexical retrieval because public Orchestrate guidance and the May postmortem both reward explainability and iteration discipline. A lexical baseline is deterministic, easy to inspect, and strong on small keyword-heavy corpora. I would only add embeddings or reranking after seeing concrete misses in sample rows.

## 3. Why the escalation gate?

Suggested answer:

> Unsupported confident answers are usually worse than a conservative escalation. The gate protects against risky requests, low-evidence rows, and out-of-scope asks. It also makes the system easier to reason about and defend.

## 4. What makes the runs reproducible?

- config is stored in a contract file
- prompt templates live in files
- retrieval ordering is deterministic
- output schema is explicit
- each run writes a manifest with paths and timestamps

## 5. Alternatives you can mention honestly

- framework-heavy agent stacks: rejected initially to keep the system inspectable
- embeddings first: rejected until the lexical baseline shows specific misses
- multi-agent orchestration: rejected as unnecessary complexity for the first reliable version

## 6. Failure modes to admit clearly

- lexical retrieval can miss semantic paraphrases
- generic prompt templates may need task-specific wording
- rule-based escalation may be too strict or too loose until tuned on sample rows
- free-form response quality depends on evidence quality and provider behavior

## 7. Ownership language to practice

Prefer:
- `I chose... because...`
- `I rejected... because...`
- `I saw regressions on...`
- `I kept this deterministic by...`
- `I used the corpus as the source of truth...`

Avoid:
- `the AI decided...`
- `the tool built...`
- `Claude wrote...`

## 8. Fill these in during the hackathon

- Biggest quality improvement I made:
- Worst failure mode I found:
- Retrieval change I considered but rejected:
- Reason I trusted the final version:
- What I would do with two more hours:
