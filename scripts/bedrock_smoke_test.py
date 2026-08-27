import os
import sys
from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv

# Confirmed in this account/region via:
#   aws bedrock list-foundation-models  (inferenceTypes = INFERENCE_PROFILE only)
#   aws bedrock list-inference-profiles (us.anthropic.claude-sonnet-4-6 = ACTIVE)
# In-region model ID anthropic.claude-sonnet-4-6 is not invokable in us-east-1.
MODEL_ID = "us.anthropic.claude-sonnet-4-6"

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_IMAGE = REPO_ROOT / "data" / "synthetic" / "invoice_page.png"
IMAGE_FORMATS = {".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg"}

PROMPT = """Extract fields from this document page.
Return JSON only, with no markdown or extra text, in this shape:
{
  "document_type": "invoice",
  "fields": {
    "company": "",
    "invoice_number": "",
    "invoice_date": "",
    "bill_to": "",
    "subtotal": "",
    "tax": "",
    "total": "",
    "po_number": "",
    "payment_terms": ""
  }
}
Use null for any field that is not present. Do not invent values."""


def resolve_image_path() -> Path:
    if DEFAULT_IMAGE.is_file():
        return DEFAULT_IMAGE

    synthetic_dir = DEFAULT_IMAGE.parent
    matches = sorted(
        path
        for path in synthetic_dir.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_FORMATS
    )
    if not matches:
        raise FileNotFoundError(
            f"No PNG/JPEG document page found at {DEFAULT_IMAGE} "
            f"or in {synthetic_dir}"
        )
    return matches[0]


def main() -> int:
    load_dotenv()

    profile = os.getenv("AWS_PROFILE", "idp-dev")
    region = os.getenv("AWS_REGION", "us-east-1")

    try:
        image_path = resolve_image_path()
        image_format = IMAGE_FORMATS[image_path.suffix.lower()]
        image_bytes = image_path.read_bytes()

        session = boto3.Session(
            profile_name=profile,
            region_name=region,
        )
        bedrock = session.client("bedrock-runtime")

        print(f"AWS profile: {profile}")
        print(f"Region: {region}")
        print(f"Model ID: {MODEL_ID}")
        print(f"Image: {image_path}")

        response = bedrock.converse(
            modelId=MODEL_ID,
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
                        {"text": PROMPT},
                    ],
                }
            ],
            inferenceConfig={"maxTokens": 512},
        )

        output_text = "".join(
            block.get("text", "")
            for block in response["output"]["message"]["content"]
        )
        usage = response["usage"]
        latency_ms = response.get("metrics", {}).get("latencyMs")

        print("Model response:")
        print(output_text)
        print(f'inputTokens: {usage["inputTokens"]}')
        print(f'outputTokens: {usage["outputTokens"]}')
        print(f'totalTokens: {usage["totalTokens"]}')
        if latency_ms is not None:
            print(f"latencyMs: {latency_ms}")
        else:
            print("latencyMs: not returned")
        print("Bedrock Converse smoke test: PASSED")
        return 0

    except (BotoCoreError, ClientError, OSError, KeyError) as error:
        print(
            f"Bedrock Converse smoke test: FAILED ({type(error).__name__}: {error})",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
