from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Core
    environment: str = "development"
    database_url: str = "sqlite:///./app.db"

    # Razorpay (test mode)
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""

    # Anthropic
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"

    # CORS
    allowed_origin: str = "http://localhost:5173"

    # Demo/ops
    demo_key: str = "change-me"
    mcp_port: int = 8800

    # Policy defaults (overridable per-env without code changes)
    policy_max_discount_pct: float = 20.0
    policy_approval_threshold_inr: float = 3000.0
    policy_max_txn_value_inr: float = 5000.0
    policy_max_session_spend_inr: float = 8000.0
    policy_max_items_per_order: int = 5
    policy_max_tool_calls_per_turn: int = 8
    policy_max_consecutive_tool_errors: int = 3


settings = Settings()
