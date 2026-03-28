from app.models import EventType, MessageEnvelope, UserMessageInput


def test_user_message_input_strips_and_validates() -> None:
    payload = UserMessageInput(message=" hola mundo ", user_id="u1")
    assert payload.message == "hola mundo"


def test_message_envelope_defaults() -> None:
    envelope = MessageEnvelope(
        event_type=EventType.USER_MESSAGE,
        role="user",
        payload={"message": "x"},
    )
    assert envelope.event_type == EventType.USER_MESSAGE
    assert envelope.id
    assert envelope.correlation_id
    assert envelope.conversation_id


def test_approval_event_types_available() -> None:
    assert EventType.APPROVAL_REQUIRED.value == "approval.required"
    assert EventType.APPROVAL_RESPONSE.value == "approval.response"
    assert EventType.APPROVAL_FINALIZED.value == "approval.finalized"
