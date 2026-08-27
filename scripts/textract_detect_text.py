import json
import os
import sys
from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv

from idp_pot.textract_detect import obtain_detect_document_text, print_summary

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCUMENT_PATH = (
    REPO_ROOT / "data" / "synthetic" / "cost_slice" / "01_clean_medical.png"
)


def main() -> int:
    load_dotenv()

    profile = os.getenv("AWS_PROFILE", "idp-dev")
    region = os.getenv("AWS_REGION", "us-east-1")

    if not DOCUMENT_PATH.is_file():
        print(f"ERROR: missing document {DOCUMENT_PATH}", file=sys.stderr)
        return 1

    print(f"AWS profile: {profile}")
    print(f"Region: {region}")
    print(f"Document: {DOCUMENT_PATH}")

    try:
        session = boto3.Session(profile_name=profile, region_name=region)
        textract = session.client("textract")
        response, _status, error, _latency = obtain_detect_document_text(
            DOCUMENT_PATH, textract
        )
        if error:
            print(
                f"Textract DetectDocumentText: FAILED ({error})",
                file=sys.stderr,
            )
            return 1
        print_summary(DOCUMENT_PATH, response)
        return 0

    except (BotoCoreError, ClientError, OSError, KeyError, json.JSONDecodeError) as error:
        print(
            f"Textract DetectDocumentText: FAILED ({type(error).__name__}: {error})",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
