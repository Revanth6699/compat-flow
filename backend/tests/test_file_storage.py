import asyncio
import io

import pytest
from starlette.datastructures import UploadFile

from app.core.config import settings
from app.services.file_storage import (
    FileStorageError,
    download_import_file,
    get_storage_path,
    save_import_file,
)


def test_local_development_storage_round_trips_without_loading_whole_file(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "supabase_url", "")
    monkeypatch.setattr(settings, "supabase_service_role_key", "")
    monkeypatch.setattr(settings, "import_storage_dir", str(tmp_path))
    monkeypatch.setattr(settings, "import_max_upload_bytes", 1024)

    payload = b"sku,name\nA-1,Widget\n"
    upload = UploadFile(filename="catalog.csv", file=io.BytesIO(payload))
    key = asyncio.run(save_import_file(upload))

    stored = get_storage_path(key)
    assert stored.read_bytes() == payload

    destination = tmp_path / "worker" / "download.csv"
    download_import_file(key, destination)
    assert destination.read_bytes() == payload


def test_local_storage_rejects_upload_over_configured_byte_limit(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "supabase_url", "")
    monkeypatch.setattr(settings, "supabase_service_role_key", "")
    monkeypatch.setattr(settings, "import_storage_dir", str(tmp_path))
    monkeypatch.setattr(settings, "import_max_upload_bytes", 4)

    upload = UploadFile(filename="catalog.csv", file=io.BytesIO(b"12345"))
    with pytest.raises(FileStorageError, match="upload limit"):
        asyncio.run(save_import_file(upload))

    assert list(tmp_path.iterdir()) == []


def test_production_refuses_local_storage_fallback(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "supabase_url", "")
    monkeypatch.setattr(settings, "supabase_service_role_key", "")
    monkeypatch.setattr(settings, "import_max_upload_bytes", 1024)

    upload = UploadFile(filename="catalog.csv", file=io.BytesIO(b"sku\nA-1\n"))
    with pytest.raises(FileStorageError, match="not configured"):
        asyncio.run(save_import_file(upload))
