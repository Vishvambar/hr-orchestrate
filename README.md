# HackerRank Orchestrate Starter Workspace

This workspace is prepped for **HackerRank Orchestrate** with a bias toward the public judging rubric: clean architecture, grounded corpus use, deterministic behavior, explicit escalation, and strong interview explainability.

It is intentionally **stdlib-first** so it runs cleanly on the existing Python `3.14` virtualenv without depending on a large framework stack.

## What is already ready

- a terminal-first Python package under `src/hackerrank_orchestrator/`
- configurable challenge contract via `TOML`
- local corpus loading and deterministic lexical retrieval
- explicit escalation rules for risky / unsupported cases
- rule-based fallback provider that works with zero API keys
- optional `OpenAI` and `Anthropic` provider stubs for hackathon-time upgrades
- run artifacts: `manifest.json`, `retrieved_evidence.jsonl`, `run_transcript.md`, `output.csv`
- packaging script for `code zip + output + transcript`
- research notes and an AI judge cheat sheet
- a runnable demo challenge so you can verify the pipeline before 11

## Quick start

### 1. Install the local package

```bash
./venv/bin/python -m pip install -e .
```

### 2. Run the demo end-to-end

```bash
./venv/bin/python -m hackerrank_orchestrator demo
```

### 3. Run tests

```bash
./venv/bin/python -m unittest discover -s tests -p 'test_*.py'
```

## When the official challenge arrives

1. Put the official files under `challenge/current/`.
2. Copy `configs/challenge.template.toml` to `challenge/current/contract.toml`.
3. Update the contract paths, input columns, output fields, and labels.
4. Review `configs/prompts/system.md` and `configs/prompts/solve.md`.
5. Use retrieval inspection on a few sample rows.
6. Run on sample data first.
7. Iterate against evidence.
8. Run on the full input and package the submission.

## Core commands

```bash
# Run any challenge contract
./venv/bin/python -m hackerrank_orchestrator run --contract challenge/current/contract.toml --provider rule-based

# Use a hosted LLM after installing the extra you want
./venv/bin/python -m pip install -e .[openai]
./venv/bin/python -m hackerrank_orchestrator run --contract challenge/current/contract.toml --provider openai --model gpt-4.1-mini

# Inspect retrieval before changing prompts
./venv/bin/python -m hackerrank_orchestrator inspect --contract challenge/current/contract.toml --query "example question"

# Evaluate against a gold CSV if one exists
./venv/bin/python -m hackerrank_orchestrator evaluate --expected examples/demo_challenge/expected/output.csv --predicted artifacts/runs/<run-id>/output.csv --id-column ticket_id

# Create a dated decision note for your interview prep
./venv/bin/python -m hackerrank_orchestrator kickoff --name june26
```

## Repo map

- `src/hackerrank_orchestrator/` — agent pipeline and CLI
- `configs/` — prompt templates and challenge contract template
- `docs/` — research, playbook, adaptation guide, judge prep
- `examples/demo_challenge/` — sample corpus + input + expected output
- `challenge/current/` — drop the official challenge here when it arrives
- `artifacts/runs/` — generated run artifacts
- `submissions/` — packaged deliverables ready to upload

## Transcript logging for the hackathon

The June event page says you will upload **code, agent output, and AI chat transcript**.

This workspace includes `AGENTS.md` so tools that support it can append summaries to:

- `~/hackerrank_orchestrator/log.txt`

The packaging script tries to copy that transcript automatically if it exists.

## Strategy references

- `docs/orchestrate-research.md`
- `docs/hackathon-playbook.md`
- `docs/adaptation-guide.md`
- `docs/judge-interview-cheatsheet.md`
# hr-orchestrate
