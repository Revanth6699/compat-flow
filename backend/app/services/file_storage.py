import re
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.core.config import settings


CHUNK_SIZE = 64 * 1024
STORAGE_KEY_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.csv$"
)


class FileStorageError(ValueError):
    pass


def get_storage_directory() -> Path:
    directory = Path(settings.import_storage_dir)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def get_storage_path(storage_key: str) -> Path:
    if not STORAGE_KEY_PATTERN.fullmatch(storage_key):
        raise FileStorageError("Invalid storage key.")

    return get_storage_directory() / storage_key


async def save_import_file(upload: UploadFile) -> str:
    filename = (upload.filename or "").strip()

    if Path(filename).suffix.lower() != ".csv":
        raise FileStorageError("Only CSV files are supported.")

    max_bytes = settings.import_max_upload_bytes
    if max_bytes <= 0:
        raise FileStorageError("Invalid upload size configuration.")

    storage_key = f"{uuid.uuid4()}.csv"
    destination = get_storage_path(storage_key)
    total_bytes = 0
    created = False

    try:
        with destination.open("xb") as stored_file:
            created = True
            while True:
                chunk = await upload.read(CHUNK_SIZE)

                if not chunk:
                    break

                total_bytes += len(chunk)

                if total_bytes > max_bytes:
                    raise FileStorageError(
                        f"File exceeds the {max_bytes}-byte upload limit."
                    )

                stored_file.write(chunk)

            if total_bytes == 0:
                raise FileStorageError("Uploaded file is empty.")

        return storage_key

    except Exception:
        if created:
            destination.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()
