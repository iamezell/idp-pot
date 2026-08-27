import csv
import hashlib
import json
import os
import sys
from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv
from PIL import Image

# Confirmed in this account/region via list-foundation-models /
# list-inference-profiles. Base model IDs are INFERENCE_PROFILE-only.
# US geo profiles only; do not use global.* IDs.
MODELS = {
    "claude_sonnet_4_6": "us.anthropic.claude-sonnet-4-6",
    "claude_haiku_4_5": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    "claude_opus_4_6": "us.anthropic.claude-opus-4-6-v1",
}

# Additional models only. Do not re-invoke or overwrite Sonnet 4.6 results.
RUN_MODELS = ("claude_haiku_4_5", "claude_opus_4_6")

REPO_ROOT = Path(__file__).resolve().parents[1]
SLICE_DIR = REPO_ROOT / "data" / "synthetic" / "cost_slice"
MANIFEST_PATH = SLICE_DIR / "manifest.json"
OUT_DIR = REPO_ROOT / "artifacts" / "cost_slice"
IMAGE_FORMATS = {".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg"}

CSV_FIELDS = [
    "page_id",
    "filename",
    "model_id",
    "sha256",
    "image_width",
    "image_height",
    "file_size_bytes",
    "inputTokens",
    "outputTokens",
    "totalTokens",
    "latencyMs",
    "stopReason",
    "success",
]

# Frozen: identical extraction/classification prompt for every page/model.
PROMPT = """Classify this document page and extract visible fields.
Return JSON only, with no markdown or extra text, in this shape:
{
  "document_type": "medical | invoice | other",
  "fields": {
    "member_name": null,
    "member_number": null,
    "dob": null,
    "dos_start": null,
    "dos_end": null,
    "npi": null,
    "provider_number": null,
    "authorization_number": null,
    "company": null,
    "invoice_number": null,
    "invoice_date": null,
    "bill_to": null,
    "subtotal": null,
    "tax": null,
    "total": null,
    "po_number": null,
    "payment_terms": null
  }
}
Use null for any field that is not present. Do not invent values."""


def image_stats(image_path: Path) -> dict:
    if not image_path.is_file():
        return {
            "image_width": None,
            "image_height": None,
            "file_size_bytes": None,
        }
    with Image.open(image_path) as img:
        width, height = img.size
    return {
        "image_width": width,
        "image_height": height,
        "file_size_bytes": image_path.stat().st_size,
    }


def jsonable(value):
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [jsonable(item) for item in value]
    if isinstance(value, bytes):
        return {"bytes_len": len(value)}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def format_aws_error(error: Exception) -> str:
    if isinstance(error, ClientError):
        aws_error = error.response.get("Error", {})
        code = aws_error.get("Code", type(error).__name__)
        message = aws_error.get("Message", str(error))
        return f"{code}: {message}"
    return f"{type(error).__name__}: {error}"


def empty_record(
    page: dict,
    image_path: Path,
    model_id: str,
    digest: str | None,
    error: str,
) -> dict:
    return {
        "page_id": page["page_id"],
        "filename": page["filename"],
        "model_id": model_id,
        "sha256": digest,
        **image_stats(image_path),
        "inputTokens": None,
        "outputTokens": None,
        "totalTokens": None,
        "latencyMs": None,
        "stopReason": None,
        "success": False,
        "error": error,
        "image_path": str(image_path),
        "raw_response": None,
    }


def invoke_page(bedrock, page: dict, model_id: str) -> dict:
    image_path = SLICE_DIR / page["filename"]
    if not image_path.is_file():
        return empty_record(
            page, image_path, model_id, None, f"missing image: {image_path}"
        )

    suffix = image_path.suffix.lower()
    if suffix not in IMAGE_FORMATS:
        return empty_record(
            page,
            image_path,
            model_id,
            None,
            f"unsupported image format: {suffix}",
        )

    image_bytes = image_path.read_bytes()
    digest = hashlib.sha256(image_bytes).hexdigest()

    try:
        response = bedrock.converse(
            modelId=model_id,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "image": {
                                "format": IMAGE_FORMATS[suffix],
                                "source": {"bytes": image_bytes},
                            }
                        },
                        {"text": PROMPT},
                    ],
                }
            ],
            inferenceConfig={"maxTokens": 512},
        )
    except (BotoCoreError, ClientError) as error:
        return empty_record(
            page, image_path, model_id, digest, format_aws_error(error)
        )

    usage = response.get("usage") or {}
    return {
        "page_id": page["page_id"],
        "filename": page["filename"],
        "model_id": model_id,
        "sha256": digest,
        **image_stats(image_path),
        "inputTokens": usage.get("inputTokens"),
        "outputTokens": usage.get("outputTokens"),
        "totalTokens": usage.get("totalTokens"),
        "latencyMs": (response.get("metrics") or {}).get("latencyMs"),
        "stopReason": response.get("stopReason"),
        "success": True,
        "error": None,
        "image_path": str(image_path),
        "raw_response": jsonable(response),
    }


def write_outputs(records: list[dict], slug: str) -> tuple[Path, Path]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    jsonl_path = OUT_DIR / f"{slug}.jsonl"
    csv_path = OUT_DIR / f"{slug}.csv"

    with jsonl_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for record in records:
            writer.writerow({field: record.get(field) for field in CSV_FIELDS})

    return jsonl_path, csv_path


def run_model(bedrock, pages: list[dict], slug: str, model_id: str) -> list[dict]:
    print(f"Model: {slug} ({model_id})")
    records = []
    for page in pages:
        print(f"Invoking {page['page_id']} ({page['filename']}) ...")
        record = invoke_page(bedrock, page, model_id)
        records.append(record)
        if record["success"]:
            print(
                f"  ok  inputTokens={record['inputTokens']}  "
                f"outputTokens={record['outputTokens']}  "
                f"totalTokens={record['totalTokens']}  "
                f"latencyMs={record['latencyMs']}"
            )
            continue

        print(
            f"  FAILED {page['page_id']}: {record['error']}",
            file=sys.stderr,
        )
        remaining = [item["page_id"] for item in pages[len(records) :]]
        if remaining:
            print(
                f"  stopping {slug}; skipped remaining pages: {', '.join(remaining)}",
                file=sys.stderr,
            )
        break
    return records


def main() -> int:
    load_dotenv()

    profile = os.getenv("AWS_PROFILE", "idp-dev")
    region = os.getenv("AWS_REGION", "us-east-1")

    if not MANIFEST_PATH.is_file():
        print(f"ERROR: missing manifest {MANIFEST_PATH}", file=sys.stderr)
        return 1

    pages = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    session = boto3.Session(profile_name=profile, region_name=region)
    bedrock = session.client("bedrock-runtime")

    print(f"AWS profile: {profile}")
    print(f"Region: {region}")
    print(f"Pages: {len(pages)}")
    print("Skipping claude_sonnet_4_6 (existing results preserved)")

    exit_code = 0
    for slug in RUN_MODELS:
        model_id = MODELS[slug]
        records = run_model(bedrock, pages, slug, model_id)
        jsonl_path, csv_path = write_outputs(records, slug)
        failed = sum(1 for record in records if not record["success"])
        print(f"JSONL: {jsonl_path}")
        print(f"CSV: {csv_path}")
        print(f"{slug}: {len(records) - failed} ok, {failed} failed")
        if failed:
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
