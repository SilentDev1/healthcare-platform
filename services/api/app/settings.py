from packages.runtime import RuntimeSettings


class ApiSettings(RuntimeSettings):
    api_title: str = "Carevero API"
    api_version: str = "0.1.0"
    # --- AI assistant (all OFF by default; the deterministic search works without it) ---
    # No external LLM runs until a provider + secret are configured AND a flag is on.
    # With the provider unset, the assistant uses the deterministic grounded fallback
    # only. Enabling any flag without the provider still never invents facts, and every
    # LLM proposal is canonical-validated before it can affect a response.
    ai_assistant_enabled: bool = False
    ai_intent_search_enabled: bool = False
    ai_explanations_enabled: bool = False

    # Provider selection + models (environment-configurable; change models without code).
    # AI_PROVIDER=openai to use OpenAI's Responses API; "none" keeps the deterministic
    # fallback. The OpenAI key comes ONLY from Secret Manager (OPENAI_API_KEY) server-side
    # and is never sent to the browser, logged, or returned in any response.
    ai_provider: str = "none"  # "openai" | "none"
    ai_primary_model: str = "gpt-5.6-luna"  # AI_PRIMARY_MODEL — routine interpretation
    ai_escalation_model: str = "gpt-5.6-terra"  # AI_ESCALATION_MODEL — hard/ambiguous only
    openai_api_key: str | None = None  # OPENAI_API_KEY (Secret Manager) — never expose
    ai_openai_endpoint: str = "https://api.openai.com/v1/responses"

    # Legacy generic-provider fields (kept for backward compatibility / self-hosted).
    ai_provider_endpoint: str | None = None
    ai_provider_api_key: str | None = None
    ai_intent_model: str = "fast-structured-model"
    ai_explanation_model: str = "fast-explanation-model"

    ai_max_output_tokens: int = 500
    ai_timeout_seconds: float = 12.0
    ai_rate_limit_requests: int = 20
    ai_rate_limit_window_seconds: int = 60

    # Cost controls. Budget is fail-closed: 0 means no LLM spend is permitted, so an
    # unconfigured budget can never authorize unbounded spend. Per-million token rates
    # feed cost estimation/telemetry and are configurable per current model pricing.
    ai_daily_budget_usd: float = 0.0
    ai_cost_input_per_million: float = 0.0
    ai_cost_output_per_million: float = 0.0

    @property
    def resolved_ai_endpoint(self) -> str | None:
        if self.ai_provider == "openai":
            return self.ai_provider_endpoint or self.ai_openai_endpoint
        return self.ai_provider_endpoint

    @property
    def resolved_ai_api_key(self) -> str | None:
        if self.ai_provider == "openai":
            return self.openai_api_key or self.ai_provider_api_key
        return self.ai_provider_api_key

    @property
    def ai_provider_configured(self) -> bool:
        """True only when a real provider AND its secret are present."""
        return bool(
            self.ai_provider != "none" and self.resolved_ai_endpoint and self.resolved_ai_api_key
        )


api_settings = ApiSettings()
