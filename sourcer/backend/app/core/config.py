"""Central typed settings, loaded from environment (.env)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Telegram
    telegram_api_id: int = Field(0, alias="TELEGRAM_API_ID")
    telegram_api_hash: str = Field("", alias="TELEGRAM_API_HASH")
    telegram_session_name: str = Field("sourcer_session", alias="TELEGRAM_SESSION_NAME")
    telegram_phone: Optional[str] = Field(None, alias="TELEGRAM_PHONE")

    # LinkedIn cookies
    linkedin_li_at: str = Field("", alias="LINKEDIN_LI_AT")
    linkedin_sales_nav_cookie: str = Field("", alias="LINKEDIN_SALES_NAV_COOKIE")

    # Apify (still used for profile sourcing deep-scan via Apify actors)
    apify_api_key: str = Field("", alias="APIFY_API_KEY")
    apify_linkedin_actor: str = Field(
        "harvestapi/linkedin-profile-search", alias="APIFY_LINKEDIN_ACTOR"
    )
    # Actor used for Phase 2 deep profile scraping (accepts profileUrls[] input)
    apify_profile_actor: str = Field(
        "harvestapi/linkedin-profile-search", alias="APIFY_PROFILE_ACTOR"
    )
    # PhantomBuster fields kept for backward compat but no longer used by any code path
    phantombuster_api_key: str = Field("", alias="PHANTOMBUSTER_API_KEY")
    phantombuster_agent_id: Optional[str] = Field(None, alias="PHANTOMBUSTER_AGENT_ID")
    pb_message_agent_id: str = Field("", alias="PB_MESSAGE_AGENT_ID")

    # LinkedIn Playwright sender settings
    li_headless: bool = Field(True, alias="LI_HEADLESS")  # set False for visual debugging
    li_send_min_delay: float = Field(300.0, alias="LI_SEND_MIN_DELAY")  # seconds between sends
    li_send_max_delay: float = Field(900.0, alias="LI_SEND_MAX_DELAY")  # up to 15 min

    # Operator alerts — Telegram handle to ping when cookies expire or agent errors occur
    operator_telegram_username: str = Field("", alias="OPERATOR_TELEGRAM_USERNAME")

    # Supabase
    supabase_url: str = Field("", alias="SUPABASE_URL")
    supabase_anon_key: str = Field("", alias="SUPABASE_ANON_KEY")
    supabase_service_role_key: Optional[str] = Field(None, alias="SUPABASE_SERVICE_ROLE_KEY")

    # Gemini
    gemini_api_key: str = Field("", alias="GEMINI_API_KEY")
    gemini_api_keys: str = Field("", alias="GEMINI_API_KEYS")  # comma-separated for rotation
    gemini_model: str = Field("gemini-2.0-flash", alias="GEMINI_MODEL")
    gemini_embed_model: str = Field("gemini-embedding-001", alias="GEMINI_EMBED_MODEL")

    # OpenRouter (OpenAI-compatible proxy — set AI_PROVIDER=openrouter to use)
    openrouter_api_key: str = Field("", alias="OPENROUTER_API_KEY")
    openrouter_model: str = Field("google/gemini-2.0-flash-001", alias="OPENROUTER_MODEL")
    ai_provider: str = Field("gemini", alias="AI_PROVIDER")  # gemini | openrouter

    # Task-specific model overrides (optional - falls back to default)
    model_job_planning: Optional[str] = Field(None, alias="MODEL_JOB_PLANNING")
    model_scoring: Optional[str] = Field(None, alias="MODEL_SCORING")
    model_vacancy_structure: Optional[str] = Field(None, alias="MODEL_VACANCY_STRUCTURE")
    model_outreach_classify: Optional[str] = Field(None, alias="MODEL_OUTREACH_CLASSIFY")
    model_outreach_draft: Optional[str] = Field(None, alias="MODEL_OUTREACH_DRAFT")
    model_channel_discovery: Optional[str] = Field(None, alias="MODEL_CHANNEL_DISCOVERY")

    # Redis / Celery
    redis_url: str = Field("redis://localhost:6379/0", alias="REDIS_URL")
    celery_broker_url: str = Field("redis://localhost:6379/0", alias="CELERY_BROKER_URL")
    celery_result_backend: str = Field("redis://localhost:6379/1", alias="CELERY_RESULT_BACKEND")

    # Enrichment
    apollo_api_key: Optional[str] = Field(None, alias="APOLLO_API_KEY")
    hunter_api_key: Optional[str] = Field(None, alias="HUNTER_API_KEY")
    enable_apollo: bool = Field(False, alias="ENABLE_APOLLO")
    enable_hunter: bool = Field(False, alias="ENABLE_HUNTER")

    # App
    app_env: str = Field("dev", alias="APP_ENV")
    api_port: int = Field(8000, alias="API_PORT")
    frontend_url: str = Field("http://localhost:3000", alias="FRONTEND_URL")
    log_level: str = Field("INFO", alias="LOG_LEVEL")

    # Scoring
    embedding_filter_percentile: float = Field(0.30, alias="EMBEDDING_FILTER_PERCENTILE")
    min_gemini_score: int = Field(50, alias="MIN_GEMINI_SCORE")
    
    # Batch scoring (5-10x speedup)
    batch_scoring_enabled: bool = Field(True, alias="BATCH_SCORING_ENABLED")
    batch_scoring_size: int = Field(5, alias="BATCH_SCORING_SIZE")  # candidates per API call

    # Auth (Tier-1: JWT multi-tenancy)
    jwt_secret: str = Field("", alias="JWT_SECRET")  # MUST set in .env for production
    jwt_algorithm: str = Field("HS256", alias="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(10080, alias="JWT_EXPIRE_MINUTES")  # 7 days

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[3] / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        protected_namespaces=(),  # allow model_* field names (model_scoring, etc.)
    )
    
    def get_model_for_task(self, task: str) -> str:
        """Get the model to use for a specific task.
        
        Falls back to default model if task-specific model not set.
        
        Args:
            task: One of: job_planning, scoring, vacancy_structure, 
                  outreach_classify, outreach_draft, channel_discovery
        
        Returns:
            Model identifier (e.g., "gemini-2.0-flash" or "google/gemini-2.0-flash-001")
        """
        task_model_map = {
            "job_planning": self.model_job_planning,
            "scoring": self.model_scoring,
            "vacancy_structure": self.model_vacancy_structure,
            "outreach_classify": self.model_outreach_classify,
            "outreach_draft": self.model_outreach_draft,
            "channel_discovery": self.model_channel_discovery,
        }
        
        # Get task-specific model or fall back to default
        task_model = task_model_map.get(task)
        if task_model:
            return task_model
        
        # Fall back to provider default
        return self.openrouter_model if self.ai_provider == "openrouter" else self.gemini_model


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
