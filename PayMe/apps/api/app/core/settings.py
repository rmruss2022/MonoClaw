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
    matching_variant: str | None = None  # rules_only | rules_vector | rules_vector_ranker
    ranker_default_rules_confidence_weight: float = 0.65
    ranker_default_similarity_weight: float = 0.2
    ranker_default_payout_weight: float = 0.1
    ranker_default_urgency_weight: float = 0.03
    ranker_default_ease_weight: float = 0.02

    # Track 2: Gmail real OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/integrations/gmail/oauth/callback"
    web_app_url: str = "http://localhost:15173"

    # Track 3: Plaid real integration
    plaid_client_id: str = ""
    plaid_secret: str = ""
    plaid_env: str = "sandbox"  # sandbox | development | production

    # Track 4: Autofill agent
    autofill_artifacts_dir: str = "/tmp/autofill-artifacts"
    autofill_max_retries: int = 3
    autofill_retry_delay_seconds: int = 60

    # Track 5: Gateway / payouts
    gateway_api_key_salt: str = "change-me-gateway-salt"
    token_encryption_key: str = ""  # Fernet key for encrypting OAuth/bank tokens at rest

    # Demo / provisioning
    mock_provision_password: str = "TestUser!2026"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
