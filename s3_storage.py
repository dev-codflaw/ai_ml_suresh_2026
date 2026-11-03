"""Private S3 PDF storage, separate from database ingestion."""

import os
from pathlib import Path
from uuid import uuid4

import boto3
from dotenv import load_dotenv


load_dotenv(Path(__file__).with_name(".env"))


def _storage():
    bucket = (os.getenv("AWS_S3_BUCKET") or os.getenv("S3_BUCKET", "")).strip()
    if not bucket:
        raise ValueError("Set AWS_S3_BUCKET in .env to your existing PDF bucket name.")
    prefix = os.getenv("AWS_S3_PREFIX", os.getenv("S3_PREFIX", "pdfs")).strip().strip("/")
    region = (os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "").strip()
    # Boto3 loads credentials from the environment or the EC2 instance role.
    # Public bucket URLs are not needed: PDF access uses private signed links.
    options = {"region_name": region} if region else {}
    return boto3.client("s3", **options), bucket, prefix + "/" if prefix else ""


def upload_pdf(name: str, data: bytes) -> str:
    """Store a PDF under a unique key without ingesting it."""
    name = Path(name).name
    if not name.lower().endswith(".pdf") or not data.startswith(b"%PDF-"):
        raise ValueError("Choose a valid PDF file.")
    client, bucket, prefix = _storage()
    key = f"{prefix}{uuid4().hex}/{name}"
    client.put_object(Bucket=bucket, Key=key, Body=data, ContentType="application/pdf")
    return key


def list_pdfs() -> list[dict]:
    """List PDFs across all pages in the configured S3 prefix."""
    client, bucket, prefix = _storage()
    files = []
    for page in client.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
        files.extend(item for item in page.get("Contents", []) if item["Key"].lower().endswith(".pdf"))
    return sorted(files, key=lambda item: item["LastModified"], reverse=True)


def download_pdf(key: str, destination: Path) -> None:
    """Download the selected S3 PDF for explicit ingestion."""
    client, bucket, prefix = _storage()
    if not key.startswith(prefix) or not key.lower().endswith(".pdf"):
        raise ValueError("Select a PDF from the configured S3 folder.")
    client.download_file(bucket, key, str(destination))


def pdf_url(key: str) -> str:
    """Create a short-lived link without making the bucket public."""
    client, bucket, _ = _storage()
    return client.generate_presigned_url(
        "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=300
    )
