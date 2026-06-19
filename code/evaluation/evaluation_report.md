# Evaluation Report — Multi-Modal Evidence Review

Auto-generated summary from the latest run. Update manually if you want more narrative detail before submission.

## 1. System summary

- Primary provider actually used: github_models
- Successful providers: github_models
- Images as primary evidence: yes
- User history used only for risk context: yes
- Evidence requirements used in decisioning: yes

## 2. Evaluation data

- Sample CSV path: ../dataset/sample_claims.csv
- Number of rows processed in this run: 4
- Number of images processed in this run: 2
- Any rows without usable images: 0

## 3. Field-level quality

| Field | Exact Accuracy | Normalized Accuracy |
| --- | --- | --- |
| `claim_object` | 1.0 | 1.0 |
| `claim_status` | 0.5 | 0.5 |
| `claim_status_justification` | 0.0 | 0.0 |
| `evidence_standard_met` | 0.5 | 0.5 |
| `evidence_standard_met_reason` | 0.0 | 0.0 |
| `image_paths` | 0.0 | 0.0 |
| `issue_type` | 0.0 | 0.0 |
| `object_part` | 0.5 | 0.5 |
| `risk_flags` | 0.25 | 0.25 |
| `severity` | 0.25 | 0.25 |
| `supporting_image_ids` | 0.0 | 0.0 |
| `user_claim` | 0.0 | 0.0 |
| `user_id` | 0.5 | 0.5 |
| `valid_image` | 0.75 | 0.75 |

## 4. Operational analysis

- Approximate number of model calls for sample + test processing in this run: 2
- Approximate input tokens observed or estimated: 1329
- Approximate output tokens observed or estimated: 170
- Number of images processed: 2
- Approximate runtime: 15.77 seconds
- Provider attempts by name: {
  "gemini": 1,
  "github_models": 1
}
- Pricing assumptions: fill in with your chosen provider's current pricing before final submission.
- TPM/RPM considerations: sequential failover with per-row delay and bounded retries.
- Batching / throttling / caching / retry strategy: one multimodal review call per row, sequential provider failover, bounded cooldown and conservative fallback.

## 5. Final decision notes

- Why this architecture was chosen: image-first prompt with deterministic post-processing and provider failover.
- What tradeoff was intentionally made: reliability and schema control were prioritized over aggressive parallelism.
- What would be improved with more time: task-specific image adjudication and richer per-field calibration.
