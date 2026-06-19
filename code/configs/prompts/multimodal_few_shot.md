Few-shot examples from labeled sample claims. These are pattern examples only; do not copy image IDs or labels unless the current row's own images support them.

Example 1 — clear supported claim:
Input pattern: car claim says the rear bumper has a new dent; image clearly shows the rear bumper dent.
Output pattern:
{
  "evidence_standard_met": true,
  "evidence_standard_met_reason": "The relevant rear bumper is visible clearly enough to evaluate the claimed dent.",
  "risk_flags": ["none"],
  "issue_type": "dent",
  "object_part": "rear_bumper",
  "claim_status": "supported",
  "claim_status_justification": "The visible dent on the rear bumper matches the user's claimed damage.",
  "supporting_image_ids": ["img_1"],
  "valid_image": true,
  "severity": "medium"
}

Example 2 — not enough information due to visibility/mismatch:
Input pattern: user claims front bumper scratch, but the submitted evidence does not clearly show the claimed object/part or creates a mismatch.
Output pattern:
{
  "evidence_standard_met": false,
  "evidence_standard_met_reason": "The submitted images do not provide a reliable view of the claimed front bumper scratch.",
  "risk_flags": ["wrong_object", "claim_mismatch", "manual_review_required"],
  "issue_type": "unknown",
  "object_part": "front_bumper",
  "claim_status": "not_enough_information",
  "claim_status_justification": "The images do not provide enough usable visual evidence to verify the claimed bumper scratch.",
  "supporting_image_ids": ["none"],
  "valid_image": true,
  "severity": "unknown"
}

Example 3 — contradicted claim with risk context:
Input pattern: user claims one car part is severely damaged, but the images show a different visible issue or non-original/mismatched evidence; user history adds risk context.
Output pattern:
{
  "evidence_standard_met": true,
  "evidence_standard_met_reason": "The image set is clear enough to evaluate the relevant vehicle evidence, but it does not show the claimed damage as described.",
  "risk_flags": ["claim_mismatch", "user_history_risk", "manual_review_required"],
  "issue_type": "scratch",
  "object_part": "rear_bumper",
  "claim_status": "contradicted",
  "claim_status_justification": "The visible evidence contradicts the user's described damage; user history is noted as risk context but is not the basis for the contradiction.",
  "supporting_image_ids": ["img_1"],
  "valid_image": true,
  "severity": "low"
}

Formatting rules to copy from these examples:
- Use concise image-grounded reasons.
- Use `not_enough_information` when evidence is insufficient, not `supported` or `contradicted`.
- Use `user_history_risk` only as context, never as the sole reason to contradict a claim.
- Use only current-row image IDs in `supporting_image_ids`.
