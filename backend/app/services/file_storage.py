import re
import shutil
import uuid
from pathlib import Path

import httpx
from fastapi import UploadFile

from app.core.config import settings


CHUNK_SIZE = 64 * 1024
SUPPORTED_IMPORT_EXTENSIONS = {
    ".csv", ".xls", ".xlsx", ".json", ".xml",
}
STORAGE_KEY_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    r"\.(?:csv|xls|xlsx|json|xml)$"
)


class FileStorageError(ValueError):
    pass


def _extension(filename: str) -> str:
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_IMPORT_EXTENSIONS:
        supported = ", ".join(sorted(item.lstrip(".").upper() for item in SUPPORTED_IMPORT_EXTENSIONS))
        raise FileStorageError(f"Unsupported import file type. Supported formats: {supported}.")
    return extension


def _content_type(extension: str) -> str:
    known = {
        ".csv": "text/csv",
        ".xls": "application/vnd.ms-excel",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".json": "application/json",
        ".xml": "application/xml",
    }
    return known[extension]


def _supabase_storage_configured() -> bool:
    return bool(
        settings.supabase_url.strip()
        and settings.supabase_service_role_key.strip()
        and settings.import_storage_bucket.strip()
    )


def _storage_url(storage_key: str) -> str:
    if not STORAGE_KEY_PATTERN.fullmatch(storage_key):
        raise FileStorageError("Invalid storage key.")
    if not _supabase_storage_configured():
        raise FileStorageError("Private import object storage is not configured.")
    base_url = settings.supabase_url.rstrip("/")
    bucket = settings.import_storage_bucket.strip()
    return f"{base_url}/storage/v1/object/{bucket}/{storage_key}"


def get_storage_directory() -> Path:
    """Local-only fallback for development; production should use private object storage."""
    if settings.app_env.lower() == "production":
        raise FileStorageError("Local import storage is disabled in production.")
    directory = Path(settings.import_storage_dir)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def get_storage_path(storage_key: str) -> Path:
    if not STORAGE_KEY_PATTERN.fullmatch(storage_key):
        raise FileStorageError("Invalid storage key.")
    return get_storage_directory() / storage_key


async def _upload_to_supabase(
    upload: UploadFile, storage_key: str, total_bytes: int, content_type: str
) -> None:
    url = _storage_url(storage_key)
    headers = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": content_type,
        "Content-Length": str(total_bytes),
        "x-upsert": "false",
    }

    async def body():
        while True:
            chunk = await upload.read(CHUNK_SIZE)
            if not chunk:
                break
            yield chunk

    timeout = httpx.Timeout(120.0, connect=15.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.put(url, headers=headers, content=body())
        response.raise_for_status()


async def save_import_file(upload: UploadFile) -> str:
    filename = (upload.filename or "").strip()
    try:
        extension = _extension(filename)
        max_bytes = settings.import_max_upload_bytes
        if max_bytes <= 0:
            raise FileStorageError("Invalid upload size configuration.")

        storage_key = f"{uuid.uuid4()}{extension}"
        # UploadFile is already spooled by Starlette; inspect its length without
        # loading the complete payload into application memory.
        upload.file.seek(0, 2)
        total_bytes = upload.file.tell()
        upload.file.seek(0)
        if total_bytes == 0:
            raise FileStorageError("Uploaded file is empty.")
        if total_bytes > max_bytes:
            raise FileStorageError(f"File exceeds the {max_bytes}-byte upload limit.")

        if _supabase_storage_configured():
            await _upload_to_supabase(
                upload, storage_key, total_bytes, _content_type(extension)
            )
        else:
            if settings.app_env.lower() == "production":
                raise FileStorageError(
                    "Private import object storage is not configured for production."
                )
            destination = get_storage_path(storage_key)
            try:
                with destination.open("xb") as stored_file:
                    while True:
                        chunk = await upload.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        stored_file.write(chunk)
            except Exception:
                destination.unlink(missing_ok=True)
                raise

        return storage_key
    except httpx.HTTPError as exc:
        raise FileStorageError("Could not store the uploaded import file.") from exc
    finally:
        await upload.close()


def download_import_file(storage_key: str, destination: Path) -> Path:
    """Download a private object to worker-local disk without buffering it in RAM."""
    if not STORAGE_KEY_PATTERN.fullmatch(storage_key):
        raise FileStorageError("Invalid storage key.")

    if not _supabase_storage_configured():
        source = get_storage_path(storage_key)
        if not source.is_file():
            raise FileStorageError("Stored import file was not found.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        return destination

    url = _storage_url(storage_key)
    headers = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    timeout = httpx.Timeout(120.0, connect=15.0)
    try:
        with httpx.Client(timeout=timeout) as client:
            with client.stream("GET", url, headers=headers) as response:
                response.raise_for_status()
                with destination.open("xb") as stored_file:
                    for chunk in response.iter_bytes(CHUNK_SIZE):
                        stored_file.write(chunk)
    except httpx.HTTPError as exc:
        destination.unlink(missing_ok=True)
        raise FileStorageError("Could not retrieve the stored import file.") from exc
    return destination


def delete_import_file(storage_key: str) -> None:
    if not STORAGE_KEY_PATTERN.fullmatch(storage_key):
        raise FileStorageError("Invalid storage key.")

    if not _supabase_storage_configured():
        get_storage_path(storage_key).unlink(missing_ok=True)
        return

    headers = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
    }
    with httpx.Client(timeout=30.0) as client:
        response = client.delete(_storage_url(storage_key), headers=headers)
        if response.status_code not in {200, 204, 404}:
            response.raise_for_status()
