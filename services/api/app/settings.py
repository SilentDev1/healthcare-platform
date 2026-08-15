from packages.runtime import RuntimeSettings


class ApiSettings(RuntimeSettings):
    api_title: str = "Carevero API"
    api_version: str = "0.1.0"
    # --- AI assistant (all OFF by default; the deterministic search works without it) ---
    # No external LLM provider is configured until ai_provider_endpoint + api_key are
    # set. With the provider unset the assistant uses the deterministic grounded
    # fallback only. Enabling any flag without the provider still never invents facts.
    ai_assistant_enabled: bool = False
    ai_intent_search_enabled: bool = False
    ai_explanations_enabled: bool = False
    ai_provider_endpoint: str | None = None
    ai_provider_api_key: str | None = None
    ai_intent_model: str = "fast-structured-model"
    ai_explanation_model: str = "fast-explanation-model"
    ai_max_output_tokens: int = 500
    ai_timeout_seconds: float = 12.0
    ai_rate_limit_requests: int = 20
    ai_rate_limit_window_seconds: int = 60


api_settings = ApiSettings()
