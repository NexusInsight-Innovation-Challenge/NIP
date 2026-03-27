from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from azure.messaging.webpubsubservice import WebPubSubServiceClient

from app.config import Settings


@dataclass(slots=True)
class PubSubAccess:
    url: str
    user_id: str
    hub: str
    group: str


class PubSubService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = WebPubSubServiceClient.from_connection_string(
            settings.azure_webpubsub_connection_string,
            hub=settings.azure_webpubsub_hub,
        )

    @property
    def hub(self) -> str:
        return self._settings.azure_webpubsub_hub

    @property
    def group(self) -> str:
        return self._settings.azure_webpubsub_group

    def negotiate_client(self, user_id: str) -> PubSubAccess:
        roles = [
            f"webpubsub.joinLeaveGroup.{self.group}",
            f"webpubsub.sendToGroup.{self.group}",
        ]
        token_data = self._client.get_client_access_token(user_id=user_id, roles=roles)
        return PubSubAccess(url=token_data["url"], user_id=user_id, hub=self.hub, group=self.group)

    def negotiate_backend_listener(self, user_id: str = "backend-listener") -> PubSubAccess:
        roles = [
            f"webpubsub.joinLeaveGroup.{self.group}",
            f"webpubsub.sendToGroup.{self.group}",
        ]
        token_data = self._client.get_client_access_token(user_id=user_id, roles=roles)
        return PubSubAccess(url=token_data["url"], user_id=user_id, hub=self.hub, group=self.group)

    def send_json_to_group(self, message: dict[str, Any]) -> None:
        self._client.send_to_group(self.group, message, content_type="application/json")
