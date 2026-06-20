# Hackathon Playbook

## Before 11 AM

- verify the local package installs
- run the demo once
- keep email, browser, and terminal ready
- decide your primary model provider in advance, but keep `rule-based` available as a fallback
- keep `docs/judge-interview-cheatsheet.md` open while building

## First 20 minutes after the prompt arrives

1. Save every official file under `challenge/current/`.
2. Read the problem statement fully.
3. Copy `configs/challenge.template.toml` to `challenge/current/contract.toml`.
4. Fill in:
   - corpus path
   - input CSV path
   - output fields and allowed values
   - id column and text columns
5. Run `kickoff` to create a dated decision note.
6. Write down the first-pass architecture in 5 bullets.

## First working version

Goal: get a complete end-to-end run as quickly as possible.

- start with the existing retrieval + escalation baseline
- run on a few sample rows first
- use `inspect` before touching prompts or provider code
- only switch to a hosted model after the contract is stable

## Iteration loop

For each iteration:
1. identify one failure mode
2. form a concrete hypothesis
3. change one thing
4. run again on sample data
5. save the result and note the tradeoff

Avoid changing retrieval, rules, prompts, and output formatting all at once.

## Submission checklist

- `output.csv` generated from the final full run
- run artifacts saved under `artifacts/runs/`
- `code.zip` created with source + configs + docs, but not `venv/` or bulky artifacts
- AI chat transcript available at `~/claim_orchestrator/log.txt` if your coding tool honored `AGENTS.md`
- judge notes updated with:
  - architecture choice
  - alternatives rejected
  - biggest observed failure mode
  - one improvement you would make with more time

## Red flags to avoid

- hallucinating unsupported answers instead of escalating
- adding heavy frameworks you cannot defend
- skipping retrieval inspection
- relying on memory instead of the provided corpus
- letting the model invent enum labels or extra output columns
- waiting until the end to think about the interview
