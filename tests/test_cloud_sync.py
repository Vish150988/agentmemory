"""Tests for encrypted cloud sync."""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

from crossagentmemory import MemoryEntry
from crossagentmemory.cloud_sync import _export_to_zip, _get_fernet, _import_from_zip


def test_fernet_roundtrip():
    f = _get_fernet("test-password-123")
    plaintext = b"hello crossagentmemory"
    encrypted = f.encrypt(plaintext)
    decrypted = f.decrypt(encrypted)
    assert decrypted == plaintext


def test_export_import_roundtrip(tmp_path):
    from crossagentmemory import MemoryEngine
    from crossagentmemory.backends.sqlite import SQLiteBackend

    db1 = tmp_path / "test1.db"
    backend = SQLiteBackend(db_path=db1)
    backend.init()
    engine = MemoryEngine.__new__(MemoryEngine)
    engine.backend = backend

    engine.store(MemoryEntry(project="p1", content="memory one"))
    engine.store(MemoryEntry(project="p1", content="memory two"))

    raw = _export_to_zip(engine)
    assert isinstance(raw, bytes)

    # Import into fresh engine
    db2 = tmp_path / "test2.db"
    backend2 = SQLiteBackend(db_path=db2)
    backend2.init()
    engine2 = MemoryEngine.__new__(MemoryEngine)
    engine2.backend = backend2

    count = _import_from_zip(engine2, raw)
    assert count == 2
    results = engine2.backend.recall(project="p1")
    assert len(results) == 2


def test_sync_export_upload():
    with patch("crossagentmemory.cloud_sync._get_s3_client") as mock_client:
        mock_s3 = MagicMock()
        mock_client.return_value = mock_s3

        from crossagentmemory import MemoryEngine
        from crossagentmemory.backends.sqlite import SQLiteBackend

        backend = SQLiteBackend()
        backend.init()
        engine = MemoryEngine.__new__(MemoryEngine)
        engine.backend = backend
        engine.store(MemoryEntry(project="p1", content="cloud test"))

        from crossagentmemory.cloud_sync import sync_export

        sync_export(engine, "pass123", "my-bucket")
        mock_s3.put_object.assert_called_once()
        args = mock_s3.put_object.call_args.kwargs
        assert args["Bucket"] == "my-bucket"
        assert args["Key"] == "crossagentmemory-backup.enc"
        assert isinstance(args["Body"], bytes)


def test_sync_import_download():
    from crossagentmemory.cloud_sync import _export_to_zip, sync_import

    with patch("crossagentmemory.cloud_sync._get_s3_client") as mock_client:
        mock_s3 = MagicMock()
        backend = MagicMock()
        backend.list_projects.return_value = ["p1"]
        backend.recall.return_value = []

        # Pre-encrypt a zip payload
        raw = _export_to_zip(MagicMock())
        f = _get_fernet("pass123")
        encrypted = f.encrypt(raw)
        mock_s3.get_object.return_value = {"Body": io.BytesIO(encrypted)}
        mock_client.return_value = mock_s3

        engine = MagicMock()
        engine.backend = backend
        sync_import(engine, "pass123", "my-bucket")
        mock_s3.get_object.assert_called_once()
