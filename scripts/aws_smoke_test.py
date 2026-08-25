import os
import sys

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv


def main() -> int:
    load_dotenv()

    profile = os.getenv("AWS_PROFILE", "idp-dev")
    region = os.getenv("AWS_REGION", "us-east-1")
    bucket = os.getenv("IDP_BUCKET")

    if not bucket:
        print("ERROR: IDP_BUCKET is not configured in .env")
        return 1

    try:
        session = boto3.Session(
            profile_name=profile,
            region_name=region,
        )

        sts = session.client("sts")
        s3 = session.client("s3")

        identity = sts.get_caller_identity()
        principal = identity["Arn"].split(":", maxsplit=5)[-1]

        s3.head_bucket(Bucket=bucket)

        public_access = s3.get_public_access_block(
            Bucket=bucket
        )["PublicAccessBlockConfiguration"]

        encryption = s3.get_bucket_encryption(
            Bucket=bucket
        )["ServerSideEncryptionConfiguration"]["Rules"][0][
            "ApplyServerSideEncryptionByDefault"
        ]["SSEAlgorithm"]

        versioning = s3.get_bucket_versioning(Bucket=bucket).get(
            "Status", "Disabled"
        )

        policy_status = s3.get_bucket_policy_status(
            Bucket=bucket
        )["PolicyStatus"]

        all_public_access_blocked = all(public_access.values())

        print(f"AWS profile: {profile}")
        print(f"Region: {region}")
        print(f"Principal: {principal}")
        print("S3 bucket reachable: yes")
        print(f"Encryption: {encryption}")
        print(f"Versioning: {versioning}")
        print(f"All public access blocked: {all_public_access_blocked}")
        print(f"Bucket policy public: {policy_status['IsPublic']}")
        print("AWS sandbox smoke test: PASSED")

        return 0

    except (BotoCoreError, ClientError) as error:
        print(f"AWS sandbox smoke test: FAILED ({type(error).__name__})")
        return 1


if __name__ == "__main__":
    sys.exit(main())