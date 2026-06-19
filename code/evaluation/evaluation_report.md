# Evaluation Report — Multi-Modal Evidence Review

Auto-generated summary from the latest run. Update manually if you want more narrative detail before submission.

## 1. System summary

- Primary provider actually used: groq_llama
- Successful providers: groq_llama, github_models, gemini, openrouter, groq_qwen
- Images as primary evidence: yes
- User history used only for risk context: yes
- Evidence requirements used in decisioning: yes

## 2. Evaluation data

- Sample CSV path: ../dataset/sample_claims.csv
- Number of rows processed in this run: 44
- Number of images processed in this run: 82
- Any rows without usable images: 6

## 3. Field-level quality

No labeled sample evaluation was available for this run.

## 4. Operational analysis

- Approximate number of model calls in this run: 110
- Approximate input tokens observed or estimated: 104995
- Approximate output tokens observed or estimated: 8096
- Number of images processed: 82
- Approximate runtime: 1200.12 seconds
- Provider attempts by name: {
  "gemini": 23,
  "github_models": 22,
  "groq_llama": 44,
  "groq_qwen": 8,
  "openrouter": 13
}
- Approximate cost for this run: $0.3434, assuming $2.50/1M input tokens and $10.00/1M output tokens. Actual cash cost may be $0 when the run stays within provider free quota.
- TPM/RPM considerations: sequential calls, row delay, bounded provider cycles, and no parallel fan-out to avoid free-tier spikes.
- Batching / throttling / caching / retry strategy: one multimodal review call per row, sequential provider failover, per-row checkpointing, resume-from-output, bounded cooldown, and conservative fallback.

## 5. Final decision notes

- Why this architecture was chosen: image-first prompt with deterministic post-processing and provider failover.
- What tradeoff was intentionally made: reliability and schema control were prioritized over aggressive parallelism.
- What would be improved with more time: task-specific image adjudication and richer per-field calibration.
