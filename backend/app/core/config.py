from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_env: str = "development"
    app_debug: bool = False
    app_secret_key: str = "local-only-change-me"
    frontend_origin: str = "http://localhost:3000"
    database_url: str = "postgresql+psycopg://compatflow_local:local-only-change-this-password@localhost:5432/compatflow"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")

settings = Settings()
