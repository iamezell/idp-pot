from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvaluationResult:
    """One-document comparison of ProcessorResult vs synthetic ground truth."""

    document_id: str
    filename: str
    processor_name: str
    model_id: str | None
    processor_success: bool
    expected_document_type: str | None
    actual_document_type: str | None
    document_type_match: bool | None
    semantic_field_scoring: str
    total_expected_fields: int
    exact_field_matches: int | None
    mismatched_fields: list[dict[str, Any]] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    unexpected_fields: list[str] = field(default_factory=list)
    field_match_rate: float | None = None
    latency_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    confidence: float | None = None
    error: str | None = None
    notes: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
