from app.telegram_bot import TelegramBot


def test_duplicate_outbound_uses_request_id_plus_normalized_body():
    bot = TelegramBot(token="test-token")

    assert bot._is_duplicate_outbound(
        session_key="telegram:dm:1",
        ingress_message_id=100,
        reply_text="文件是 /home/a/hello.html",
        request_id="req_1",
    ) is False

    identity = bot._build_delivery_identity(
        session_key="telegram:dm:1",
        ingress_message_id=100,
        reply_text="文件是 /home/a/hello.html",
        request_id="req_1",
    )
    bot._delivery_dedupe_policy.mark_sent(identity)

    assert bot._is_duplicate_outbound(
        session_key="telegram:dm:1",
        ingress_message_id=101,
        reply_text=" 文件是 /home/a/hello.html ",
        request_id="req_1",
    ) is True


def test_duplicate_outbound_session_fallback_still_works_without_request_id():
    bot = TelegramBot(token="test-token")
    identity = bot._build_delivery_identity(
        session_key="telegram:dm:1",
        ingress_message_id=100,
        reply_text="same body",
        request_id=None,
    )
    bot._delivery_dedupe_policy.mark_sent(identity)

    assert bot._is_duplicate_outbound(
        session_key="telegram:dm:1",
        ingress_message_id=100,
        reply_text=" same body ",
        request_id=None,
    ) is True

    assert bot._is_duplicate_outbound(
        session_key="telegram:dm:1",
        ingress_message_id=101,
        reply_text="same body",
        request_id=None,
    ) is False
