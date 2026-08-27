import hashlib
import json
import os
import sys
from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCUMENT_PATH = (
    REPO_ROOT / "data" / "synthetic" / "cost_slice" / "01_clean_medical.png"
)
CACHE_ROOT = REPO_ROOT / "artifacts" / "cache"
SERVICE = "textract"
OPERATION = "detect_document_text"


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


def cache_path_for(digest: str) -> Path:
    return CACHE_ROOT / SERVICE / OPERATION / f"{digest}.json"


def load_cached(path: Path) -> dict | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def persist_cache(path: Path, response: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(response, indent=2) + "\n", encoding="utf-8")


def blocks_of_type(blocks: list[dict], block_type: str) -> list[dict]:
    return [block for block in blocks if block.get("BlockType") == block_type]


def print_summary(document_path: Path, response: dict) -> None:
    blocks = response.get("Blocks") or []
    pages_meta = (response.get("DocumentMetadata") or {}).get("Pages")
    page_blocks = blocks_of_type(blocks, "PAGE")
    line_blocks = blocks_of_type(blocks, "LINE")
    word_blocks = blocks_of_type(blocks, "WORD")
    confidences = [
        float(block["Confidence"])
        for block in word_blocks
        if "Confidence" in block
    ]
    printed = sum(1 for block in word_blocks if block.get("TextType") == "PRINTED")
    handwriting = sum(
        1 for block in word_blocks if block.get("TextType") == "HANDWRITING"
    )
    avg_confidence = (
        sum(confidences) / len(confidences) if confidences else None
    )

    print(f"Document: {document_path}")
    print(f"DocumentMetadata.Pages: {pages_meta}")
    print(f"PAGE blocks: {len(page_blocks)}")
    print(f"LINE blocks: {len(line_blocks)}")
    print(f"WORD blocks: {len(word_blocks)}")
    if avg_confidence is None:
        print("Average WORD confidence: n/a")
    else:
        print(f"Average WORD confidence: {avg_confidence:.2f}")
    print(f"PRINTED words: {printed}")
    print(f"HANDWRITING words: {handwriting}")
    print("LINE text (Textract order):")
    for line in line_blocks:
        print(line.get("Text", ""))


def main() -> int:
    load_dotenv()

    profile = os.getenv("AWS_PROFILE", "idp-dev")
    region = os.getenv("AWS_REGION", "us-east-1")

    if not DOCUMENT_PATH.is_file():
        print(f"ERROR: missing document {DOCUMENT_PATH}", file=sys.stderr)
        return 1

    document_bytes = DOCUMENT_PATH.read_bytes()
    digest = hashlib.sha256(document_bytes).hexdigest()
    cache_key = (
        f"sha256={digest}|service={SERVICE}|operation={OPERATION}"
    )
    cached_path = cache_path_for(digest)

    print(f"AWS profile: {profile}")
    print(f"Region: {region}")
    print(f"Document: {DOCUMENT_PATH}")
    print(f"Cache key: {cache_key}")
    print(f"Cache file: {cached_path}")

    try:
        cached = load_cached(cached_path)
        if cached is not None:
            print("CACHE HIT — returning cached Textract response (no AWS call)")
            print_summary(DOCUMENT_PATH, cached)
            return 0

        print("CACHE MISS — invoking Textract DetectDocumentText once")
        session = boto3.Session(profile_name=profile, region_name=region)
        textract = session.client("textract")
        response = jsonable(
            textract.detect_document_text(Document={"Bytes": document_bytes})
        )
        persist_cache(cached_path, response)
        print(f"Cached raw response: {cached_path}")
        print_summary(DOCUMENT_PATH, response)
        return 0

    except (BotoCoreError, ClientError, OSError, KeyError, json.JSONDecodeError) as error:
        print(
            f"Textract DetectDocumentText: FAILED ({type(error).__name__}: {error})",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
