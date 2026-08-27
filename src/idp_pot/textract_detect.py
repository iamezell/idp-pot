"""IDP-206 DetectDocumentText helpers: cache + inspect. Not a framework."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from botocore.exceptions import BotoCoreError, ClientError

REPO_ROOT = Path(__file__).resolve().parents[2]
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


def cache_path_for(digest: str, cache_root: Path | None = None) -> Path:
    root = cache_root if cache_root is not None else CACHE_ROOT
    return root / SERVICE / OPERATION / f"{digest}.json"


def load_cached(path: Path) -> dict | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def persist_cache(path: Path, response: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(response, indent=2) + "\n", encoding="utf-8")


def blocks_of_type(blocks: list[dict], block_type: str) -> list[dict]:
    return [block for block in blocks if block.get("BlockType") == block_type]


def inspect_response(response: dict) -> dict:
    blocks = response.get("Blocks") or []
    page_blocks = blocks_of_type(blocks, "PAGE")
    line_blocks = blocks_of_type(blocks, "LINE")
    word_blocks = blocks_of_type(blocks, "WORD")
    confidences = [
        float(block["Confidence"])
        for block in word_blocks
        if "Confidence" in block
    ]
    return {
        "pages_meta": (response.get("DocumentMetadata") or {}).get("Pages"),
        "page_count": len(page_blocks),
        "line_count": len(line_blocks),
        "word_count": len(word_blocks),
        "avg_word_confidence": (
            sum(confidences) / len(confidences) if confidences else None
        ),
        "printed_count": sum(
            1 for block in word_blocks if block.get("TextType") == "PRINTED"
        ),
        "handwriting_count": sum(
            1 for block in word_blocks if block.get("TextType") == "HANDWRITING"
        ),
        "line_text": [line.get("Text", "") for line in line_blocks],
    }


def print_summary(document_path: Path, response: dict) -> None:
    stats = inspect_response(response)
    print(f"Document: {document_path}")
    print(f"DocumentMetadata.Pages: {stats['pages_meta']}")
    print(f"PAGE blocks: {stats['page_count']}")
    print(f"LINE blocks: {stats['line_count']}")
    print(f"WORD blocks: {stats['word_count']}")
    if stats["avg_word_confidence"] is None:
        print("Average WORD confidence: n/a")
    else:
        print(f"Average WORD confidence: {stats['avg_word_confidence']:.2f}")
    print(f"PRINTED words: {stats['printed_count']}")
    print(f"HANDWRITING words: {stats['handwriting_count']}")
    print("LINE text (Textract order):")
    for line in stats["line_text"]:
        print(line)


def format_aws_error(error: Exception) -> str:
    if isinstance(error, ClientError):
        aws_error = error.response.get("Error", {})
        code = aws_error.get("Code", type(error).__name__)
        message = aws_error.get("Message", str(error))
        return f"{code}: {message}"
    return f"{type(error).__name__}: {error}"


def obtain_detect_document_text(
    document_path: Path,
    textract,
    cache_root: Path | None = None,
) -> tuple[dict | None, str, str | None, int | None]:
    document_bytes = document_path.read_bytes()
    digest = hashlib.sha256(document_bytes).hexdigest()
    cache_key = f"sha256={digest}|service={SERVICE}|operation={OPERATION}"
    cached_path = cache_path_for(digest, cache_root)
    print(f"Cache key: {cache_key}")
    print(f"Cache file: {cached_path}")

    cached = load_cached(cached_path)
    if cached is not None:
        print("CACHE HIT — returning cached Textract response (no AWS call)")
        return cached, "HIT", None, None

    print("CACHE MISS — invoking Textract DetectDocumentText once")
    started = time.perf_counter()
    try:
        response = jsonable(
            textract.detect_document_text(Document={"Bytes": document_bytes})
        )
    except (BotoCoreError, ClientError) as error:
        return None, "FAILED", format_aws_error(error), None
    latency_ms = int(round((time.perf_counter() - started) * 1000))

    persist_cache(cached_path, response)
    print(f"Cached raw response: {cached_path}")
    return response, "MISS", None, latency_ms
