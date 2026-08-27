from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv

from idp_pot.extraction_prompt import EXTRACTION_PROMPT
from idp_pot.processor_result import ProcessorResult

PROCESSOR_NAME = "bedrock_converse"
IMAGE_FORMATS = {".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg"}
MAX_TOKENS = 512


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def detect_image_format(path: Path) -> str | None:
    return IMAGE_FORMATS.get(path.suffix.lower())


def parse_model_json(text: str) -> dict:
    """Parse model JSON, including optional markdown fences. Does not retry."""
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    parsed = json.loads(stripped)
    if not isinstance(parsed, dict):
        raise ValueError("model JSON must be an object")
    return parsed


def format_aws_error(error: Exception) -> str:
    if isinstance(error, ClientError):
        aws_error = error.response.get("Error", {})
        code = aws_error.get("Code", type(error).__name__)
        message = aws_error.get("Message", str(error))
        return f"{code}: {message}"
    return f"{type(error).__name__}: {error}"


def _output_text(response: dict) -> str:
    return "".join(
        block.get("text", "")
        for block in response.get("output", {}).get("message", {}).get("content", [])
    )


class BedrockDocumentProcessor:
    """Reusable Converse-based document processor. Not a production framework."""

    def __init__(
        self,
        model_id: str,
        profile: str | None = None,
        region: str | None = None,
    ) -> None:
        load_dotenv()
        self.model_id = model_id
        self.profile = profile or os.getenv("AWS_PROFILE", "idp-dev")
        self.region = region or os.getenv("AWS_REGION", "us-east-1")
        session = boto3.Session(
            profile_name=self.profile,
            region_name=self.region,
        )
        self._bedrock = session.client("bedrock-runtime")

    def process(self, image_path: str | Path) -> ProcessorResult:
        path = Path(image_path)
        if not path.is_file():
            return ProcessorResult(
                processor_name=PROCESSOR_NAME,
                model_id=self.model_id,
                document_sha256=None,
                success=False,
                error=f"missing image: {path}",
            )

        image_bytes = path.read_bytes()
        digest = sha256_bytes(image_bytes)
        image_format = detect_image_format(path)
        if image_format is None:
            return ProcessorResult(
                processor_name=PROCESSOR_NAME,
                model_id=self.model_id,
                document_sha256=digest,
                success=False,
                error=f"unsupported image format: {path.suffix}",
                metadata={"path": str(path)},
            )

        try:
            response = self._bedrock.converse(
                modelId=self.model_id,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "image": {
                                    "format": image_format,
                                    "source": {"bytes": image_bytes},
                                }
                            },
                            {"text": EXTRACTION_PROMPT},
                        ],
                    }
                ],
                inferenceConfig={"maxTokens": MAX_TOKENS},
            )
        except (BotoCoreError, ClientError) as error:
            return ProcessorResult(
                processor_name=PROCESSOR_NAME,
                model_id=self.model_id,
                document_sha256=digest,
                success=False,
                error=format_aws_error(error),
                metadata={
                    "path": str(path),
                    "image_format": image_format,
                    "profile": self.profile,
                    "region": self.region,
                },
            )

        usage = response.get("usage") or {}
        raw_text = _output_text(response)
        metadata = {
            "path": str(path),
            "image_format": image_format,
            "stop_reason": response.get("stopReason"),
            "profile": self.profile,
            "region": self.region,
        }

        try:
            parsed = parse_model_json(raw_text)
        except (json.JSONDecodeError, ValueError) as error:
            return ProcessorResult(
                processor_name=PROCESSOR_NAME,
                model_id=self.model_id,
                document_sha256=digest,
                success=False,
                raw_text=raw_text,
                latency_ms=(response.get("metrics") or {}).get("latencyMs"),
                input_tokens=usage.get("inputTokens"),
                output_tokens=usage.get("outputTokens"),
                total_tokens=usage.get("totalTokens"),
                error=f"malformed model JSON: {error}",
                metadata=metadata,
            )

        fields = parsed.get("fields")
        if fields is not None and not isinstance(fields, dict):
            fields = None

        return ProcessorResult(
            processor_name=PROCESSOR_NAME,
            model_id=self.model_id,
            document_sha256=digest,
            success=True,
            document_type=parsed.get("document_type"),
            fields=fields,
            raw_text=raw_text,
            latency_ms=(response.get("metrics") or {}).get("latencyMs"),
            input_tokens=usage.get("inputTokens"),
            output_tokens=usage.get("outputTokens"),
            total_tokens=usage.get("totalTokens"),
            metadata=metadata,
        )
