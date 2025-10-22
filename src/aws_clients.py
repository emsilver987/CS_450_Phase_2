# NEW FILE
import os
import boto3

REGION = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
ENDPOINT = os.getenv("AWS_ENDPOINT_URL")  # e.g., http://localhost:4566 for LocalStack

def _kw():
    k = {"region_name": REGION}
    if ENDPOINT:
        k["endpoint_url"] = ENDPOINT
    return k

def s3_client():
    return boto3.client("s3", **_kw())

def dynamodb_client():
    return boto3.client("dynamodb", **_kw())

def dynamodb_resource():
    return boto3.resource("dynamodb", **_kw())
