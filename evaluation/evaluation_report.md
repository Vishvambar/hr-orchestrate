# Evaluation Report — Multi-Modal Evidence Review

Update this file during the hackathon before packaging your submission.

## 1. System summary

- Primary model/provider:
- Backup model/provider:
- Images as primary evidence: yes
- User history used only for risk context: yes
- Evidence requirements used in decisioning: yes

## 2. Evaluation data

- Sample CSV path:
- Number of sample rows evaluated:
- Number of images processed for sample evaluation:
- Any excluded / unreadable images:

## 3. Field-level quality

Fill in after running on `dataset/sample_claims.csv`.

| Field | Metric | Notes |
| --- | --- | --- |
| `evidence_standard_met` |  |  |
| `risk_flags` |  | compare as sets |
| `issue_type` |  |  |
| `object_part` |  |  |
| `claim_status` |  |  |
| `supporting_image_ids` |  | compare as sets |
| `valid_image` |  |  |
| `severity` |  |  |

## 4. Biggest observed failure modes

1.
2.
3.

## 5. Operational analysis

Required by the prompt.

- Approximate number of model calls for sample processing:
- Approximate number of model calls for full test processing:
- Approximate input tokens per row:
- Approximate output tokens per row:
- Number of images processed:
- Pricing assumptions:
- Approximate cost for full test run:
- Approximate latency / runtime:
- TPM / RPM considerations:
- Batching / throttling / caching / retry strategy:

## 6. Final decision notes

- Why this architecture was chosen:
- What tradeoff was intentionally made:
- What would be improved with more time:
