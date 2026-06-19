# Multi-Modal Evidence Review Submission Code

This `code/` directory is structured to match the HackerRank Orchestrate submission contract.

## Expected repo layout during evaluation

```text
.
├── dataset/
│   ├── test.csv or claims.csv
│   ├── sample_claims.csv or sample.csv
│   ├── user_history.csv
│   ├── evidence_requirements.csv
│   └── images/...
└── code/
    ├── main.py
    ├── src/
    ├── configs/
    └── evaluation/
```

## Install

```bash
pip install -r code/requirements.txt
```

## Environment

Configure at least one vision-capable provider. The sequential failover chain is:
1. GitHub Models (`GITHUB_TOKEN`, default model `gpt-4o`)
2. Gemini (`GEMINI_API_KEY`, default model `gemini-2.5-flash`)
3. OpenRouter (`OPENROUTER_API_KEY`, default model `openai/gpt-4o-mini`)

Optional overrides:
- `GITHUB_MODEL`
- `GEMINI_MODEL`
- `OPENROUTER_MODEL`
- `ORCH_ROW_DELAY_SECONDS`
- `ORCH_VISION_COOLDOWN_SECONDS`
- `ORCH_VISION_MAX_CYCLES`
- `ORCH_PROVIDER_ORDER` such as `github_models,gemini,openrouter` for high-quality quota-safe runs when GitHub is healthy, or `openrouter,gemini,github_models` for faster bulk runs
- `ORCH_RESUME_OUTPUT` defaults to `true` so interrupted runs resume from completed rows instead of repeating API calls

## Run

From the repo root:

```bash
python code/main.py
```

Optional:

```bash
python code/main.py --max-rows 5
python code/main.py --output output.csv
python code/main.py --contract code/contract.toml
```

## What it produces

- `output.csv` at the repo root by default
- run artifacts under `artifacts/runs/` when using the full workspace
- `code/evaluation/evaluation_report.md` is updated with operational notes when run via the full pipeline

## Design notes

- images are treated as the primary source of truth
- user history is used only for risk context
- evidence requirements are used to decide whether the image set is sufficient
- provider failover is sequential and bounded to reduce free-tier failure risk
- interrupted runs resume from the existing `output.csv` prefix to avoid wasting free quota on repeated rows
- final label normalization is deterministic in Python
- mislabeled/unsupported image containers such as AVIF files with `.jpg` names are converted to cached JPEG copies before API calls
