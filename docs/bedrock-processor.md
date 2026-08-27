# Bedrock Document Processor

## Purpose

This story turns the working Bedrock Converse cost-slice call into reusable POT plumbing.

Claude document processing is no longer trapped in smoke-test or cost-experiment scripts. Later evaluation can call one processor and get one result shape.

This is **not** a production framework, plugin system, or evaluation harness.

## What shipped

- Canonical internal result: `ProcessorResult` in `src/idp_pot/processor_result.py`
- Reusable processor: `BedrockDocumentProcessor` in `src/idp_pot/bedrock_processor.py`
- Shared frozen extraction prompt/schema: `src/idp_pot/extraction_prompt.py`
- One-page smoke script: `scripts/bedrock_processor_smoke.py`
- Local unit tests (no AWS): SHA-256, media type, JSON parse, result construction

Public interface:

```python
processor = BedrockDocumentProcessor(model_id)
result = processor.process(image_path)  # -> ProcessorResult
```

Model ID is supplied at construction. Tested IDs remain:

- `us.anthropic.claude-haiku-4-5-20251001-v1:0`
- `us.anthropic.claude-sonnet-4-6`
- `us.anthropic.claude-opus-4-6-v1`

This story invoked **Sonnet 4.6 only** for the smoke test.

## Result contract

`ProcessorResult` carries processor name, model ID, document SHA-256, success, document type, extracted fields, raw text, confidence, latency, token counts, error, and metadata.

Fields that a processor does not produce stay `None`. Bedrock fills token counts; Textract would not. Textract was **not** migrated onto this contract in this story.

## What this does not do

- evaluation harness
- accuracy / precision / recall / F1
- Magic 8 scoring against a gold set
- prompt tuning
- retries
- S3 or new AWS infrastructure
- rerunning the frozen three-model cost slice

The cost-slice script and artifacts were left unchanged. The shared prompt is a copy of that frozen prompt.

## Smoke test

Document: `data/synthetic/cost_slice/01_clean_medical.png`  
Profile / region: `idp-dev` / `us-east-1`  
API: Bedrock Converse, local image bytes, JSON-only extraction schema

Observed result:

| Item | Value |
|---|---|
| success | True |
| processor_name | `bedrock_converse` |
| model_id | `us.anthropic.claude-sonnet-4-6` |
| document_type | `medical` |
| input / output / total tokens | 1464 / 234 / 1698 |
| latency_ms | 4467 |

Extracted fields included member name, member number, DOB, DOS start/end, NPI, provider number, and authorization number. This is one clean synthetic page, not a quality benchmark.

## Next steps

1. Wrap Textract in the same `ProcessorResult` contract.
2. Point evaluation at `processor.process(...)` instead of one-off scripts.
3. Add field-level scoring after the Magic 8 schema and gold set are finalized.
