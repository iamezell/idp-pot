"""IDP-204: small deterministic document-degradation utility.

Creates controlled quality variants of one clean synthetic page so later
Textract/Claude runs can be compared. Not a production image pipeline.
"""

from __future__ import annotations

import hashlib
import json
import random
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageFilter

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = (
    REPO_ROOT / "data" / "synthetic" / "cost_slice" / "01_clean_medical.png"
)
OUT_DIR = REPO_ROOT / "data" / "synthetic" / "degraded"

# JPEG quality 40 is low enough to show blocking/ringing around glyphs
# without making a clean typed page unreadable.
JPEG_QUALITY = 40

# 3 degrees is a realistic copier/scanner skew; expand keeps the full page.
SKEW_DEGREES = 3.0

# Halving resolution then scaling back up mimics a low-DPI capture.
DOWNSAMPLE_SCALE = 0.5

# Fixed seed makes noise replayable for benchmarking.
NOISE_SEED = 42
NOISE_FRACTION = 0.12
NOISE_DELTA = 22

# Small Gaussian radius: slight scanner softness, not a smear.
BLUR_RADIUS = 1.25


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def image_info(path: Path) -> dict:
    with Image.open(path) as img:
        width, height = img.size
    return {
        "width": width,
        "height": height,
        "file_size": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def load_rgb(path: Path) -> Image.Image:
    with Image.open(path) as img:
        return img.convert("RGB")


def save_png(img: Image.Image, path: Path) -> None:
    img.save(path, format="PNG")


def apply_jpeg_compression(img: Image.Image, quality: int) -> Image.Image:
    """Lossy JPEG is the usual fax/email/scan compression artifact."""
    buf = BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=quality)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def apply_skew(img: Image.Image, degrees: float) -> Image.Image:
    """Small rotation models a page fed crooked into a scanner.

    expand=True grows the canvas so corners are not cropped.
    """
    return img.rotate(
        degrees,
        resample=Image.BICUBIC,
        expand=True,
        fillcolor="white",
    )


def apply_downsample(img: Image.Image, scale: float) -> Image.Image:
    """Downsample then restore nominal size so fine glyph edges are lost."""
    width, height = img.size
    small = img.resize(
        (max(1, int(width * scale)), max(1, int(height * scale))),
        Image.BILINEAR,
    )
    return small.resize((width, height), Image.BILINEAR)


def apply_noise(
    img: Image.Image,
    seed: int,
    fraction: float,
    delta: int,
) -> Image.Image:
    """Sparse pixel noise stands in for sensor/scan grain.

    A fixed seed keeps the same grain pattern across reruns.
    """
    rng = random.Random(seed)
    noisy = img.convert("RGB").copy()
    pixels = noisy.load()
    width, height = noisy.size
    for y in range(height):
        for x in range(width):
            if rng.random() < fraction:
                r, g, b = pixels[x, y]
                bump = rng.randint(-delta, delta)
                pixels[x, y] = (
                    max(0, min(255, r + bump)),
                    max(0, min(255, g + bump)),
                    max(0, min(255, b + bump)),
                )
    return noisy


def apply_blur(img: Image.Image, radius: float) -> Image.Image:
    """Mild Gaussian blur models slight defocus or motion on capture."""
    return img.filter(ImageFilter.GaussianBlur(radius=radius))


def apply_combined_degradation(img: Image.Image) -> Image.Image:
    """Plausible poor scan: skew + lost DPI + grain + JPEG, still readable."""
    combined = apply_skew(img, SKEW_DEGREES)
    combined = apply_downsample(combined, DOWNSAMPLE_SCALE)
    combined = apply_noise(combined, NOISE_SEED, NOISE_FRACTION, NOISE_DELTA)
    return apply_jpeg_compression(combined, JPEG_QUALITY)


def record(
    source: Path,
    output: Path,
    transformation_type: str,
    parameters: dict,
    notes: str,
) -> dict:
    src = image_info(source)
    out = image_info(output)
    return {
        "source_filename": source.name,
        "output_filename": output.name,
        "transformation_type": transformation_type,
        "transformation_parameters": parameters,
        "source_sha256": src["sha256"],
        "output_sha256": out["sha256"],
        "source_width": src["width"],
        "source_height": src["height"],
        "output_width": out["width"],
        "output_height": out["height"],
        "source_file_size": src["file_size"],
        "output_file_size": out["file_size"],
        "synthetic": True,
        "notes": notes,
    }


