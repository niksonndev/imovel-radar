from send_final_notice import announcement_message


def test_announcement_directs_users_to_whatsapp_and_updates() -> None:
    message = announcement_message("https://example.com/")

    assert "canal de atendimento pelo Telegram será encerrado" in message
    assert "https://wa.me/5582993345293" in message
    assert "não serão transferidos" in message
    assert "https://example.com/novidades" in message
