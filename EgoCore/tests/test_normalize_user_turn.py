from app.interaction.normalize_user_turn import normalize_user_turn
from app.runtime_v2.semantic_parser import parse_session_control_intent


def test_normalize_user_turn_compacts_control_probe_and_extracts_path() -> None:
    turn = normalize_user_turn('  继 续 ！？  在 D:\\Project\\AIProject\\MyProject\\Test2\\demo.txt 看一下  ')

    assert turn.text == '继 续 ！？  在 D:\\Project\\AIProject\\MyProject\\Test2\\demo.txt 看一下'
    assert turn.probe_key.startswith("继续")
    assert turn.control_key.startswith("继续")
    assert turn.explicit_paths == (r"D:\Project\AIProject\MyProject\Test2\demo.txt",)


def test_normalize_user_turn_marks_attachment_and_slash_command() -> None:
    turn = normalize_user_turn("  /new [附件: demo.txt]  ")

    assert turn.is_slash_command is True
    assert turn.has_attachment is True


def test_parse_session_control_intent_uses_normalized_turn() -> None:
    intent = parse_session_control_intent("  继 续 ！？  ")
    assert intent.kind == "manual_resume"

    replace_intent = parse_session_control_intent("  替 换 。")
    assert replace_intent.kind == "task_conflict_resolution"
    assert replace_intent.resolution == "replace"


def test_parse_session_control_intent_treats_zai_ma_as_chat_ping() -> None:
    chat_intent = parse_session_control_intent("在吗")
    assert chat_intent.kind == "chat_ping"

    status_intent = parse_session_control_intent("还在吗")
    assert status_intent.kind == "status_probe"
