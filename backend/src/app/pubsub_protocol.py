from __future__ import annotations

from typing import Any


def join_group_message(group: str, ack_id: int = 1) -> dict[str, Any]:
    return {
        "type": "joinGroup",
        "group": group,
        "ackId": ack_id,
    }


def is_group_json_message(payload: dict[str, Any]) -> bool:
    return (
        payload.get("type") == "message"
        and payload.get("from") == "group"
        and payload.get("dataType") == "json"
        and isinstance(payload.get("data"), dict)
    )
