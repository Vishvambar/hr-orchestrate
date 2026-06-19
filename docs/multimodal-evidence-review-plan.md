# Multi-Modal Evidence Review Plan

This problem is different from the earlier text-only starter: the **images are the primary source of truth**.

## What matters most

1. Parse the actual claim from the conversation.
2. Review the submitted images with a vision-capable model.
3. Use `evidence_requirements.csv` to decide whether the image set is sufficient.
4. Use `user_history.csv` only for risk context.
5. Produce deterministic final CSV rows with exact allowed labels.

## Recommended architecture

```text
claims.csv row
  -> split image paths / image ids
  -> parse claim text heuristically
  -> join user_history.csv
  -> filter evidence_requirements.csv
  -> multimodal review call (images + row context)
  -> deterministic post-processing
  -> output.csv + run artifacts + evaluation report
```

## Important design rule

Do not let the model invent the final row unchecked.
Use the model for:
- image interpretation
- visual issue detection
- image quality assessment
- supporting image selection

Use deterministic Python logic for:
- allowed-label normalization
- set formatting
- final fallback behavior
- history-based risk flags
- conservative handling of missing/weak evidence

## Model selection note

For this challenge, a text-only model is not enough.
If your current provider/model cannot take image input, use it only for text parsing or not at all.

## Required artifacts

- `output.csv`
- `evaluation/` folder
- `evaluation/evaluation_report.md`
- run manifest and run transcript
- chat transcript

## Strong default fallback behavior

If images are missing, unreadable, or ambiguous:
- `valid_image=false`
- `evidence_standard_met=false`
- `claim_status=not_enough_information`
- include conservative `risk_flags`

This is usually safer than hallucinating damage.
