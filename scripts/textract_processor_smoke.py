import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from idp_pot.textract_processor import TextractDocumentProcessor

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCUMENT_PATH = (
    REPO_ROOT / "data" / "synthetic" / "cost_slice" / "01_clean_medical.png"
)


def main() -> int:
    load_dotenv()
    if not DOCUMENT_PATH.is_file():
        print(f"ERROR: missing document {DOCUMENT_PATH}", file=sys.stderr)
        return 1

    processor = TextractDocumentProcessor(
        profile=os.getenv("AWS_PROFILE", "idp-dev"),
        region=os.getenv("AWS_REGION", "us-east-1"),
    )
    result = processor.process(DOCUMENT_PATH)
    line_count = 0 if result.raw_text is None else len(result.raw_text.splitlines())
    cache_status = (result.metadata or {}).get("cache_status")

    print(f"success: {result.success}")
    print(f"processor_name: {result.processor_name}")
    print(f"model_id: {result.model_id}")
    print(f"document_sha256: {result.document_sha256}")
    print(f"document_type: {result.document_type}")
    print(f"fields: {result.fields}")
    print(f"confidence: {result.confidence}")
    print(f"raw_text_line_count: {line_count}")
    print(f"latency_ms: {result.latency_ms}")
    print(f"input_tokens: {result.input_tokens}")
    print(f"output_tokens: {result.output_tokens}")
    print(f"total_tokens: {result.total_tokens}")
    print(f"cache_status: {cache_status}")
    print(f"metadata: {result.metadata}")
    if result.error:
        print(f"error: {result.error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
