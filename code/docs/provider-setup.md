# Provider Setup for Low-Cost / Free-Tier Use

If you do **not** want to rely on a paid model, that is fine.
This starter can still work for the hackathon as long as:
- the official prompt allows external model APIs
- your agent uses the **local challenge corpus** as the source of truth
- you do **not** use the live web for challenge answers

## Important security note

If you ever pasted real API keys into chat, treat them as compromised.
Rotate or revoke them before the hackathon.

## Recommended setup philosophy

Do **not** keep ten provider keys in your `.env` just because you have them.
For the hackathon, keep only:
- one primary provider
- optionally one backup provider

That keeps debugging simple and avoids accidental provider switching.

## Best options in this repo

### Option A — Stay fully local first

Use the deterministic baseline until the task contract is stable:

```bash
./venv/bin/python -m hackerrank_orchestrator run --contract challenge/current/contract.toml --provider rule-based
```

This is the safest starting point for:
- schema validation
- retrieval debugging
- escalation tuning

### Option B — Use one OpenAI-compatible provider

Create a minimal `.env` with just these values:

```bash
OPENAI_COMPAT_API_KEY=...
OPENAI_COMPAT_BASE_URL=...
OPENAI_COMPAT_MODEL=...
```

Then run:

```bash
./venv/bin/python -m pip install -e .[openai]
./venv/bin/python -m hackerrank_orchestrator run --contract challenge/current/contract.toml --provider compat
```

Use this when you have exactly one provider you trust.

### Option C — Use auto fallback across compatible providers

Supported env names in `auto` mode:
- `CEREBRAS_API_KEY` + `CEREBRAS_MODEL`
- `GROQ_API_KEY` + `GROQ_MODEL`
- `OPENROUTER_API_KEY` + `OPENROUTER_MODEL`
- `DEEPSEEK_API_KEY` + `DEEPSEEK_MODEL`
- `FIREWORKS_API_KEY` + `FIREWORKS_MODEL`
- `SAMBANOVA_API_KEY` + `SAMBANOVA_MODEL`
- `XAI_API_KEY` + `XAI_MODEL`
- `OPENAI_API_KEY` + `OPENAI_MODEL`

Then run:

```bash
./venv/bin/python -m pip install -e .[openai]
./venv/bin/python -m hackerrank_orchestrator run --contract challenge/current/contract.toml --provider auto
```

This will try the first configured compatible provider that works and fail over if needed.

## What changed compared with the raw JS pattern

The current Python implementation fixes a few things that matter in the hackathon:
- it does **not** mutate the prompt messages in place across retries
- it supports a clean fallback chain instead of selecting one provider only once
- it uses `temperature=0` for more deterministic outputs
- it strips code fences and trailing commas before JSON parsing
- it falls back when `response_format=json_object` is unsupported by a compatible provider

## Important note for Multi-Modal Evidence Review

The official prompt is image-first. Public model docs indicate that `gpt-oss-120b` is text-only, and the public docs for `zai-glm-4.7` also describe text-only input. That means those two public Cerebras options are not sufficient by themselves for the image-review portion of this challenge.

Cerebras documentation does list `Gemma 4 31B` and `Kimi K2.6` under vision and multimodal use cases, but availability may depend on your plan or endpoint access. Verify image-input support before committing to Cerebras for the final run.

## Recommended vision failover chain for this challenge

The current multimodal runner is wired in this exact order:
1. `GitHub Models` via `GITHUB_TOKEN` with default model `gpt-4o`
2. `Gemini` via `GEMINI_API_KEY` with default model `gemini-2.5-flash`
3. `OpenRouter` via `OPENROUTER_API_KEY` with default model `openai/gpt-4o-mini`

You can override the models with:
- `GITHUB_MODEL`
- `GEMINI_MODEL`
- `OPENROUTER_MODEL`

You can also tune the router with:
- `ORCH_ROW_DELAY_SECONDS` (default `3`)
- `ORCH_VISION_COOLDOWN_SECONDS` (default `15`)
- `ORCH_VISION_MAX_CYCLES` (default `2`)

### Minimal `.env` for this hackathon path

```bash
GITHUB_TOKEN=...
GITHUB_MODEL=gpt-4o

GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.5-flash

OPENROUTER_API_KEY=...
OPENROUTER_MODEL=openai/gpt-4o-mini

ORCH_ROW_DELAY_SECONDS=3
ORCH_VISION_COOLDOWN_SECONDS=15
ORCH_VISION_MAX_CYCLES=2
```

## My recommendation for you

For the first run after the prompt arrives:
1. place the official dataset under `challenge/current/dataset/`
2. use `./venv/bin/python -m hackerrank_orchestrator run-claims --contract challenge/current/contract.toml --max-rows 5`
3. inspect the generated `artifacts/runs/.../claim_reviews.jsonl`
4. only then run the full dataset

That is the safest path if you are trying to maximize score without burning time.
