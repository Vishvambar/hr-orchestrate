# Multi-Modal Claim Orchestrator 

An image-first, fault-tolerant pipeline that utilizes multi-modal LLMs to verify insurance damage claims. 

**The Engineering Challenge:** 
Processing high-resolution images through LLM APIs (Groq, Gemini, GPT-4o) frequently results in `413 Request Entity Too Large` crashes, `429 Rate Limit` blocks, and corrupted JSON outputs. 

**The Solution:**
This system introduces a robust **5-Layer Sequential Vision Router**. If a primary model (like Groq's Llama 4) fails due to rate limits or timeouts, the payload is dynamically intercepted, normalized (auto-downscaled via LANCZOS to sub-2MB), and seamlessly routed to the next available provider without dropping the process. 

Coupled with deterministic JSON brace-counting extraction and per-row checkpointing, this pipeline guarantees 100% completion of asynchronous visual data processing without data loss.

## Table of Contents

- [Approach Overview](#approach-overview)
- [Architecture](#architecture)
- [Setup Instructions](#setup-instructions)
- [How to Run](#how-to-run)
- [Project Structure](#project-structure)
- [Configuration Reference](#configuration-reference)
- [Design Decisions](#design-decisions)
- [Evaluation & Operational Analysis](#evaluation--operational-analysis)

---

## Approach Overview

Each claim row consists of one or more images, a customer–support conversation, optional user history, and a set of minimum evidence requirements. The system processes every row through the following pipeline:

1. **Claim Extraction** — Parse the `user_claim` conversation to identify the reported damage type and the object part involved.
2. **Evidence Requirement Matching** — Look up the relevant `evidence_requirements.csv` entries for the claim's `claim_object` and damage type.
3. **Image Preprocessing** — Normalize image formats (AVIF-in-JPEG detection, format conversion) and automatically downscale any image exceeding 2 MB to 1024×1024 using LANCZOS resampling to prevent `413 Request Entity Too Large` API errors.
4. **Multimodal Vision Review** — Send the system prompt, review prompt (containing the conversation, evidence requirements, and user history context), and all images to a vision-capable LLM. The model returns a structured JSON verdict.
5. **Deterministic Post-Processing** — Normalize every output field against the allowed value lists defined in the contract. Enforce business rules (e.g., severity must be `unknown` when `claim_status` is `not_enough_information`; `supporting_image_ids` must be `none` when claim is contradicted).
6. **Per-Row Checkpointing** — Write each completed row to `output.csv` immediately, enabling safe resume if the process is interrupted.

### Key Principles

- **Images are the primary source of truth.** The LLM is instructed to ground every decision in what is visually observable.
- **User history adds risk context only.** It must never override clear visual evidence.
- **Prompt injection defense.** The system prompt explicitly instructs the model to ignore any text or instructions embedded within images.
- **Conservative fallback.** If all API providers fail for a row, the system emits a safe `not_enough_information` verdict rather than crashing.

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    main.py (CLI Entry)                    │
│  Reads dataset CSVs, builds TOML contract, invokes       │
│  the claim review pipeline                               │
└──────────────────────┬───────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────┐
│             claim_review_pipeline.py                      │
│  For each row:                                           │
│    1. Build prompt from templates + row data              │
│    2. Resolve image paths                                 │
│    3. Call SequentialVisionRouter                          │
│    4. Normalize + validate output fields                  │
│    5. Checkpoint row to output.csv                        │
└──────────────────────┬───────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────┐
│         SequentialVisionRouter (vision_failover.py)       │
│                                                          │
│  5-Layer Provider Fallback Chain:                         │
│                                                          │
│   ┌─────────────┐   ┌──────────────┐   ┌──────────────┐ │
│   │ 1. Groq     │──▸│ 2. Gemini    │──▸│ 3. GitHub    │ │
│   │ Llama Scout │   │ 2.5 Flash    │   │ GPT-4o       │ │
│   └─────────────┘   └──────────────┘   └──────────────┘ │
│          │                                    │          │
│          ▼                                    ▼          │
│   ┌──────────────┐              ┌──────────────────┐     │
│   │ 4. OpenRouter│◂─────────────│ 5. Groq Qwen 3.6 │     │
│   │ Gemma        │              │ (last resort)     │     │
│   └──────────────┘              └──────────────────┘     │
│                                                          │
│  On 429/413/timeout: catch → log attempt → next provider │
│  On full cycle exhaust: cooldown → retry cycle            │
└──────────────────────┬───────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────┐
│                  image_utils.py                           │
│  - AVIF/WebP → JPEG conversion with caching              │
│  - Auto-downscale images > 2 MB (LANCZOS, 1024×1024)     │
│  - Base64 encoding for API payloads                       │
└──────────────────────────────────────────────────────────┘
```

---

## Setup Instructions

### Prerequisites

- Python 3.10 or later
- `pip` package manager
- At least one vision-capable API key (see below)

### 1. Clone and enter the repository

```bash
git clone https://github.com/Vishvambar/hr-orchestrate.git
cd hr-orchestrate
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv venv
source venv/bin/activate        # Linux / macOS
# venv\Scripts\activate         # Windows
```

### 3. Install dependencies

```bash
pip install -r code/requirements.txt
```

Dependencies are minimal by design:

| Package              | Purpose                                              |
|----------------------|------------------------------------------------------|
| `openai>=1.93.0`     | OpenAI-compatible SDK for GitHub Models & OpenRouter  |
| `pillow>=10.0.0`     | Image resizing and format conversion                  |
| `pillow-avif-plugin` | AVIF format support for mislabeled image containers   |

> **Note:** The Groq SDK (`groq`) and Google Gemini API are called via their respective native HTTP clients and do not require additional pip packages beyond those listed above.

### 4. Configure API keys

Copy the example environment file and fill in your keys:

```bash
cp code/.env.example code/.env
```

Edit `code/.env` with at least one provider:

```env
# Primary — Groq (free tier, 500k TPD)
GROQ_API_KEY=gsk_your_key_here

# Secondary — Google Gemini (free tier)
GEMINI_API_KEY=your_key_here

# Tertiary — GitHub Models (free tier)
GITHUB_TOKEN=your_token_here

# Quaternary — OpenRouter (free tier)
OPENROUTER_API_KEY=your_key_here

# Provider execution order (left = highest priority)
ORCH_PROVIDER_ORDER=groq_llama,gemini,github_models,openrouter,groq_qwen

# Rate-limit mitigation
ORCH_ROW_DELAY_SECONDS=5
ORCH_RESUME_OUTPUT=true
```

### 5. Place the dataset

Ensure the `dataset/` directory is at the repository root:

```
.
├── dataset/
│   ├── claims.csv              # or test.csv
│   ├── sample_claims.csv       # labeled sample for local evaluation
│   ├── user_history.csv
│   ├── evidence_requirements.csv
│   └── images/
│       ├── sample/case_001/...
│       └── test/case_001/...
└── code/
    ├── main.py
    └── ...
```

---

## How to Run

### Full evaluation (all 44 test rows)

```bash
python code/main.py --output output.csv
```

### Limit to N rows (for testing)

```bash
python code/main.py --output output.csv --max-rows 5
```

### Resume an interrupted run

The pipeline automatically detects existing rows in `output.csv` and skips them:

```bash
# If the process was interrupted at row 20, just re-run:
python code/main.py --output output.csv
# → resumes from row 21
```

### Sample evaluation (labeled data)

```bash
python code/evaluation/main.py --output code/evaluation/sample_predictions.csv
```

### Output

- **`output.csv`** — Predictions for all rows with the 14 required columns
- **`artifacts/runs/<timestamp>/`** — Run logs, manifest, resolved contract, and per-row JSONL

---

## Project Structure

```
code/
├── main.py                          # CLI entrypoint
├── README.md                        # This file
├── requirements.txt                 # Python dependencies
├── .env.example                     # Template for API keys
│
├── configs/
│   └── prompts/
│       ├── multimodal_system.md     # System prompt (rules, injection defense)
│       ├── multimodal_review.md     # Per-row review prompt template
│       ├── multimodal_verify.md     # Verification prompt (unused, reserved)
│       └── multimodal_few_shot.md   # Few-shot examples (optional)
│
├── src/claim_orchestrator/
│   ├── claim_review_pipeline.py     # Main pipeline loop
│   ├── claim_review_config.py       # TOML contract loader
│   ├── vision_failover.py           # 5-layer provider router
│   ├── image_utils.py               # Image preprocessing & downscaling
│   ├── multimodal_helpers.py        # Prompt builder & output normalizer
│   ├── multimodal_evaluation.py     # Set-aware field evaluation
│   ├── artifacts.py                 # Run artifact management
│   └── utils.py                     # Stable JSON serialization
│
├── evaluation/
│   ├── main.py                      # Sample evaluation runner
│   ├── experiment_loop.py           # Prompt/parameter experiments
│   └── evaluation_report.md         # Operational analysis
│
└── docs/
    └── interview_cheatsheet.md      # AI Judge interview preparation
```

---

## Configuration Reference

| Environment Variable            | Default                                     | Description                                                         |
|---------------------------------|---------------------------------------------|---------------------------------------------------------------------|
| `GROQ_API_KEY`                  | —                                           | Groq API key for Llama and Qwen models                              |
| `GEMINI_API_KEY`                | —                                           | Google AI Studio API key                                            |
| `GITHUB_TOKEN`                  | —                                           | GitHub personal access token for GPT-4o                             |
| `OPENROUTER_API_KEY`            | —                                           | OpenRouter API key for Gemma and other models                       |
| `ORCH_PROVIDER_ORDER`           | `groq_llama,gemini,github_models,openrouter,groq_qwen` | Comma-separated failover priority                    |
| `ORCH_ROW_DELAY_SECONDS`       | `5`                                         | Delay between rows to respect RPM limits                            |
| `ORCH_VISION_COOLDOWN_SECONDS` | `15`                                        | Wait time after a full provider cycle fails before retrying         |
| `ORCH_VISION_MAX_CYCLES`       | `2`                                         | Maximum retry cycles through the entire provider list               |
| `ORCH_RESUME_OUTPUT`           | `true`                                      | Skip already-completed rows in `output.csv`                         |
| `ORCH_IMAGE_DETAIL`            | `auto`                                      | Image detail level sent to OpenAI-compatible providers              |

---

## Design Decisions

### Why 5 providers instead of 1?

Free-tier API limits are strict (Groq: 500k tokens/day, Gemini: 20 RPM, GitHub: rate-limited). A single provider would fail partway through the 44-row dataset. The sequential router guarantees that if one provider hits its limit, the next one picks up seamlessly — no data loss, no crashes.

### Why Llama 4 Scout as primary?

We tested Qwen 3.6 27B first. While its analysis quality was high, it generated excessive `<think>` reasoning tokens that consumed the 1200-token output budget and truncated the JSON response. Llama 4 Scout produces clean, structured JSON without chain-of-thought overhead, making it the ideal primary.

### Why auto-downscale images?

Row 43 in the test dataset contains high-resolution images exceeding 2 MB. Without downscaling, every provider rejects the payload with a `413 Request Entity Too Large` error. The LANCZOS downscaler (1024×1024, quality 85) preserves enough visual detail for damage assessment while keeping payloads under API limits.

### Why brace-counting JSON extraction?

LLMs occasionally wrap JSON in markdown code fences, prepend reasoning text, or produce partial outputs. The brace-counting parser (`_parse_json_object`) reliably extracts the JSON object regardless of surrounding noise, making the pipeline robust against inconsistent model output formatting.

### Why per-row checkpointing?

A 44-row run takes ~20 minutes on free-tier APIs with rate-limit delays. If the process is interrupted at row 30, per-row checkpointing ensures rows 1–30 are preserved and the next run resumes from row 31 — no wasted API calls.

---

## Evaluation & Operational Analysis

See [`evaluation/evaluation_report.md`](evaluation/evaluation_report.md) for full operational metrics including:

- Token usage estimates (~105k input, ~8k output across 44 rows)
- Provider attempt distribution (Groq Llama: 44, Gemini: 23, GitHub: 22, OpenRouter: 13, Groq Qwen: 8)
- Approximate runtime (~20 minutes with rate-limit delays)
- Cost analysis ($0.00 actual on free tiers; $0.34 theoretical at paid rates)

### Output Schema

| Column                         | Type     | Example Values                              |
|--------------------------------|----------|---------------------------------------------|
| `user_id`                      | string   | `user_001`                                  |
| `image_paths`                  | string   | `images/test/case_001/img_1.jpg`            |
| `user_claim`                   | string   | Conversation transcript                     |
| `claim_object`                 | enum     | `car`, `laptop`, `package`                  |
| `evidence_standard_met`        | boolean  | `true`, `false`                             |
| `evidence_standard_met_reason` | string   | Free-text reasoning                         |
| `risk_flags`                   | set      | `none`, `blurry_image;user_history_risk`    |
| `issue_type`                   | enum     | `dent`, `scratch`, `crack`, `unknown`       |
| `object_part`                  | enum     | `front_bumper`, `screen`, `box`, `unknown`  |
| `claim_status`                 | enum     | `supported`, `contradicted`, `not_enough_information` |
| `claim_status_justification`   | string   | Image-grounded explanation                  |
| `supporting_image_ids`         | set      | `img_1`, `img_1;img_2`, `none`              |
| `valid_image`                  | boolean  | `true`, `false`                             |
| `severity`                     | enum     | `low`, `medium`, `high`, `unknown`, `none`  |
