
import re
from urllib.parse import urlsplit

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_debug: bool = False
    app_secret_key: str = "local-development-only-change-me"
    frontend_origin: str = "http://localhost:3001"
    allowed_hosts: str = "*"
    supabase_url: str = ""
    supabase_anon_key: str = ""

    database_url: str = (
        "postgresql+psycopg://compatflow_local:"
        "local-only-change-this-password@localhost:5432/compatflow"
    )
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    import_storage_dir: str = "/data/imports"
    import_max_upload_bytes: int = 5 * 1024 * 1024
    connector_allowed_hosts: str = ""
    sftp_known_hosts_path: str = ""

    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""
    razorpay_plan_ids_json: str = "{}"

    model_config = SettingsConfigDict(
        env_file="../.env",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_settings(self):
        if self.import_max_upload_bytes <= 0:
            raise ValueError("IMPORT_MAX_UPLOAD_BYTES must be positive.")

        if self.import_max_upload_bytes > 50 * 1024 * 1024:
            raise ValueError("IMPORT_MAX_UPLOAD_BYTES cannot exceed 50 MB.")

        if self.app_env.lower() != "production":
            return self

        if (
            len(self.app_secret_key) < 32
            or self.app_secret_key in {
                "local-only-change-me",
                "local-development-only-change-me",
                "change-me",
                "secret",
            }
        ):
            raise ValueError(
                "APP_SECRET_KEY must be a strong, randomly generated "
                "secret of at least 32 characters in production."
            )

        origins = [
            value.strip()
            for value in self.frontend_origin.split(",")
            if value.strip()
        ]

        if not origins:
            raise ValueError("FRONTEND_ORIGIN must contain an HTTPS origin.")

        for origin in origins:
            parsed = urlsplit(origin)

            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.path not in ("", "/")
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError(
                    "FRONTEND_ORIGIN must contain valid public HTTPS origins."
                )

        hosts = [
            value.strip().lower()
            for value in self.allowed_hosts.split(",")
            if value.strip()
        ]

        hostname_pattern = re.compile(
            r"^(?=.{1,253}$)"
            r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*"
            r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"
        )

        if not hosts or "*" in hosts:
            raise ValueError(
                "ALLOWED_HOSTS must contain explicit public API hostnames."
            )

        if any(not hostname_pattern.fullmatch(host) for host in hosts):
            raise ValueError(
                "ALLOWED_HOSTS contains an invalid hostname."
            )

        if self.app_debug:
            raise ValueError("APP_DEBUG must be false in production.")

        return self


settings = Settings()
