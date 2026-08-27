"""Cost summary from existing cost-slice JSONL + dated pricing config.

Does not invoke Bedrock. Does not modify measured result files.
"""

from __future__ import annotations

import csv
import json
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PRICING_PATH = REPO_ROOT / "config" / "bedrock_pricing_2026-08-26.json"
OUT_DIR = REPO_ROOT / "artifacts" / "cost_slice"

MILLION = Decimal("1000000")
EXTRAPOLATION_NOTE = (
    "Simple linear extrapolation from a five-page synthetic cost slice, "
    "not a production forecast."
)


def money(value: Decimal, places: str) -> str:
    return str(value.quantize(Decimal(places), rounding=ROUND_HALF_EVEN))


def page_cost(input_tokens: int, output_tokens: int, rates: dict) -> Decimal:
    return (
        Decimal(input_tokens) / MILLION * Decimal(str(rates["input_price_per_1m"]))
        + Decimal(output_tokens) / MILLION * Decimal(str(rates["output_price_per_1m"]))
    )


def load_records(path: Path) -> list[dict]:
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def summarize_model(slug: str, spec: dict) -> dict:
    jsonl_path = REPO_ROOT / spec["result_jsonl"]
    records = load_records(jsonl_path)
    if not records:
        raise ValueError(f"no records in {jsonl_path}")

    costs = [
        page_cost(rec["inputTokens"], rec["outputTokens"], spec) for rec in records
    ]
    page_count = len(records)
    total_input = sum(rec["inputTokens"] for rec in records)
    total_output = sum(rec["outputTokens"] for rec in records)
    total_tokens = sum(rec["totalTokens"] for rec in records)
    total_latency = sum(rec["latencyMs"] for rec in records)
    experiment_cost = sum(costs, Decimal("0"))
    avg_cost = experiment_cost / Decimal(page_count)

    return {
        "model_slug": slug,
        "display_name": spec["display_name"],
        "model_id": spec["model_id"],
        "page_count": page_count,
        "avg_input_tokens_per_page": total_input / page_count,
        "avg_output_tokens_per_page": total_output / page_count,
        "avg_total_tokens_per_page": total_tokens / page_count,
        "avg_latency_ms_per_page": total_latency / page_count,
        "avg_cost_usd_per_page": money(avg_cost, "0.00000001"),
        "experiment_cost_usd": money(experiment_cost, "0.00000001"),
        "estimated_cost_usd_50m_pages": money(
            avg_cost * Decimal("50000000"), "0.01"
        ),
        "estimated_cost_usd_200m_pages": money(
            avg_cost * Decimal("200000000"), "0.01"
        ),
        "extrapolation_note": EXTRAPOLATION_NOTE,
        "pricing_observation_date": None,
        "pricing_scope": None,
        "currency": None,
        "source": None,
        "input_price_per_1m": spec["input_price_per_1m"],
        "output_price_per_1m": spec["output_price_per_1m"],
    }


def main() -> None:
    pricing = json.loads(PRICING_PATH.read_text(encoding="utf-8"))
    rows = []
    for slug, spec in pricing["models"].items():
        row = summarize_model(slug, spec)
        row["pricing_observation_date"] = pricing["pricing_observation_date"]
        row["pricing_scope"] = pricing["pricing_scope"]
        row["currency"] = pricing["currency"]
        row["source"] = pricing["source"]
        rows.append(row)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUT_DIR / "cost_summary_2026-08-26.json"
    csv_path = OUT_DIR / "cost_summary_2026-08-26.csv"
    json_path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")

    fieldnames = list(rows[0].keys())
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Pricing config: {PRICING_PATH}")
    print(f"JSON: {json_path}")
    print(f"CSV: {csv_path}")
    for row in rows:
        print()
        print(row["display_name"])
        print(f"  avg input tokens/page: {row['avg_input_tokens_per_page']}")
        print(f"  avg output tokens/page: {row['avg_output_tokens_per_page']}")
        print(f"  avg total tokens/page: {row['avg_total_tokens_per_page']}")
        print(f"  avg latency ms/page: {row['avg_latency_ms_per_page']}")
        print(f"  avg cost/page: ${row['avg_cost_usd_per_page']}")
        print(f"  five-page experiment: ${row['experiment_cost_usd']}")
        print(
            f"  50M pages (linear extrapolation): "
            f"${row['estimated_cost_usd_50m_pages']}"
        )
        print(
            f"  200M pages (linear extrapolation): "
            f"${row['estimated_cost_usd_200m_pages']}"
        )


if __name__ == "__main__":
    main()
