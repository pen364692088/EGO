from app.interaction.normalize_user_turn import normalize_user_turn
from app.runtime_v2.semantic_parser import is_presence_probe_text, parse_session_control_intent


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
    assert intent.kind == "execute_task"

    replace_intent = parse_session_control_intent("  替 换 。")
    assert replace_intent.kind == "execute_task"
    assert replace_intent.resolution is None


def test_parse_session_control_intent_presence_probes_do_not_enter_control_plane() -> None:
    chat_intent = parse_session_control_intent("在吗")
    assert chat_intent.kind == "execute_task"

    chat_intent_2 = parse_session_control_intent("还在吗")
    assert chat_intent_2.kind == "execute_task"

    assert is_presence_probe_text("在吗") is True
    assert is_presence_probe_text("还在吗") is True
