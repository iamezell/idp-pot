# Frozen extraction/classification prompt from the successful cost-slice experiment.
# Do not tune this prompt here; the cost-slice script keeps its own copy unchanged.

EXTRACTION_PROMPT = """Classify this document page and extract visible fields.
Return JSON only, with no markdown or extra text, in this shape:
{
  "document_type": "medical | invoice | other",
  "fields": {
    "member_name": null,
    "member_number": null,
    "dob": null,
    "dos_start": null,
    "dos_end": null,
    "npi": null,
    "provider_number": null,
    "authorization_number": null,
    "company": null,
    "invoice_number": null,
    "invoice_date": null,
    "bill_to": null,
    "subtotal": null,
    "tax": null,
    "total": null,
    "po_number": null,
    "payment_terms": null
  }
}
Use null for any field that is not present. Do not invent values."""
