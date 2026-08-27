import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

from dotenv import load_dotenv

from idp_pot.bedrock_processor import BedrockDocumentProcessor
from idp_pot.evaluation import evaluate_result, load_ground_truth
from idp_pot.evaluation_result import EvaluationResult
from idp_pot.textract_processor import TextractDocumentProcessor

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCUMENT_PATH = (
    REPO_ROOT / "data" / "synthetic" / "cost_slice" / "01_clean_medical.png"
)
GROUND_TRUTH_PATH = REPO_ROOT / "data" / "ground_truth" / "01_clean_medical.json"
OUT_DIR = REPO_ROOT / "artifacts" / "evaluation"
SONNET_ID = "us.anthropic.claude-sonnet-4-6"


def print_bedrock(row: EvaluationResult) -> None:
    print("Bedrock Sonnet 4.6")
    print(f"success: {row.processor_success}")
    print(f"document_type_match: {row.document_type_match}")
    total = row.total_expected_fields
    matches = row.exact_field_matches
    print(f"field_matches: {matches}/{total}")
    print(f"field_match_rate: {row.field_match_rate}")
    if row.mismatched_fields:
        print(f"mismatched_fields: {row.mismatched_fields}")
    if row.missing_fields:
        print(f"missing_fields: {row.missing_fields}")
    if row.error:
        print(f"error: {row.error}")


def print_textract(row: EvaluationResult) -> None:
    print("Textract DetectDocumentText")
    print(f"success: {row.processor_success}")
    print(f"semantic_field_scoring: N/A")
    confidence = row.confidence
    if confidence is None:
        print("ocr_confidence: None")
    else:
        print(f"ocr_confidence: {confidence:.2f}")
    raw_lines = (row.metadata or {}).get("line_count")
    print(f"raw_text_lines: {raw_lines}")
    print(f"cache_status: {(row.metadata or {}).get('cache_status')}")
    if row.error:
        print(f"error: {row.error}")


def main() -> int:
    load_dotenv()
    if not DOCUMENT_PATH.is_file():
        print(f"ERROR: missing document {DOCUMENT_PATH}", file=sys.stderr)
        return 1
    if not GROUND_TRUTH_PATH.is_file():
        print(f"ERROR: missing ground truth {GROUND_TRUTH_PATH}", file=sys.stderr)
        return 1

    ground_truth = load_ground_truth(GROUND_TRUTH_PATH)
    profile = os.getenv("AWS_PROFILE", "idp-dev")
    region = os.getenv("AWS_REGION", "us-east-1")

    bedrock = BedrockDocumentProcessor(
        model_id=SONNET_ID, profile=profile, region=region
    )
    textract = TextractDocumentProcessor(profile=profile, region=region)

    rows = [
        evaluate_result(bedrock.process(DOCUMENT_PATH), ground_truth),
        evaluate_result(textract.process(DOCUMENT_PATH), ground_truth),
    ]

    print(f"Document: {DOCUMENT_PATH.name}")
    print()
    print_bedrock(rows[0])
    print()
    print_textract(rows[1])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUT_DIR / "01_clean_medical.json"
    json_path.write_text(
        json.dumps([asdict(row) for row in rows], indent=2) + "\n",
        encoding="utf-8",
    )
    print()
    print(f"JSON: {json_path}")
    return 0 if all(row.processor_success for row in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
