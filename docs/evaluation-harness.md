# IDP-209: Evaluation Harness Skeleton

## Purpose

IDP-209 adds a small evaluation harness that compares a canonical `ProcessorResult` to synthetic ground truth.

This is evaluation machinery only. It is not the final IDP benchmark or an accuracy claim.

> This is an evaluation harness skeleton using a small synthetic example. It is not the final IDP benchmark or an accuracy claim.

## How ProcessorResult feeds evaluation

Both `BedrockDocumentProcessor` and `TextractDocumentProcessor` already return `ProcessorResult`.

```text
document image
      ↓
Bedrock or Textract processor
      ↓
ProcessorResult
      ↓
evaluate_result(result, ground_truth)
      ↓
EvaluationResult
```

## Ground truth vs processor output

Initial ground truth is one clean synthetic page:

`data/ground_truth/01_clean_medical.json`

It records the expected document type `medical` and the eight fictional Magic 8 field values for `01_clean_medical.png`. It is not a gold set.

The harness compares that file to whatever the processor actually returned. It does not invent expected values at score time.

## Normalization

Before field comparison:

- strings: trim leading/trailing whitespace
- identifiers (`member_number`, `npi`, `provider_number`, `authorization_number`): trim and remove internal whitespace; hyphens are kept
- dates (`dob`, `dos_start`, `dos_end`): convert unambiguous `YYYY-MM-DD`, `MM/DD/YYYY`, and `M/D/YYYY` to ISO `YYYY-MM-DD`

Ambiguous dates are left unchanged and will not be forced equal.

## Semantic scoring (Bedrock)

For a semantic processor:

- compare `document_type`
- compare each expected field after normalization
- count exact matches
- record mismatches and missing fields
- `field_match_rate` = exact matches / expected field count

Extra schema keys with empty/null values are not treated as unexpected extractions. Non-empty extra keys are listed as unexpected.

## Textract scoring

`DetectDocumentText` does not classify documents or extract Magic 8 fields.

For `textract_detect_document_text`:

- `semantic_field_scoring` = `not_applicable`
- missing Magic 8 fields are **not** counted as extraction failures
- OCR confidence, raw-text line count, and cache status are preserved from `ProcessorResult`

That keeps OCR honest: Textract is not scored as a failed extractor of fields it never claimed to produce.

## First clean-page evaluation

Measured on `01_clean_medical.png`:

```text
Document: 01_clean_medical.png

Bedrock Sonnet 4.6
success: True
document_type_match: True
field_matches: 8/8
field_match_rate: 1.0

Textract DetectDocumentText
success: True
semantic_field_scoring: N/A
ocr_confidence: 98.45
raw_text_lines: 24
cache_status: HIT
```

Bedrock made one Sonnet Converse call. Textract was a CACHE HIT (no AWS call).

Machine-readable output: `artifacts/evaluation/01_clean_medical.json`

This is one synthetic page. It is not a quality claim.

## Current limitations

- one synthetic page
- no precision / recall / F1
- no degradation set
- no Haiku / Opus comparison
- no HEDIS or table scoring
- no gold set

## Next steps

1. Run the one-page script and record the measured `EvaluationResult`.
2. Expand ground truth only after the Magic 8 schema is stable.
3. Add degraded and handwritten pages later.
4. Add precision / recall / F1 only when the gold set exists.
