# IDP-206: Textract Baseline Processor

## Purpose

This story establishes Amazon Textract `DetectDocumentText` as the conventional OCR baseline for the IDP proof of technology.

The baseline is intended to show:

- raw text recognition
- PAGE / LINE / WORD block structure
- confidence values
- printed vs handwriting classification
- geometry / coordinates
- parent-child relationships between blocks
- local response caching to avoid repeated paid OCR calls

This story does **not** yet perform:

- Magic 8 field extraction
- MR / NON MR / MR Plus classification
- FORMS or TABLES analysis
- accuracy benchmarking against Claude
- production workflow implementation

## Test Document

First test page:

`data/synthetic/cost_slice/01_clean_medical.png`

This is a synthetic typed medical encounter summary containing fictional data only. No PHI, PII, or employer documents were used.

## AWS / API Configuration

| Setting | Value |
|---|---|
| AWS profile | `idp-dev` |
| Region | `us-east-1` |
| Service | Amazon Textract |
| API operation | `DetectDocumentText` |
| Input | local image bytes sent directly through boto3 |

S3 was not used. Asynchronous Textract APIs were not used. `AnalyzeDocument`, FORMS, and TABLES were not used.

## Cache Design

The processor SHA-256 hashes the document bytes and builds a cache key containing:

- document SHA-256
- service = `textract`
- operation = `detect_document_text`

Observed cache key:

```text
sha256=1b663d6a4b2223060474e14d4647dae3c05a54c6c0aad9404d0e402bf17a1990|service=textract|operation=detect_document_text
```

Cache location:

```text
artifacts/cache/textract/detect_document_text/1b663d6a4b2223060474e14d4647dae3c05a54c6c0aad9404d0e402bf17a1990.json
```

Observed behavior:

- the first successful execution was a **CACHE MISS**
- Textract was invoked once
- the complete raw response was written to the local cache
- the second execution was a **CACHE HIT**
- the second execution made no AWS call
- failed Textract calls are not cached

## Baseline Result

Measured result for this one page:

| Metric | Value |
|---|---|
| DocumentMetadata.Pages | 1 |
| PAGE blocks | 1 |
| LINE blocks | 24 |
| WORD blocks | 92 |
| Average WORD confidence | 98.45 |
| PRINTED words | 92 |
| HANDWRITING words | 0 |

Manual inspection showed the visible typed content was recognized correctly on this clean synthetic page.

This is one page and is only a baseline smoke / structural test. It is not a statistically meaningful OCR accuracy result.

## Detected Text

Representative recognized text:

- `CEDAR HILL OUTPATIENT CLINIC`
- `Morgan Sampleton`
- `SYN-MBR-880214`
- `1979-11-04`
- `1999999992`
- `SYN-PRV-55201`
- `SYN-AUTH-77421`

The full raw Textract JSON is preserved in the cache file above and is not reproduced here.

## Textract Block Model

The cached response is a flat `Blocks` collection with a graph of IDs, not nested JSON. Observed structure:

`PAGE -> LINE -> WORD`

Representative IDs from this page:

- PAGE: `cd77242b-8a17-486d-a89d-a4ec26235d46`
- first LINE: `6237466b-9588-47f9-a663-12b38f2f5d65`
- first WORD: `62d468dc-cbd8-491e-ab04-353cd03edc43`

Each block has its own `Id`. `Relationships` connect blocks through those IDs. The PAGE lists the LINE as a CHILD. The LINE lists WORD blocks as CHILD relationships.

```text
PAGE
  |
  +-- CHILD --> LINE
                  |
                  +-- CHILD --> WORD
                  +-- CHILD --> WORD
                  +-- CHILD --> WORD
```

## Geometry

Textract geometry uses normalized page coordinates from 0 to 1.

Representative WORD `SYNTHETIC`:

- Left approximately 0.0568
- Top approximately 0.0069
- Width approximately 0.0882
- Height approximately 0.0109
- RotationAngle: 0.0

That word begins about 5.7% from the left side of the page and about 0.7% from the top.

Geometry matters for downstream IDP because it supports:

- locating evidence in the original document
- highlighting detected values
- reconstructing layout
- page-and-coordinate workflows

## Confidence and Text Type

Observed representative values:

- LINE confidence: `89.2833`
- WORD confidence: `99.8039`
- WORD TextType: `PRINTED`

Confidence exists at multiple block levels and should not be treated as a single document-level truth. `TextType` is how Textract distinguishes printed text from handwriting.

## Key Learning

OCR and IDP are not the same step.

Textract `DetectDocumentText` answers:

> What text is on this page, where is it, and how confident is the OCR engine?

It does not yet answer:

> Which detected value is the member name, NPI, date of service, or other business field?

Richer IDP capability adds semantic meaning on top of OCR structure:

```text
Pixels
  ->
OCR structure
  ->
document graph
  ->
semantic extraction
  ->
business meaning
```

## Preliminary Conclusion

IDP-206 established a working Textract OCR baseline with:

- authenticated boto3 access
- successful `DetectDocumentText`
- raw response preservation
- SHA-256-based local caching
- PAGE / LINE / WORD traversal
- confidence inspection
- geometry inspection
- printed / handwriting metadata

The clean typed page produced high-confidence OCR. No broader quality conclusion should be drawn until degraded, handwritten, and representative benchmark pages are evaluated.

## Next Steps

1. Reuse the cached baseline in later evaluation work.
2. Expand testing to degraded and handwritten synthetic documents.
3. Build the preprocessing / degradation pipeline.
4. Define the reusable processor/result contract.
5. Add field-level evaluation after the Magic 8 schema and gold set are finalized.
