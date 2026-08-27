import hashlib
from pathlib import Path

from botocore.exceptions import ClientError

from idp_pot.textract_detect import inspect_response, persist_cache
from idp_pot.textract_processor import (
    TextractDocumentProcessor,
    map_textract_to_result,
)

SAMPLE_RESPONSE = {
    "DocumentMetadata": {"Pages": 1},
    "Blocks": [
        {"BlockType": "PAGE", "Id": "page-1"},
        {"BlockType": "LINE", "Id": "line-1", "Text": "Member Name:"},
        {"BlockType": "LINE", "Id": "line-2", "Text": "Morgan Sampleton"},
        {
            "BlockType": "WORD",
            "Id": "word-1",
            "Text": "Member",
            "TextType": "PRINTED",
            "Confidence": 99.0,
        },
        {
            "BlockType": "WORD",
            "Id": "word-2",
            "Text": "Name",
            "TextType": "PRINTED",
            "Confidence": 97.0,
        },
        {
            "BlockType": "WORD",
            "Id": "word-3",
            "Text": "Morgan",
            "TextType": "HANDWRITING",
            "Confidence": 91.0,
        },
    ],
}


class BoomTextract:
    def detect_document_text(self, **kwargs):
        raise AssertionError("DetectDocumentText must not be called")


class FailingTextract:
    def detect_document_text(self, **kwargs):
        raise ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "denied"}},
            "DetectDocumentText",
        )


def test_inspect_block_counts_and_confidence() -> None:
    stats = inspect_response(SAMPLE_RESPONSE)
    assert stats["page_count"] == 1
    assert stats["line_count"] == 2
    assert stats["word_count"] == 3
    assert stats["printed_count"] == 2
    assert stats["handwriting_count"] == 1
    assert stats["avg_word_confidence"] == (99.0 + 97.0 + 91.0) / 3
    assert stats["line_text"] == ["Member Name:", "Morgan Sampleton"]
    assert stats["pages_meta"] == 1


def test_map_textract_to_processor_result() -> None:
    result = map_textract_to_result(
        document_sha256="abc",
        response=SAMPLE_RESPONSE,
        cache_status="HIT",
        region="us-east-1",
        latency_ms=None,
    )
    assert result.success is True
    assert result.processor_name == "textract_detect_document_text"
    assert result.model_id is None
    assert result.document_type is None
    assert result.fields is None
    assert result.input_tokens is None
    assert result.output_tokens is None
    assert result.total_tokens is None
    assert result.raw_text == "Member Name:\nMorgan Sampleton"
    assert result.confidence == (99.0 + 97.0 + 91.0) / 3
    assert result.latency_ms is None
    assert result.metadata["cache_status"] == "HIT"
    assert result.metadata["page_count"] == 1
    assert result.metadata["word_count"] == 3
    assert result.metadata["printed_count"] == 2
    assert result.metadata["handwriting_count"] == 1
    assert "member_name" not in (result.fields or {})


def test_cache_hit_does_not_invoke_textract(tmp_path: Path) -> None:
    image = tmp_path / "page.png"
    image.write_bytes(b"fake-png-bytes")
    digest = hashlib.sha256(image.read_bytes()).hexdigest()
    persist_cache(
        tmp_path / "textract" / "detect_document_text" / f"{digest}.json",
        SAMPLE_RESPONSE,
    )
    processor = TextractDocumentProcessor(
        region="us-east-1",
        textract_client=BoomTextract(),
        cache_root=tmp_path,
    )
    result = processor.process(image)
    assert result.success is True
    assert result.metadata["cache_status"] == "HIT"
    assert result.latency_ms is None
    assert result.document_type is None
    assert result.fields is None


def test_failure_produces_unsuccessful_result(tmp_path: Path) -> None:
    image = tmp_path / "page.png"
    image.write_bytes(b"fake-png-bytes")
    processor = TextractDocumentProcessor(
        region="us-east-1",
        textract_client=FailingTextract(),
        cache_root=tmp_path,
    )
    result = processor.process(image)
    assert result.success is False
    assert result.error is not None
    assert "AccessDeniedException" in result.error
    assert result.document_type is None
    assert result.fields is None
    assert result.metadata["cache_status"] == "FAILED"


def test_missing_image_failure(tmp_path: Path) -> None:
    processor = TextractDocumentProcessor(
        region="us-east-1",
        textract_client=BoomTextract(),
        cache_root=tmp_path,
    )
    result = processor.process(tmp_path / "missing.png")
    assert result.success is False
    assert result.document_sha256 is None
    assert "missing image" in result.error
