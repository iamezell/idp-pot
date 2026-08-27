"""Run DetectDocumentText on the IDP-204 degraded variants.

Reuses the IDP-206 cache and DetectDocumentText helper. Not an evaluation harness.
"""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

import boto3
from dotenv import load_dotenv
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from textract_detect_text import (
    inspect_response,
    obtain_detect_document_text,
    print_summary,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "artifacts" / "degradation_textract"
CSV_PATH = OUT_DIR / "comparison.csv"

DOCUMENTS = [
    {
        "path": REPO_ROOT / "data" / "synthetic" / "cost_slice" / "01_clean_medical.png",
        "transformation": "none",
    },
    {
        "path": REPO_ROOT / "data" / "synthetic" / "degraded" / "01_clean_medical_jpeg_q40.jpg",
        "transformation": "jpeg_compression",
    },
    {
        "path": REPO_ROOT / "data" / "synthetic" / "degraded" / "01_clean_medical_skew_3deg.png",
        "transformation": "skew",
    },
    {
        "path": REPO_ROOT / "data" / "synthetic" / "degraded" / "01_clean_medical_downsample_50pct.png",
        "transformation": "downsample",
    },
    {
        "path": REPO_ROOT / "data" / "synthetic" / "degraded" / "01_clean_medical_noise.png",
        "transformation": "noise",
    },
    {
        "path": REPO_ROOT / "data" / "synthetic" / "degraded" / "01_clean_medical_blur.png",
        "transformation": "blur",
    },
    {
        "path": REPO_ROOT / "data" / "synthetic" / "degraded" / "01_clean_medical_combined.png",
        "transformation": "combined",
    },
]

CSV_FIELDS = [
    "filename",
    "transformation",
    "width",
    "height",
    "word_count",
    "line_count",
    "avg_word_confidence",
    "printed_count",
    "handwriting_count",
    "cache_status",
]


def image_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as img:
        return img.size


def empty_row(path: Path, transformation: str, cache_status: str) -> dict:
    width = height = None
    if path.is_file():
        width, height = image_size(path)
    return {
        "filename": path.name,
        "transformation": transformation,
        "width": width,
        "height": height,
        "word_count": None,
        "line_count": None,
        "avg_word_confidence": None,
        "printed_count": None,
        "handwriting_count": None,
        "cache_status": cache_status,
    }


def main() -> int:
    load_dotenv()
    profile = os.getenv("AWS_PROFILE", "idp-dev")
    region = os.getenv("AWS_REGION", "us-east-1")
    session = boto3.Session(profile_name=profile, region_name=region)
    textract = session.client("textract")

    print(f"AWS profile: {profile}")
    print(f"Region: {region}")
    print(f"Images: {len(DOCUMENTS)}")

    rows = []
    failed = 0
    for item in DOCUMENTS:
        path: Path = item["path"]
        transformation = item["transformation"]
        print()
        print("=" * 72)
        print(f"{path.name}  ({transformation})")
        print("=" * 72)

        if not path.is_file():
            print(f"FAILED missing file: {path}", file=sys.stderr)
            rows.append(empty_row(path, transformation, "FAILED"))
            failed += 1
            continue

        width, height = image_size(path)
        response, cache_status, error = obtain_detect_document_text(path, textract)
        if error:
            print(f"FAILED {path.name}: {error}", file=sys.stderr)
            row = empty_row(path, transformation, cache_status)
            row["width"] = width
            row["height"] = height
            rows.append(row)
            failed += 1
            continue

        print_summary(path, response)
        stats = inspect_response(response)
        avg = stats["avg_word_confidence"]
        rows.append(
            {
                "filename": path.name,
                "transformation": transformation,
                "width": width,
                "height": height,
                "word_count": stats["word_count"],
                "line_count": stats["line_count"],
                "avg_word_confidence": (
                    None if avg is None else round(avg, 2)
                ),
                "printed_count": stats["printed_count"],
                "handwriting_count": stats["handwriting_count"],
                "cache_status": cache_status,
            }
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print()
    print(f"CSV: {CSV_PATH}")
    print()
    print(
        f"{'filename':<42} {'xform':<18} {'W':>4} {'L':>4} {'avg':>6} "
        f"{'print':>5} {'hand':>4} {'cache':<6}"
    )
    for row in rows:
        avg = row["avg_word_confidence"]
        avg_s = "-" if avg is None else f"{avg:.2f}"
        def cell(value) -> str:
            return "-" if value is None else str(value)

        print(
            f"{row['filename']:<42} {row['transformation']:<18} "
            f"{cell(row['word_count']):>4} "
            f"{cell(row['line_count']):>4} "
            f"{avg_s:>6} "
            f"{cell(row['printed_count']):>5} "
            f"{cell(row['handwriting_count']):>4} "
            f"{row['cache_status']:<6}"
        )

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
