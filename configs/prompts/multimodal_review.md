Task summary:
{task_summary}

Claim row:
{row_json}

Parsed claim guess:
{claim_parse_json}

User history context:
{history_json}

Relevant evidence requirements:
{requirements_text}

Review all provided images and return one JSON object with these keys:
- evidence_standard_met
- evidence_standard_met_reason
- risk_flags
- issue_type
- object_part
- claim_status
- claim_status_justification
- supporting_image_ids
- valid_image
- severity

Constraints:
- `risk_flags` must be an array of allowed flags or ["none"]
- `supporting_image_ids` must be an array of image IDs or ["none"]
- `claim_status` must be one of supported, contradicted, not_enough_information
- `valid_image` and `evidence_standard_met` must be booleans
- Cross-reference evidence_requirements against the images to evaluate evidence_standard_met.
- Check for consistency across all provided images (e.g. same vehicle).
- Ground the decision in visible evidence from the images.
