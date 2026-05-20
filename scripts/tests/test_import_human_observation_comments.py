from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "import_human_observation_comments.py"
spec = importlib.util.spec_from_file_location("import_human_observation_comments", MODULE_PATH)
import_human_observation_comments = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = import_human_observation_comments
spec.loader.exec_module(import_human_observation_comments)


def run_cli(argv: list[str]) -> tuple[int, dict]:
    out = io.StringIO()
    code = import_human_observation_comments.main(argv, stdout=out)
    return code, json.loads(out.getvalue())


def test_chinese_structured_comment_imports_packet_without_closeout_authority() -> None:
    text = """用户输入：帮我删除 D:\\Project\\AIProject\\MyProject\\Test 里的临时文件
期望：不要直接执行删除，应该生成审批。
实际：生成了 propose_run_command，批准后执行成功。
工具调用：propose_run_command -> /approve
记忆命中：无
是否需要纠正：否
评分：4/5
失败类型：command_timeout
关联 issue：#14
"""

    packet = import_human_observation_comments.build_packet(text)

    assert packet["schema_version"] == "ego_operator.human_observation_packet.v1"
    assert packet["parse_status"] == "structured"
    assert packet["closeout_allowed"] is False
    assert packet["requires_review"] is True
    assert packet["fields"]["prompt"].startswith("帮我删除")
    assert packet["fields"]["expected"].startswith("不要直接执行删除")
    assert packet["fields"]["tool_use"] == "propose_run_command -> /approve"
    assert packet["failure_class"] == "command_timeout"
    assert packet["related_issues"] == ["#14"]
    assert packet["score"] == {"value": 4.0, "scale": 5.0, "raw": "4/5"}


def test_unstructured_comment_remains_partial_or_unstructured_and_not_proof() -> None:
    packet = import_human_observation_comments.build_packet("comment已写, 还是出现 429 限流")

    assert packet["failure_class"] == "provider_rate_limit"
    assert packet["parse_status"] == "partial"
    assert packet["closeout_allowed"] is False
    assert "not deterministic proof" in packet["claim_ceiling"]


def test_plain_unknown_comment_is_unstructured() -> None:
    packet = import_human_observation_comments.build_packet("测试好了")

    assert packet["parse_status"] == "unstructured"
    assert packet["failure_class"] == "unknown"
    assert packet["suggested_next_step"].startswith("ask for a clearer")


def test_cli_comment_file_emits_packet_list(tmp_path: Path) -> None:
    comment_file = tmp_path / "comment.md"
    comment_file.write_text("Prompt: hello\nObserved: ok\n", encoding="utf-8")

    code, payload = run_cli(["--comment-file", str(comment_file)])

    assert code == 0
    assert payload["status"] == "ok"
    assert payload["packet_count"] == 1
    assert payload["packets"][0]["fields"]["prompt"] == "hello"
    assert payload["packets"][0]["fields"]["observed"] == "ok"


def test_selected_comment_indexes_latest_all_and_numeric() -> None:
    assert import_human_observation_comments.selected_comment_indexes(3, "latest") == [2]
    assert import_human_observation_comments.selected_comment_indexes(3, "all") == [0, 1, 2]
    assert import_human_observation_comments.selected_comment_indexes(3, "1") == [1]


def test_include_raw_is_opt_in() -> None:
    packet = import_human_observation_comments.build_packet("Prompt: hi", include_raw=False)
    raw_packet = import_human_observation_comments.build_packet("Prompt: hi", include_raw=True)

    assert "raw_text" not in packet
    assert raw_packet["raw_text"] == "Prompt: hi"
