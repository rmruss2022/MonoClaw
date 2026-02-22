from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://payme:payme@localhost:5432/payme"
    jwt_secret: str = "change-me"
    jwt_expire_minutes: int = 120
    mock_gmail: bool = True
    mock_plaid: bool = True
    admin_debug: bool = True
    log_file_path: str = "/tmp/payme-app.jsonl"
    experiment_key: str = "matching_v1"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
