# Orchestrate Research Notes

This workspace is tuned to the public signals HackerRank has already shared.

## Public facts used here

### June 2026 event page

Public event copy says the flow is:
1. receive the challenge by email at `11 AM IST`
2. build and submit the solution
3. complete a `30-minute AI judge interview`
4. upload `code`, `agent output`, and `AI chat transcript`

### May 2026 public starter repo + rubric

The May edition rubric evaluated participants across four dimensions:
- agent design / code quality
- AI judge interview
- output CSV accuracy
- AI fluency from the transcript

The public rubric emphasized:
- separation of concerns
- grounding answers in the provided corpus
- explicit escalation for risky or unsupported cases
- deterministic, reproducible runs
- readable code and secrets via env vars only

### HackerRank postmortem blog

Public write-up after May highlighted that top participants:
- planned before writing code
- set explicit constraints and architectural decisions up front
- iterated on sample data and inspected outputs continuously
- treated the AI as an engineering partner, not an autopilot
- explained choices in ownership language: `I chose...`, `I rejected...`, `I observed regressions on...`

The blog also gave a concrete example of a strong explanation:
- start with `BM25` / lexical retrieval for small keyword-heavy corpora
- add complexity only after observing specific failures

## What that means for this repo

This starter intentionally prefers:
- a terminal-first workflow
- a simple, explainable retrieval baseline
- explicit artifacts per run
- clear adaptation points when the official prompt arrives
- strong fallback / escalation logic instead of unsupported guesses

## Strategy for a high-signal submission

1. Read the prompt and write down the exact contract before coding.
2. Make the first version boring and reproducible.
3. Inspect retrieval on real sample rows early.
4. Add complexity only after you can explain why the baseline misses.
5. Save evidence for every change: what improved, what regressed, and why.
6. Keep notes for the interview while building, not after.

## Recommended talking points for the judge

- why you started with lexical retrieval
- why the escalation gate exists and what it protects against
- how the pipeline stays deterministic
- what artifacts you save per run and why that matters
- where the system can fail and what you would improve next

## Useful links

- June event page: `https://www.hackerrank.com/hackerrank-orchestrate-june26`
- May starter repo: `https://github.com/interviewstreet/hackerrank-orchestrate-may26`
- Public rubric file: `evalutation_criteria.md` in that repo
- Postmortem blog: `https://www.hackerrank.com/blog/what-12885-developers-taught-us-about-building-with-ai/`
