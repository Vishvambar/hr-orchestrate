# Evaluation Folder

This folder exists because the HackerRank Orchestrate prompt for **Multi-Modal Evidence Review** explicitly requires an `evaluation/` directory inside `code.zip`.

## What should live here during the hackathon

- scripts or notebooks used to evaluate `dataset/sample_claims.csv`
- lightweight fixture CSVs or notes for manual checks
- the final `evaluation_report.md`
- any helper documentation for reproducing the evaluation

## Expected workflow

1. Run the claim-review pipeline against `dataset/sample_claims.csv`:

   ```bash
   python code/evaluation/main.py
   ```

   For a quick smoke test:

   ```bash
   python code/evaluation/main.py --max-rows 3
   ```

2. Save predictions under a run directory in `code/artifacts/runs/` and mirror sample predictions to `code/evaluation/sample_predictions.csv`.
3. Compare predictions with the labeled sample CSV using the built-in evaluator.
4. Update `evaluation/evaluation_report.md` with field-level metrics and operational analysis.

## Recommended checks for this challenge

- exact / normalized match for scalar fields
- set comparison for `risk_flags`
- set comparison for `supporting_image_ids`
- row-order / identity consistency checks
- counts of image-processing failures or manual-review fallbacks

## Notes

Do not store bulky challenge datasets or large generated artifacts inside `evaluation/`; keep those in the official dataset location and `artifacts/runs/`.