def validate(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(path)
    with Image.open(path) as img:
        img.load()


def main() -> int:
    if not SOURCE_PATH.is_file():
        raise FileNotFoundError(f"missing source: {SOURCE_PATH}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = load_rgb(SOURCE_PATH)

    jobs = [
        {
            "name": "JPEG compression",
            "path": OUT_DIR / "01_clean_medical_jpeg_q40.jpg",
            "image": source,
            "save": "jpeg",
            "type": "jpeg_compression",
            "parameters": {"quality": JPEG_QUALITY},
            "notes": "Visible JPEG blocking/ringing at quality 40.",
        },
        {
            "name": "skew",
            "path": OUT_DIR / "01_clean_medical_skew_3deg.png",
            "image": apply_skew(source, SKEW_DEGREES),
            "save": "png",
            "type": "skew",
            "parameters": {
                "degrees": SKEW_DEGREES,
                "expand": True,
                "fillcolor": "white",
            },
            "notes": "3 degree rotation with expanded canvas so content is not cropped.",
        },
        {
            "name": "downsample",
            "path": OUT_DIR / "01_clean_medical_downsample_50pct.png",
            "image": apply_downsample(source, DOWNSAMPLE_SCALE),
            "save": "png",
            "type": "downsample",
            "parameters": {
                "scale": DOWNSAMPLE_SCALE,
                "resample": "BILINEAR",
                "restore_original_size": True,
                "intermediate_size": [
                    max(1, int(source.size[0] * DOWNSAMPLE_SCALE)),
                    max(1, int(source.size[1] * DOWNSAMPLE_SCALE)),
                ],
            },
            "notes": "Resized to 50% then back to original dimensions to drop high-frequency detail.",
        },
        {
            "name": "noise",
            "path": OUT_DIR / "01_clean_medical_noise.png",
            "image": apply_noise(source, NOISE_SEED, NOISE_FRACTION, NOISE_DELTA),
            "save": "png",
            "type": "noise",
            "parameters": {
                "seed": NOISE_SEED,
                "fraction": NOISE_FRACTION,
                "delta": NOISE_DELTA,
            },
            "notes": "Deterministic sparse pixel noise; seed recorded for replay.",
        },
        {
            "name": "blur",
            "path": OUT_DIR / "01_clean_medical_blur.png",
            "image": apply_blur(source, BLUR_RADIUS),
            "save": "png",
            "type": "blur",
            "parameters": {"filter": "GaussianBlur", "radius": BLUR_RADIUS},
            "notes": "Mild Gaussian blur for slight capture softness.",
        },
        {
            "name": "combined degradation",
            "path": OUT_DIR / "01_clean_medical_combined.png",
            "image": apply_combined_degradation(source),
            "save": "png",
            "type": "combined",
            "parameters": {
                "degrees": SKEW_DEGREES,
                "scale": DOWNSAMPLE_SCALE,
                "seed": NOISE_SEED,
                "fraction": NOISE_FRACTION,
                "delta": NOISE_DELTA,
                "jpeg_quality": JPEG_QUALITY,
                "order": ["skew", "downsample", "noise", "jpeg_compression"],
            },
            "notes": "Combined mild skew, downsample, noise, and JPEG as a plausible poor scan.",
        },
    ]

    records = []
    for job in jobs:
        path: Path = job["path"]
        if job["save"] == "jpeg":
            job["image"].save(path, format="JPEG", quality=JPEG_QUALITY)
        else:
            save_png(job["image"], path)
        validate(path)
        records.append(
            record(
                SOURCE_PATH,
                path,
                job["type"],
                job["parameters"],
                job["notes"],
            )
        )

    manifest_path = OUT_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")

    print(f"Source: {SOURCE_PATH.name}")
    print("Generated:")
    for job in jobs:
        print(f"- {job['name']}")
    print()
    print("Manifest:")
    print(manifest_path)
    for rec in records:
        print(
            f"  {rec['output_filename']}  "
            f"{rec['output_width']}x{rec['output_height']}  "
            f"{rec['output_file_size']} bytes  "
            f"sha256={rec['output_sha256'][:12]}..."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
