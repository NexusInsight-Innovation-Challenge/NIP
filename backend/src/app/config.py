from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    azure_webpubsub_connection_string: str = Field(
        ...,
        alias="AZURE_WEBPUBSUB_CONNECTION_STRING",
        min_length=8,
    )
    azure_webpubsub_hub: str = Field(..., alias="AZURE_WEBPUBSUB_HUB_NAME", min_length=3)
    azure_webpubsub_group: str = Field(..., alias="AZURE_WEBPUBSUB_GROUP", min_length=3)

    azure_ai_project_endpoint: str | None = Field(None, alias="AZURE_AI_PROJECT_ENDPOINT")
    azure_openai_responses_deployment_name: str | None = Field(
        None,
        alias="AZURE_OPENAI_RESPONSES_DEPLOYMENT_NAME",
    )
    azure_openai_endpoint: str | None = Field(None, alias="AZURE_OPENAI_ENDPOINT")
    azure_openai_api_key: str | None = Field(None, alias="AZURE_OPENAI_API_KEY")
    azure_openai_api_version: str | None = Field(None, alias="AZURE_OPENAI_API_VERSION")

    app_host: str = Field("0.0.0.0", alias="APP_HOST")
    app_port: int = Field(8010, alias="APP_PORT", ge=1, le=65535)
    app_log_level: str = Field("INFO", alias="APP_LOG_LEVEL")
    app_env: str = Field("development", alias="APP_ENV")

    azure_sql_connection_string: str | None = Field(None, alias="AZURE_SQL_CONNECTION_STRING")
    sql_query_timeout_seconds: int = Field(20, alias="SQL_QUERY_TIMEOUT_SECONDS", ge=1, le=120)
    sql_row_limit: int = Field(200, alias="SQL_ROW_LIMIT", ge=1, le=5000)
    sql_require_schema_catalog: bool = Field(
        False,
        alias="SQL_REQUIRE_SCHEMA_CATALOG",
    )
    sql_max_retry_corrections: int = Field(
        2,
        alias="SQL_MAX_RETRY_CORRECTIONS",
        ge=0,
        le=5,
    )

    hitl_sensitive_approval_enabled: bool = Field(
        True,
        alias="HITL_SENSITIVE_APPROVAL_ENABLED",
    )
    hitl_approval_timeout_seconds: int = Field(
        180,
        alias="HITL_APPROVAL_TIMEOUT_SECONDS",
        ge=15,
        le=3600,
    )
    hitl_llm_review_enabled: bool = Field(
        False,
        alias="HITL_LLM_REVIEW_ENABLED",
    )
    hitl_llm_review_timeout_seconds: int = Field(
        2,
        alias="HITL_LLM_REVIEW_TIMEOUT_SECONDS",
        ge=1,
        le=15,
    )
    hitl_policy_version: str = Field(
        "v1",
        alias="HITL_POLICY_VERSION",
        min_length=2,
        max_length=40,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
