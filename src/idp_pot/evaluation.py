"""Minimal field normalization and ProcessorResult scoring. Not a benchmark."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from idp_pot.evaluation_result import EvaluationResult
from idp_pot.processor_result import ProcessorResult

IDENTIFIER_FIELDS = {
    "member_number",
    "npi",
    "provider_number",
    "authorization_number",
}
DATE_FIELDS = {"dob", "dos_start", "dos_end"}
TEXTRACT_PROCESSOR = "textract_detect_document_text"
SEMANTIC_N_A = "not_applicable"
SEMANTIC_APPLICABLE = "applicable"


def normalize_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def normalize_identifier(value: Any) -> str | None:
    text = normalize_string(value)
    if text is None:
        return None
    return "".join(text.split())


def normalize_date(value: Any) -> str | None:
    """Normalize unambiguous dates to YYYY-MM-DD. Do not guess ambiguous values."""
    text = normalize_string(value)
    if text is None:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return text


def normalize_field(name: str, value: Any) -> str | None:
    if name in DATE_FIELDS:
        return normalize_date(value)
    if name in IDENTIFIER_FIELDS:
        return normalize_identifier(value)
    return normalize_string(value)


def load_ground_truth(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def evaluate_result(
    result: ProcessorResult,
    ground_truth: dict,
) -> EvaluationResult:
    expected_type = ground_truth.get("document_type")
    expected_fields: dict[str, Any] = ground_truth.get("fields") or {}
    document_id = ground_truth.get("document_id", "")
    filename = ground_truth.get("filename", "")

    actual_type = normalize_string(result.document_type)
    expected_type_norm = normalize_string(expected_type)
    type_match = (
        None
        if expected_type_norm is None
        else actual_type == expected_type_norm
    )

    base = dict(
        document_id=document_id,
        filename=filename,
        processor_name=result.processor_name,
        model_id=result.model_id,
        processor_success=result.success,
        expected_document_type=expected_type,
        actual_document_type=result.document_type,
        document_type_match=type_match,
        total_expected_fields=len(expected_fields),
        latency_ms=result.latency_ms,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        total_tokens=result.total_tokens,
        confidence=result.confidence,
        error=result.error,
        metadata=dict(result.metadata or {}),
    )

    if result.processor_name == TEXTRACT_PROCESSOR:
        base["document_type_match"] = None
        return EvaluationResult(
            **base,
            semantic_field_scoring=SEMANTIC_N_A,
            exact_field_matches=None,
            field_match_rate=None,
            notes=(
                "DetectDocumentText does not provide Magic 8 fields; "
                "semantic field scoring is not applicable."
            ),
        )

    if not result.success:
        return EvaluationResult(
            **base,
            semantic_field_scoring=SEMANTIC_APPLICABLE,
            exact_field_matches=0,
            field_match_rate=0.0,
            missing_fields=list(expected_fields),
            notes="processor failed; field comparison skipped beyond missing expected fields",
        )

    actual_fields = result.fields or {}
    matches = 0
    mismatched: list[dict[str, Any]] = []
    missing: list[str] = []

    for name, expected_value in expected_fields.items():
        expected_norm = normalize_field(name, expected_value)
        if name not in actual_fields or normalize_field(name, actual_fields.get(name)) is None:
            missing.append(name)
            continue
        actual_norm = normalize_field(name, actual_fields.get(name))
        if actual_norm == expected_norm:
            matches += 1
        else:
            mismatched.append(
                {
                    "field": name,
                    "expected": expected_norm,
                    "actual": actual_norm,
                }
            )

    unexpected = [
        name
        for name, value in actual_fields.items()
        if name not in expected_fields and normalize_field(name, value) is not None
    ]
    total = len(expected_fields)
    rate = (matches / total) if total else None

    return EvaluationResult(
        **base,
        semantic_field_scoring=SEMANTIC_APPLICABLE,
        exact_field_matches=matches,
        mismatched_fields=mismatched,
        missing_fields=missing,
        unexpected_fields=unexpected,
        field_match_rate=rate,
    )
