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

## My recommendation for you

For the first run after the prompt arrives:
1. use `rule-based`
2. lock the contract
3. inspect retrieval
4. only then switch to `compat` or `auto`

That is the safest path if you are trying to maximize score without burning time.
