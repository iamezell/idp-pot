import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from idp_pot.bedrock_processor import BedrockDocumentProcessor

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCUMENT_PATH = (
    REPO_ROOT / "data" / "synthetic" / "cost_slice" / "01_clean_medical.png"
)
MODEL_ID = "us.anthropic.claude-sonnet-4-6"


def main() -> int:
    load_dotenv()
    if not DOCUMENT_PATH.is_file():
        print(f"ERROR: missing document {DOCUMENT_PATH}", file=sys.stderr)
        return 1

    processor = BedrockDocumentProcessor(
        model_id=MODEL_ID,
        profile=os.getenv("AWS_PROFILE", "idp-dev"),
        region=os.getenv("AWS_REGION", "us-east-1"),
    )
    result = processor.process(DOCUMENT_PATH)

    print(f"success: {result.success}")
    print(f"processor_name: {result.processor_name}")
    print(f"model_id: {result.model_id}")
    print(f"document_sha256: {result.document_sha256}")
    print(f"document_type: {result.document_type}")
    print("fields:")
    print(json.dumps(result.fields, indent=2))
    print(f"input_tokens: {result.input_tokens}")
    print(f"output_tokens: {result.output_tokens}")
    print(f"total_tokens: {result.total_tokens}")
    print(f"latency_ms: {result.latency_ms}")
    if result.error:
        print(f"error: {result.error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
