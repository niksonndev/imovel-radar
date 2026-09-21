from handlers.create_new_alert import new_alert_conversation


def test_new_alert_conversation_is_persistent() -> None:
    handler = new_alert_conversation()
    assert handler.name == "new_alert"
    assert handler.persistent is True
    assert handler.allow_reentry is True
