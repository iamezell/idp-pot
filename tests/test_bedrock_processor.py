import json
from dataclasses import asdict
from pathlib import Path

import pytest

from idp_pot.bedrock_processor import (
    detect_image_format,
    parse_model_json,
    sha256_bytes,
)
from idp_pot.processor_result import ProcessorResult


def test_sha256_generation() -> None:
    assert sha256_bytes(b"abc") == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )
    assert sha256_bytes(b"idp-pot") == sha256_bytes(b"idp-pot")
    assert sha256_bytes(b"idp-pot") != sha256_bytes(b"idp-pot-2")


def test_media_type_detection(tmp_path: Path) -> None:
    png = tmp_path / "page.png"
    jpeg = tmp_path / "page.jpeg"
    jpg = tmp_path / "page.jpg"
    other = tmp_path / "page.gif"
    for path in (png, jpeg, jpg, other):
        path.write_bytes(b"x")
    assert detect_image_format(png) == "png"
    assert detect_image_format(jpeg) == "jpeg"
    assert detect_image_format(jpg) == "jpeg"
    assert detect_image_format(other) is None


def test_parse_valid_model_json() -> None:
    payload = {
        "document_type": "medical",
        "fields": {"member_name": "Morgan Sampleton", "npi": None},
    }
    parsed = parse_model_json(json.dumps(payload))
    assert parsed["document_type"] == "medical"
    assert parsed["fields"]["member_name"] == "Morgan Sampleton"


def test_parse_fenced_model_json() -> None:
    text = """```json
{"document_type": "invoice", "fields": {"company": "ACME"}}
```"""
    parsed = parse_model_json(text)
    assert parsed["document_type"] == "invoice"
    assert parsed["fields"]["company"] == "ACME"


def test_parse_malformed_model_json() -> None:
    with pytest.raises(json.JSONDecodeError):
        parse_model_json("not-json {")


def test_processor_result_construction() -> None:
    result = ProcessorResult(
        processor_name="bedrock_converse",
        model_id="us.anthropic.claude-sonnet-4-6",
        document_sha256="abc123",
        success=True,
        document_type="medical",
        fields={"member_name": "Morgan Sampleton"},
        raw_text='{"document_type":"medical"}',
        confidence=None,
        latency_ms=1200,
        input_tokens=1464,
        output_tokens=234,
        total_tokens=1698,
        error=None,
        metadata={"stop_reason": "end_turn"},
    )
    dumped = asdict(result)
    assert dumped["processor_name"] == "bedrock_converse"
    assert dumped["success"] is True
    assert dumped["confidence"] is None
    assert dumped["fields"]["member_name"] == "Morgan Sampleton"
    assert dumped["metadata"]["stop_reason"] == "end_turn"
