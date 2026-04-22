"""Encrypted cloud sync for CrossAgentMemory (S3-compatible)."""

from __future__ import annotations

import io
import json
import logging
import zipfile
from typing import Any

from .core import MemoryEngine

logger = logging.getLogger(__name__)


def _get_fernet(password: str):
    """Derive a Fernet key from a password using PBKDF2."""
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"crossagentmemory-v1",
        iterations=480000,
    )
    key = kdf.derive(password.encode("utf-8"))
    # Fernet needs base64-encoded 32-byte key
    import base64

    return Fernet(base64.urlsafe_b64encode(key))


def _export_to_zip(engine: MemoryEngine) -> bytes:
    """Export all memories to an in-memory zip of JSON files."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        projects = engine.backend.list_projects()
        for project in projects:
            memories = engine.backend.recall(project=project, limit=100000)
            data = {
                "project": project,
                "memories": [
                    {
                        "id": m.id,
                        "project": m.project,
                        "session_id": m.session_id,
                        "timestamp": m.timestamp,
                        "category": m.category,
                        "content": m.content,
                        "confidence": m.confidence,
                        "source": m.source,
                        "tags": m.tags,
                        "metadata": m.metadata,
                    }
                    for m in memories
                ],
            }
            zf.writestr(f"{project}.json", json.dumps(data, indent=2))
    return buf.getvalue()


def _import_from_zip(engine: MemoryEngine, data: bytes) -> int:
    """Import memories from a zip of JSON files."""
    count = 0
    buf = io.BytesIO(data)
    with zipfile.ZipFile(buf, "r") as zf:
        for name in zf.namelist():
            if not name.endswith(".json"):
                continue
            raw = zf.read(name)
            payload = json.loads(raw)
            for item in payload.get("memories", []):
                from .core import MemoryEntry

                entry = MemoryEntry(
                    id=None,  # Let backend assign new ID
                    project=item.get("project", "imported"),
                    session_id=item.get("session_id", "cloud-import"),
                    timestamp=item.get("timestamp", ""),
                    category=item.get("category", "fact"),
                    content=item.get("content", ""),
                    confidence=item.get("confidence", 0.8),
                    source=item.get("source", "cloud-import"),
                    tags=item.get("tags", ""),
                    metadata=item.get("metadata", "{}"),
                )
                engine.store(entry)
                count += 1
    return count


def _get_s3_client(endpoint: str | None = None):
    import boto3

    kwargs: dict[str, Any] = {}
    if endpoint:
        kwargs["endpoint_url"] = endpoint
    return boto3.client("s3", **kwargs)


def sync_export(
    engine: MemoryEngine,
    password: str,
    bucket: str,
    endpoint: str | None = None,
    key: str = "crossagentmemory-backup.enc",
) -> None:
    """Export memories to an encrypted zip and upload to S3."""
    fernet = _get_fernet(password)
    raw = _export_to_zip(engine)
    encrypted = fernet.encrypt(raw)

    s3 = _get_s3_client(endpoint)
    s3.put_object(Bucket=bucket, Key=key, Body=encrypted)
    logger.info("Uploaded encrypted backup to s3://%s/%s", bucket, key)


def sync_import(
    engine: MemoryEngine,
    password: str,
    bucket: str,
    endpoint: str | None = None,
    key: str = "crossagentmemory-backup.enc",
) -> int:
    """Download encrypted backup from S3 and restore memories."""
    s3 = _get_s3_client(endpoint)
    response = s3.get_object(Bucket=bucket, Key=key)
    encrypted = response["Body"].read()

    fernet = _get_fernet(password)
    raw = fernet.decrypt(encrypted)
    count = _import_from_zip(engine, raw)
    logger.info("Restored %d memories from s3://%s/%s", count, bucket, key)
    return count


def sync_list(
    bucket: str,
    endpoint: str | None = None,
    prefix: str = "crossagentmemory",
) -> list[dict[str, Any]]:
    """List backup objects in the S3 bucket."""
    s3 = _get_s3_client(endpoint)
    response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
    return [
        {"key": obj["Key"], "size": obj["Size"], "modified": obj["LastModified"]}
        for obj in response.get("Contents", [])
    ]
