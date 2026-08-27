from idp_pot.evaluation import evaluate_result, normalize_date, normalize_field
from idp_pot.processor_result import ProcessorResult

GROUND_TRUTH = {
    "document_id": "01_clean_medical",
    "filename": "01_clean_medical.png",
    "document_type": "medical",
    "fields": {
        "member_name": "Morgan Sampleton",
        "member_number": "SYN-MBR-880214",
        "dob": "1979-11-04",
        "npi": "1999999992",
    },
}


def _bedrock_result(**overrides) -> ProcessorResult:
    values = dict(
        processor_name="bedrock_converse",
        model_id="us.anthropic.claude-sonnet-4-6",
        document_sha256="abc",
        success=True,
        document_type="medical",
        fields={
            "member_name": "Morgan Sampleton",
            "member_number": "SYN-MBR-880214",
            "dob": "1979-11-04",
            "npi": "1999999992",
        },
    )
    values.update(overrides)
    return ProcessorResult(**values)


def test_exact_string_match() -> None:
    row = evaluate_result(_bedrock_result(), GROUND_TRUTH)
    assert row.exact_field_matches == 4
    assert row.field_match_rate == 1.0
    assert row.mismatched_fields == []
    assert row.missing_fields == []


def test_whitespace_normalization() -> None:
    row = evaluate_result(
        _bedrock_result(fields={"member_name": "  Morgan Sampleton  ", "member_number": "SYN-MBR-880214", "dob": "1979-11-04", "npi": "1999999992"}),
        GROUND_TRUTH,
    )
    assert row.exact_field_matches == 4


def test_date_normalization() -> None:
    assert normalize_date("11/04/1979") == "1979-11-04"
    assert normalize_date("11/4/1979") == "1979-11-04"
    assert normalize_date("1979-11-04") == "1979-11-04"
    row = evaluate_result(
        _bedrock_result(fields={"member_name": "Morgan Sampleton", "member_number": "SYN-MBR-880214", "dob": "11/4/1979", "npi": "1999999992"}),
        GROUND_TRUTH,
    )
    assert row.exact_field_matches == 4


def test_identifier_normalization() -> None:
    assert normalize_field("npi", "1999 999 992") == "1999999992"
    assert normalize_field("member_number", " SYN-MBR-880214 ") == "SYN-MBR-880214"
    row = evaluate_result(
        _bedrock_result(
            fields={
                "member_name": "Morgan Sampleton",
                "member_number": "SYN-MBR-880214",
                "dob": "1979-11-04",
                "npi": "1999 999992",
            }
        ),
        GROUND_TRUTH,
    )
    assert row.exact_field_matches == 4


def test_mismatch_detection() -> None:
    row = evaluate_result(
        _bedrock_result(fields={"member_name": "Wrong Name", "member_number": "SYN-MBR-880214", "dob": "1979-11-04", "npi": "1999999992"}),
        GROUND_TRUTH,
    )
    assert row.exact_field_matches == 3
    assert row.mismatched_fields[0]["field"] == "member_name"
    assert row.field_match_rate == 0.75


def test_missing_field_detection() -> None:
    row = evaluate_result(
        _bedrock_result(fields={"member_name": "Morgan Sampleton", "member_number": "SYN-MBR-880214", "dob": "1979-11-04"}),
        GROUND_TRUTH,
    )
    assert "npi" in row.missing_fields
    assert row.exact_field_matches == 3


def test_document_type_comparison() -> None:
    match = evaluate_result(_bedrock_result(), GROUND_TRUTH)
    assert match.document_type_match is True
    miss = evaluate_result(_bedrock_result(document_type="invoice"), GROUND_TRUTH)
    assert miss.document_type_match is False


def test_textract_semantic_scoring_not_applicable() -> None:
    result = ProcessorResult(
        processor_name="textract_detect_document_text",
        model_id=None,
        document_sha256="abc",
        success=True,
        document_type=None,
        fields=None,
        raw_text="Member Name:\nMorgan Sampleton",
        confidence=98.45,
        metadata={"cache_status": "HIT", "line_count": 24},
    )
    row = evaluate_result(result, GROUND_TRUTH)
    assert row.semantic_field_scoring == "not_applicable"
    assert row.exact_field_matches is None
    assert row.field_match_rate is None
    assert row.document_type_match is None
    assert row.missing_fields == []
    assert row.confidence == 98.45


def test_failed_processor_result() -> None:
    result = _bedrock_result(success=False, fields=None, error="AccessDenied")
    row = evaluate_result(result, GROUND_TRUTH)
    assert row.processor_success is False
    assert row.exact_field_matches == 0
    assert row.field_match_rate == 0.0
    assert "npi" in row.missing_fields
    assert row.error == "AccessDenied"


def test_field_match_rate_calculation() -> None:
    row = evaluate_result(
        _bedrock_result(
            fields={
                "member_name": "Morgan Sampleton",
                "member_number": "SYN-MBR-880214",
                "dob": "wrong",
                "npi": None,
            }
        ),
        GROUND_TRUTH,
    )
    assert row.exact_field_matches == 2
    assert row.field_match_rate == 0.5
    assert "npi" in row.missing_fields
    assert any(item["field"] == "dob" for item in row.mismatched_fields)
