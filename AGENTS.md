# AGENTS.md

This workspace is optimized for **HackerRank Orchestrate**.
If your AI coding tool supports `AGENTS.md`, follow these rules.

## Goals

Optimize for the public Orchestrate rubric:
- clear architecture and engineering hygiene
- grounded answers from the provided corpus only
- explicit escalation logic for risky or unsupported cases
- deterministic, reproducible runs
- interview-ready decisions that the user can explain

## Mandatory transcript logging

Append every session and meaningful turn summary to:
- Linux/macOS: `~/hackerrank_orchestrator/log.txt`
- Windows: `%USERPROFILE%\\hackerrank_orchestrator\\log.txt`

Create the parent directory if it does not exist.
Keep the file append-only.
Never log secrets; redact keys and tokens.

Recommended entry format:

```text
## [ISO-8601 TIMESTAMP] <short title>

User Prompt:
<verbatim prompt with secrets redacted>

Assistant Summary:
<2-5 sentences on what changed and why>

Actions:
- <files edited>
- <commands run>
```

## Working rules

1. Prefer minimal, explainable architecture over framework-heavy abstractions.
2. Keep the solution terminal-friendly.
3. Use local corpus evidence, not live web knowledge, for challenge answers.
4. Save run artifacts: output CSV, manifest, retrieval evidence, and a run transcript.
5. Put secrets in environment variables only.
6. After significant changes, run the demo or tests if possible.

## Where to look first

1. `README.md`
2. `docs/orchestrate-research.md`
3. `docs/hackathon-playbook.md`
4. `docs/adaptation-guide.md`
