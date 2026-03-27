from __future__ import annotations

from importlib import import_module
from typing import Any

from app.config import Settings


class MicrosoftAgentFrameworkClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._agent: Any | None = None
        self._sdk_ready = False
        self._client_type: Any | None = None
        self._credential_type: Any | None = None
        self._load_sdk()

    @property
    def _has_key_auth(self) -> bool:
        return bool(self._settings.azure_openai_endpoint and self._settings.azure_openai_api_key)

    @property
    def _has_project_auth(self) -> bool:
        return bool(self._settings.azure_ai_project_endpoint)

    def _load_sdk(self) -> None:
        try:
            azure_module = import_module("agent_framework.azure")
            self._client_type = getattr(azure_module, "AzureOpenAIResponsesClient", None)
        except Exception:
            self._client_type = None

        if self._client_type is None:
            try:
                base_module = import_module("agent_framework")
                self._client_type = getattr(base_module, "AzureOpenAIResponsesClient", None)
            except Exception:
                self._client_type = None

        try:
            identity_module = import_module("azure.identity")
            self._credential_type = getattr(identity_module, "DefaultAzureCredential", None)
        except Exception:
            self._credential_type = None

        self._sdk_ready = self._client_type is not None

    @property
    def enabled(self) -> bool:
        return bool(
            self._sdk_ready
            and self._settings.azure_openai_responses_deployment_name
            and (self._has_key_auth or self._has_project_auth)
        )

    def _build_agent(self) -> Any:
        if not self.enabled:
            raise RuntimeError(
                "Microsoft Agent Framework config is incomplete. "
                "Provide deployment name plus either: "
                "(AZURE_OPENAI_ENDPOINT + AZURE_OPENAI_API_KEY) or AZURE_AI_PROJECT_ENDPOINT."
            )

        deployment_name = self._settings.azure_openai_responses_deployment_name
        assert deployment_name is not None
        assert self._client_type is not None

        if self._has_key_auth:
            client = self._client_type(
                endpoint=self._settings.azure_openai_endpoint,
                deployment_name=deployment_name,
                api_key=self._settings.azure_openai_api_key,
                api_version=self._settings.azure_openai_api_version,
            )
        else:
            if self._credential_type is None:
                raise RuntimeError("azure.identity is required for project-endpoint authentication")

            credential = self._credential_type(
                exclude_cli_credential=True,
                exclude_interactive_browser_credential=True,
                exclude_shared_token_cache_credential=True,
                exclude_visual_studio_code_credential=True,
            )
            client = self._client_type(
                project_endpoint=self._settings.azure_ai_project_endpoint,
                deployment_name=deployment_name,
                credential=credential,
            )

        return client.as_agent(
            name="RealtimeResponseAgent",
            instructions=(
                "You are a concise enterprise assistant. "
                "Answer in Spanish with practical next steps."
            ),
        )

    async def generate(self, prompt: str) -> str:
        if not self.enabled:
            raise RuntimeError("Microsoft Agent Framework not enabled")

        if self._agent is None:
            self._agent = self._build_agent()

        result = await self._agent.run(prompt)
        response_text = str(result).strip()
        if not response_text:
            raise RuntimeError("Microsoft Agent Framework returned an empty response")
        return response_text
