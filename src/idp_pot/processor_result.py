from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProcessorResult:
    """Canonical POT processor result. Unused fields stay None."""

    processor_name: str
    model_id: str | None
    document_sha256: str | None
    success: bool
    document_type: str | None = None
    fields: dict[str, Any] | None = None
    raw_text: str | None = None
    confidence: float | None = None
    latency_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
