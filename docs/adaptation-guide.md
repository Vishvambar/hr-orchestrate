# Adaptation Guide

This repo is meant to absorb an unknown challenge quickly.

## The main files you should touch when the prompt arrives

### 1. `challenge/current/contract.toml`

This is the highest-value file.
Update:
- `corpus_dir`
- `input_csv`
- `output_csv`
- `id_column`
- `text_columns`
- `passthrough_columns`
- `output_fields`
- retrieval thresholds
- escalation keywords

### 2. `configs/prompts/system.md`

Tune this only if the official prompt adds important constraints.
Examples:
- formal tone requirements
- citation requirements
- short-answer requirements
- safety rules specific to the challenge

### 3. `configs/prompts/solve.md`

Tune this if the output schema or reasoning pattern changes.
Do not add complexity until you have inspected retrieval on real rows.

## Commands to use in order

### Inspect retrieval on a real row

```bash
./venv/bin/python -m claim_orchestrator inspect --contract challenge/current/contract.toml --query "paste a representative row here"
```

### Run a first end-to-end pass

```bash
./venv/bin/python -m claim_orchestrator run --contract challenge/current/contract.toml --provider rule-based
```

### Upgrade to a hosted model if needed

```bash
./venv/bin/python -m pip install -e .[openai]
./venv/bin/python -m claim_orchestrator run --contract challenge/current/contract.toml --provider openai --model gpt-4.1-mini
```

## How to think about output fields

For each output field ask:
- is it an enum?
- what are the exact allowed values?
- should unsupported cases escalate?
- which fields must be strictly grounded in corpus evidence?

## If the challenge is not support-ticket shaped

That is fine. This scaffold is still useful because it separates:
- contract definition
- corpus loading
- retrieval
- safety / escalation
- output writing
- evaluation artifacts

You may only need to change the contract and prompts.

## If the official starter repo has its own structure

Two good options:
1. copy the official files into `challenge/current/` and keep this scaffold as the driver
2. move this scaffold under the official repo's `code/` or equivalent runtime folder

Prefer the option that preserves the official evaluator contract with the least risk.
