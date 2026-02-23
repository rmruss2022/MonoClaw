"""Worker-side settings for the autofill agent service."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    database_url: str = "postgresql+psycopg://payme:payme@db:5432/payme"
    # Directory where screenshot / html / log artifacts are written.
    autofill_artifacts_dir: str = "/tmp/autofill-artifacts"
    # How many times to attempt a job before giving up.
    autofill_max_retries: int = 3
    # Seconds to wait before re-queuing a failed job.
    autofill_retry_delay_seconds: int = 60
    # Seconds between polling loops when the queue is empty.
    poll_interval_seconds: int = 5
    # API base URL used to fetch user profile data.
    api_base_url: str = "http://api:8000"
    # Anthropic API key for the vision-LLM form-fill loop.
    anthropic_api_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


worker_settings = WorkerSettings()
