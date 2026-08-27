# IDP-208: Textract Processor / Canonical Contract Integration

## Purpose

IDP-208 wraps the working Amazon Textract `DetectDocumentText` baseline from IDP-206 in a reusable `TextractDocumentProcessor` that returns the IDP-207 `ProcessorResult`.

```text
BedrockDocumentProcessor ──┐
                           ├──> ProcessorResult
TextractDocumentProcessor ─┘
```

This is integration/refactoring so both processors can feed a future evaluation harness. It is not a production framework.

`ProcessorResult` is the POT's internal application contract. It is not the native Amazon Textract response schema. The complete native Textract JSON remains in the local raw-response cache.

## Public interface

```python
processor = TextractDocumentProcessor(profile="idp-dev", region="us-east-1")
result = processor.process(image_path)  # -> ProcessorResult
```

Same shape as `BedrockDocumentProcessor.process(...)`. No abstract base class.

## Mapping to ProcessorResult

| Field | Value |
|---|---|
| processor_name | `textract_detect_document_text` |
| model_id | `None` |
| document_sha256 | SHA-256 of original document bytes (same as the cache key) |
| success | `True` if a Textract response came from AWS or cache |
| document_type | `None` — DetectDocumentText does not classify |
| fields | `None` — no Magic 8 extraction |
| raw_text | LINE text in Textract order, joined with newlines |
| confidence | average WORD confidence (same formula as IDP-206) |
| latency_ms | measured API time on CACHE MISS; `None` on CACHE HIT |
| input/output/total tokens | `None` |

`document_type` and `fields` stay `None` on purpose. OCR is not semantic extraction. Nearby labels such as `Member Name:` / `Morgan Sampleton` are left in `raw_text` only.

Textract-specific counts live in `metadata`:

- service / operation / region
- cache_status (`HIT` or `MISS`)
- page_count, line_count, word_count
- printed_count, handwriting_count
- document_metadata_pages

Full `Blocks` are not copied into `metadata`.

## Cache

Unchanged IDP-206 behavior:

- SHA-256 of document bytes
- key: `sha256=...\|service=textract\|operation=detect_document_text`
- path: `artifacts/cache/textract/detect_document_text/<sha256>.json`
- CACHE HIT: no AWS call
- CACHE MISS: one `DetectDocumentText` call, then persist
- failures are not cached

The clean medical page is already cached and should be a HIT.

## Smoke test

```bash
uv run python scripts/textract_processor_smoke.py
```

Uses `data/synthetic/cost_slice/01_clean_medical.png`. Expected: CACHE HIT, no paid Textract call.

## Boundaries

This story does not:

- build the evaluation harness
- extract Magic 8 fields
- classify MR / NON-MR / MR Plus
- score accuracy
- use AnalyzeDocument, FORMS, TABLES, or async Textract
- add S3, Lambda, Step Functions, or IAM changes
- rerun the degradation slice, Bedrock, or the frozen cost experiment
