"""S3-backed storage for uploaded PDF documents."""

import os
import re
from datetime import datetime
from functools import lru_cache
from pathlib import PurePosixPath
from urllib.parse import urlparse

from dotenv import load_dotenv


load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

MAX_UPLOAD_SIZE_BYTES = 30 * 1024 * 1024
AWS_REGION = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
AWS_S3_BUCKET_URL = os.getenv("AWS_S3_BUCKET_URL", "").strip()
AWS_S3_PREFIX = os.getenv("AWS_S3_PREFIX", "documents").strip("/")
AWS_ENDPOINT_URL = os.getenv("AWS_ENDPOINT_URL", "").strip() or None


def _bucket_name(value: str) -> str:
    """Accept an S3 bucket name, s3:// URI, or AWS bucket URL."""
    value = value.strip()
    if not value:
        return ""
    if "://" not in value:
        return value

    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    path_parts = [part for part in parsed.path.split("/") if part]

    # Virtual-hosted-style URL: https://bucket.s3.region.amazonaws.com/...
    if ".s3" in host and not host.startswith("s3."):
        return host.split(".s3", 1)[0]

    # Path-style URL: https://s3.region.amazonaws.com/bucket/...
    if host.startswith("s3.") or host == "s3.amazonaws.com":
        return path_parts[0] if path_parts else ""

    # s3://bucket/key
    if parsed.scheme == "s3":
        return parsed.netloc

    return ""


AWS_S3_BUCKET = _bucket_name(
    os.getenv("AWS_S3_BUCKET", "") or AWS_S3_BUCKET_URL
)


def _normalise_prefix() -> str:
    return f"{AWS_S3_PREFIX}/" if AWS_S3_PREFIX else ""


def _safe_filename(file_name: str) -> str:
    """Keep uploaded object keys inside the configured S3 prefix."""
    name = PurePosixPath(file_name.replace("\\", "/")).name
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", name).strip(" .")
    if not name:
        raise ValueError("The uploaded file must have a valid filename.")
    if not name.lower().endswith(".pdf"):
        raise ValueError("Only PDF files can be uploaded.")
    return name


def _validate_key(key: str) -> str:
    """Validate a key received from the UI before using it with S3."""
    prefix = _normalise_prefix()
    if not key or (prefix and not key.startswith(prefix)):
        raise ValueError("The selected document is not in the configured S3 prefix.")
    if ".." in PurePosixPath(key).parts or not key.lower().endswith(".pdf"):
        raise ValueError("The selected S3 object is not a valid PDF document.")
    return key


def _require_bucket() -> None:
    if not AWS_S3_BUCKET:
        raise RuntimeError(
            "AWS_S3_BUCKET is not configured. Add the S3 bucket name to .env."
        )


@lru_cache(maxsize=1)
def _get_s3_client():
    """Create one boto3 client using its standard credential chain."""
    try:
        import boto3
    except ImportError as error:
        raise RuntimeError(
            "S3 support requires boto3. Install dependencies with: "
            "pip install -r requirements.txt"
        ) from error

    client_options = {}
    if AWS_REGION:
        client_options["region_name"] = AWS_REGION
    if AWS_ENDPOINT_URL:
        client_options["endpoint_url"] = AWS_ENDPOINT_URL
    return boto3.client("s3", **client_options)


def check_s3_connection() -> tuple[bool, str]:
    """Return whether the configured S3 bucket is reachable."""
    if not AWS_S3_BUCKET:
        return False, "AWS_S3_BUCKET is not configured."

    try:
        _get_s3_client().head_bucket(Bucket=AWS_S3_BUCKET)
        location = f"{AWS_S3_BUCKET}/{_normalise_prefix()}".rstrip("/")
        return True, f"Connected to S3 ({location})."
    except Exception as error:
        return False, f"S3 bucket is not reachable: {error}"


def upload_pdf(file_name: str, file_bytes: bytes) -> dict:
    """Upload one PDF to S3 and return its document metadata."""
    _require_bucket()
    safe_name = _safe_filename(file_name)
    if len(file_bytes) > MAX_UPLOAD_SIZE_BYTES:
        raise ValueError("PDF files must be 30 MB or smaller.")
    if not file_bytes.startswith(b"%PDF"):
        raise ValueError("The selected file does not appear to be a valid PDF.")

    key = f"{_normalise_prefix()}{safe_name}"
    _get_s3_client().put_object(
        Bucket=AWS_S3_BUCKET,
        Key=key,
        Body=file_bytes,
        ContentType="application/pdf",
    )
    verified = _get_s3_client().head_object(Bucket=AWS_S3_BUCKET, Key=key)
    return {
        "key": key,
        "name": safe_name,
        "size": len(file_bytes),
        "verified": int(verified.get("ContentLength", -1)) == len(file_bytes),
        "last_modified": datetime.now().isoformat(timespec="seconds"),
    }


def list_documents() -> list[dict]:
    """List PDF documents stored under the configured S3 prefix."""
    _require_bucket()
    client = _get_s3_client()
    documents: list[dict] = []
    paginator = client.get_paginator("list_objects_v2")

    for page in paginator.paginate(Bucket=AWS_S3_BUCKET, Prefix=_normalise_prefix()):
        for item in page.get("Contents", []):
            key = item.get("Key", "")
            if not key.lower().endswith(".pdf"):
                continue
            documents.append(
                {
                    "key": key,
                    "name": PurePosixPath(key).name,
                    "size": int(item.get("Size", 0)),
                    "last_modified": item.get("LastModified"),
                }
            )

    return sorted(
        documents,
        key=lambda document: document["last_modified"].timestamp()
        if document["last_modified"]
        else 0,
        reverse=True,
    )


def download_pdf(key: str) -> bytes:
    """Download a selected PDF from S3 for in-memory ingestion."""
    _require_bucket()
    key = _validate_key(key)
    response = _get_s3_client().get_object(Bucket=AWS_S3_BUCKET, Key=key)
    body = response["Body"]
    try:
        file_bytes = body.read(MAX_UPLOAD_SIZE_BYTES + 1)
    finally:
        body.close()

    if len(file_bytes) > MAX_UPLOAD_SIZE_BYTES:
        raise ValueError("The selected PDF is larger than the 30 MB limit.")
    return file_bytes
