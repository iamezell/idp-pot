from __future__ import annotations

import hashlib
import os
from pathlib import Path

import boto3
from dotenv import load_dotenv

from idp_pot.processor_result import ProcessorResult
from idp_pot.textract_detect import (
    inspect_response,
    obtain_detect_document_text,
)

PROCESSOR_NAME = "textract_detect_document_text"


def map_textract_to_result(
    *,
    document_sha256: str,
    response: dict | None,
    cache_status: str,
    region: str,
    latency_ms: int | None,
    error: str | None = None,
) -> ProcessorResult:
    """Map DetectDocumentText output onto ProcessorResult. No field extraction."""
    if error or response is None:
        return ProcessorResult(
            processor_name=PROCESSOR_NAME,
            model_id=None,
            document_sha256=document_sha256,
            success=False,
            error=error or "missing Textract response",
            metadata={
                "service": "textract",
                "operation": "detect_document_text",
                "region": region,
                "cache_status": cache_status,
            },
        )

    stats = inspect_response(response)
    return ProcessorResult(
        processor_name=PROCESSOR_NAME,
        model_id=None,
        document_sha256=document_sha256,
        success=True,
        document_type=None,
        fields=None,
        raw_text="\n".join(stats["line_text"]),
        confidence=stats["avg_word_confidence"],
        latency_ms=latency_ms,
        input_tokens=None,
        output_tokens=None,
        total_tokens=None,
        error=None,
        metadata={
            "service": "textract",
            "operation": "detect_document_text",
            "region": region,
            "cache_status": cache_status,
            "page_count": stats["page_count"],
            "line_count": stats["line_count"],
            "word_count": stats["word_count"],
            "printed_count": stats["printed_count"],
            "handwriting_count": stats["handwriting_count"],
            "document_metadata_pages": stats["pages_meta"],
        },
    )


class TextractDocumentProcessor:
    """Reusable DetectDocumentText processor. Reuses the IDP-206 SHA-256 cache."""

    def __init__(
        self,
        profile: str | None = None,
        region: str | None = None,
        *,
        textract_client=None,
        cache_root: Path | None = None,
    ) -> None:
        load_dotenv()
        self.profile = profile or os.getenv("AWS_PROFILE", "idp-dev")
        self.region = region or os.getenv("AWS_REGION", "us-east-1")
        self.cache_root = cache_root
        if textract_client is not None:
            self._textract = textract_client
        else:
            session = boto3.Session(
                profile_name=self.profile,
                region_name=self.region,
            )
            self._textract = session.client("textract")

    def process(self, image_path: str | Path) -> ProcessorResult:
        path = Path(image_path)
        if not path.is_file():
            return ProcessorResult(
                processor_name=PROCESSOR_NAME,
                model_id=None,
                document_sha256=None,
                success=False,
                error=f"missing image: {path}",
            )

        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        response, cache_status, error, latency_ms = obtain_detect_document_text(
            path,
            self._textract,
            cache_root=self.cache_root,
        )
        return map_textract_to_result(
            document_sha256=digest,
            response=response,
            cache_status=cache_status,
            region=self.region,
            latency_ms=latency_ms,
            error=error,
        )
