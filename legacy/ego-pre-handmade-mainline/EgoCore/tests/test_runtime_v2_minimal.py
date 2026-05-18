import json
from pathlib import Path

import pytest

from app.runtime_v2.action_protocol import RuntimeV2Action
from app.runtime_v2.loop import RuntimeV2Loop
from app.runtime_v2.run_items import (
    RunConflictState,
    RunItem,
    build_run_item_summary_text,
    build_run_item_verified_text,
    build_run_items_from_request,
    current_date_string,
)
from app.runtime_v2.semantic_parser import build_runtime_status_reply
from app.runtime_v2.state import RuntimeV2State
from app.runtime_v2.transition import _build_host_completion_summary
from app.runtime_v2.verifier import RuntimeV2Verifier


def test_action_protocol_parses_complete_json():
    action = RuntimeV2Action.from_model_output('{"type":"complete","summary":"done","verification":{"target":"/tmp/x"}}')
    assert action.type == "complete"
    assert action.summary == "done"
    assert action.verification["target"] == "/tmp/x"


def test_verifier_fails_when_target_missing(tmp_path):
    verifier = RuntimeV2Verifier()
    result = verifier.verify_complete({"target": str(tmp_path / 'missing.html')}, None)
    assert result["passed"] is False


@pytest.mark.asyncio
async def test_runtime_v2_loop_runs_plan_act_complete(monkeypatch, tmp_path):
    loop = RuntimeV2Loop()
    target = tmp_path / "hello.html"
    target.write_text("background: modern", encoding="utf-8")

    actions = iter([
        RuntimeV2Action.from_model_output(
            json.dumps({"type": "plan", "goal": "改配色", "steps": ["修改文件", "验证结果"]}, ensure_ascii=False)
        ),
        RuntimeV2Action.from_model_output(
            json.dumps(
                {
                    "type": "act",
                    "tool": "file",
                    "input": {"operation": "read", "path": str(target)},
                },
                ensure_ascii=False,
            )
        ),
        RuntimeV2Action.from_model_output(
            json.dumps(
                {
                    "type": "complete",
                    "summary": "已完成",
                    "verification": {"target": str(target), "expected": "modern"},
                },
                ensure_ascii=False,
            )
        ),
    ])

    async def fake_decide(_state):
        return next(actions)

    async def fake_execute(_tool, _tool_input):
        return {"success": True, "tool": "file", "stdout": "background: modern", "stderr": "", "exit_code": 0, "metadata": {}}

    monkeypatch.setattr(loop, "_decide", fake_decide)
    monkeypatch.setattr(loop.tool_broker, "execute", fake_execute)
    result = await loop.run_turn_typed("session:test", "请修改 hello.html 配色")
    assert result.status == "completed_verified"
    assert result.reply_text == "已完成"


@pytest.mark.asyncio
async def test_runtime_v2_loop_emits_progress_callback_during_turn(monkeypatch, tmp_path):
    loop = RuntimeV2Loop()
    target = tmp_path / "hello.html"
    target.write_text("background: modern", encoding="utf-8")

    actions = iter([
        RuntimeV2Action.from_model_output(
            json.dumps({"type": "plan", "goal": "改配色", "steps": ["修改文件", "验证结果"]}, ensure_ascii=False)
        ),
        RuntimeV2Action.from_model_output(
            json.dumps(
                {
                    "type": "act",
                    "tool": "file",
                    "input": {"operation": "read", "path": str(target)},
                },
                ensure_ascii=False,
            )
        ),
        RuntimeV2Action.from_model_output(
            json.dumps(
                {
                    "type": "complete",
                    "summary": "已完成",
                    "verification": {"target": str(target), "expected": "modern"},
                },
                ensure_ascii=False,
            )
        ),
    ])
    emitted = []

    async def fake_decide(_state):
        return next(actions)

    async def fake_execute(_tool, _tool_input):
        return {"success": True, "tool": "file", "stdout": "background: modern", "stderr": "", "exit_code": 0, "metadata": {}}

    async def progress_callback(event):
        emitted.append((event.event_type.value, event.message))

    monkeypatch.setattr(loop, "_decide", fake_decide)
    monkeypatch.setattr(loop.tool_broker, "execute", fake_execute)

    result = await loop.run_turn_typed(
        "session:test-progress",
        "请修改 hello.html 配色",
        progress_callback=progress_callback,
    )

    assert result.status == "completed_verified"
    assert emitted == [
        ("executing_changes", "我先处理需要的文件。"),
        ("verifying", "我先验证一下结果。"),
    ]


@pytest.mark.asyncio
async def test_runtime_v2_loop_rejects_complete_when_explicit_output_missing(monkeypatch, tmp_path):
    loop = RuntimeV2Loop()
    state = loop.get_state("session:missing-output")
    state.ingress_context = {
        "runtime_action": "execute_task",
        "resolved_target": {"path": str(tmp_path)},
    }

    actions = iter([
        RuntimeV2Action.from_model_output(
            json.dumps(
                {
                    "type": "act",
                    "tool": "file",
                    "input": {"operation": "write", "path": str(tmp_path / "demo.txt"), "content": "hello"},
                },
                ensure_ascii=False,
            )
        ),
        RuntimeV2Action.from_model_output(
            json.dumps(
                {
                    "type": "complete",
                    "summary": "全部完成",
                    "verification": {"target": str(tmp_path / "demo.txt"), "expected": "hello"},
                },
                ensure_ascii=False,
            )
        ),
    ])

    async def fake_decide(_state):
        return next(actions)

    async def fake_execute(_tool, tool_input):
        path = tmp_path / "demo.txt"
        path.write_text(tool_input["content"], encoding="utf-8")
        return {
            "success": True,
            "tool": "file",
            "stdout": f"Successfully wrote to {path}",
            "stderr": "",
            "exit_code": 0,
            "metadata": {"path": str(path)},
        }

    monkeypatch.setattr(loop, "_decide", fake_decide)
    monkeypatch.setattr(loop.tool_broker, "execute", fake_execute)

    prompt = (
        f"在 {tmp_path} 目录下创建 demo.txt，写入 hello。"
        " 最后做一个print hello world.py文件"
    )
    result = await loop.run_turn_typed("session:missing-output", prompt, max_steps=2)

    assert result.status == "resumable_pause"
    assert state.last_verification_result["reason"] == "declared_output_missing"
    assert "print hello world.py" in state.last_verification_result["evidence"]["missing_outputs"]


def test_runtime_v2_loop_promotes_explicit_analyze_shell_read_to_file_read():
    loop = RuntimeV2Loop()
    target = r"D:\Project\AIProject\MyProject\Ego\PROJECT_MEMORY.md"
    state = RuntimeV2State(session_id="session:explicit-read")
    state.ingress_context = {
        "request_mode": "analyze",
        "runtime_action": "execute_task",
        "resolved_target": {
            "source": "explicit_path",
            "path": target,
            "filename": "PROJECT_MEMORY.md",
        },
    }
    action = RuntimeV2Action.from_model_output(
        json.dumps(
            {
                "type": "act",
                "tool": "shell",
                "input": {"command": f'type "{target}"'},
            },
            ensure_ascii=False,
        )
    )

    normalized = loop._normalize_action_for_host_contract(state, action)

    assert normalized.tool == "file"
    assert normalized.input == {"operation": "read", "path": target}
    assert normalized.raw["host_normalization"]["kind"] == "explicit_path_analyze_promoted_to_file_read"


def test_build_run_items_from_request_preserves_user_order_and_verify_target(tmp_path):
    prompt = (
        f"在 {tmp_path} 目录下创建 demo.txt，写入三行内容：第一行是 hello，第二行是当前日期，第三行是 autonomous chain test。"
        "然后读取这个文件确认内容。然后再创建一个参照youtube的html页面,只是看着像,不用做真正的功能."
        "最后做一个print hello world.py文件"
    )

    items = build_run_items_from_request(
        prompt,
        ingress_context={
            "runtime_action": "execute_task",
            "requested_output": {"target_directory": str(tmp_path)},
        },
    )

    assert [(item.kind, item.canonical_path.split("\\")[-1].split("/")[-1]) for item in items] == [
        ("file_write", "demo.txt"),
        ("file_verify", "demo.txt"),
        ("page_generate", "youtube_lookalike.html"),
        ("script_generate", "print hello world.py"),
    ]
    assert items[1].metadata["verify_source_item_id"] == items[0].item_id


def test_build_run_items_marks_structured_file_and_verify_as_host_deterministic(tmp_path):
    prompt = (
        f"在 {tmp_path} 目录下创建 demo.txt，写入三行内容：第一行是 hello，第二行是当前日期，第三行是 autonomous chain test。"
        "然后读取这个文件确认内容。然后再创建一个参照youtube的html页面,只是看着像,不用做真正的功能."
    )

    items = build_run_items_from_request(
        prompt,
        ingress_context={
            "runtime_action": "execute_task",
            "requested_output": {"target_directory": str(tmp_path)},
        },
    )

    assert [item.execution_mode for item in items] == [
        "host_deterministic",
        "host_deterministic",
        "model_driven",
    ]


def test_begin_execute_task_resets_task_scoped_state(tmp_path):
    state = RuntimeV2State(session_id="session:begin-execute")
    state.task_status = "blocked"
    state.current_goal = "旧的 bilibili 页面任务"
    state.current_step = "tool:file"
    state.waiting_for_user_input = True
    state.last_model_action = {"type": "act"}
    state.last_tool_result = {"metadata": {"path": str(tmp_path / "old.html")}}
    state.last_verification_result = {"reason": "run_items_verified"}
    state.task_contract = {"goal": "old"}
    state.next_step_decision = {"action_type": "file"}
    state.verification_history = [{"reason": "old"}]
    state.current_step_number = 3
    state.total_steps_planned = 5
    state.pending_progress_events = ["stale-progress"]
    state.pending_run_events = [{"event_type": "item_started", "text": "old"}]
    state.active_item_id = "stale-item"
    state.ingress_context = {
        "runtime_action": "execute_task",
        "requested_output": {"target_directory": str(tmp_path)},
    }

    run_items = build_run_items_from_request(
        f"在 {tmp_path} 目录下创建 demo.txt。",
        ingress_context=state.ingress_context,
    )

    state.begin_execute_task(
        f"在 {tmp_path} 目录下创建 demo.txt。",
        run_items,
        state.ingress_context,
    )

    snapshot = state.to_snapshot()
    assert snapshot["current_goal"] == f"在 {tmp_path} 目录下创建 demo.txt。"
    assert snapshot["current_step"] is None
    assert snapshot["last_verification_result"] is None
    assert state.pending_progress_events == []
    assert snapshot["pending_run_events"] == []
    assert snapshot["active_item_id"] is None
    assert snapshot["run_items"][0]["canonical_path"].endswith("demo.txt")


@pytest.mark.asyncio
async def test_runtime_v2_loop_emits_ordered_run_item_events_during_turn(monkeypatch, tmp_path):
    loop = RuntimeV2Loop()
    prompt = (
        f"在 {tmp_path} 目录下创建 demo.txt，写入 hello。"
        "然后再创建一个print hello world.py文件"
    )
    state = loop.get_state("session:run-items")
    state.ingress_context = {
        "runtime_action": "execute_task",
        "requested_output": {"target_directory": str(tmp_path)},
    }
    state.set_run_items(build_run_items_from_request(prompt, ingress_context=state.ingress_context))

    actions = iter(
        [
            RuntimeV2Action.from_model_output(
                json.dumps(
                    {
                        "type": "act",
                        "tool": "file",
                        "input": {"operation": "write", "path": str(tmp_path / "demo.txt"), "content": "hello"},
                    },
                    ensure_ascii=False,
                )
            ),
            RuntimeV2Action.from_model_output(
                json.dumps(
                    {
                        "type": "complete",
                        "summary": "demo 完成",
                        "verification": {"target": str(tmp_path / "demo.txt"), "expected": "hello"},
                    },
                    ensure_ascii=False,
                )
            ),
            RuntimeV2Action.from_model_output(
                json.dumps(
                    {
                        "type": "act",
                        "tool": "file",
                        "input": {
                            "operation": "write",
                            "path": str(tmp_path / "print hello world.py"),
                            "content": 'print("hello world")',
                        },
                    },
                    ensure_ascii=False,
                )
            ),
            RuntimeV2Action.from_model_output(
                json.dumps(
                    {
                        "type": "complete",
                        "summary": "脚本完成",
                        "verification": {"target": str(tmp_path / "print hello world.py"), "expected": "hello world"},
                    },
                    ensure_ascii=False,
                )
            ),
        ]
    )
    run_events = []

    async def fake_decide(_state):
        return next(actions)

    async def fake_execute(_tool, tool_input):
        path = tmp_path / Path(tool_input["path"]).name
        path.write_text(tool_input["content"], encoding="utf-8")
        return {
            "success": True,
            "tool": "file",
            "stdout": f"Successfully wrote to {path}",
            "stderr": "",
            "exit_code": 0,
            "metadata": {"path": str(path)},
        }

    async def run_event_callback(event):
        run_events.append((event.event_type, event.text))

    monkeypatch.setattr(loop, "_decide", fake_decide)
    monkeypatch.setattr(loop.tool_broker, "execute", fake_execute)

    result = await loop.run_turn_typed(
        "session:run-items",
        prompt,
        max_steps=4,
        run_event_callback=run_event_callback,
    )

    assert result.status == "completed_verified"
    assert run_events == [
        ("item_started", "开始处理 demo.txt。"),
        ("item_verified", "已写入 demo.txt。"),
        ("item_started", "开始处理 print hello world.py。"),
        ("item_verified", "已验证 print hello world.py。"),
    ]


def test_runtime_status_reply_prefers_run_items_and_pending_conflict_over_stale_goal(tmp_path):
    state = RuntimeV2State(session_id="session:status")
    state.current_goal = "旧的 bilibili 页面任务"
    state.current_step = "tool:file"
    state.ingress_context = {
        "runtime_action": "execute_task",
        "requested_output": {"target_directory": str(tmp_path)},
    }
    state.set_run_items(
        build_run_items_from_request(
            f"在 {tmp_path} 目录下创建 demo.txt。最后做一个print hello world.py文件",
            ingress_context=state.ingress_context,
        )
    )
    state.ensure_active_run_item_started()

    reply = build_runtime_status_reply(state)
    assert "demo.txt" in reply
    assert "print hello world.py" in reply
    assert "bilibili" not in reply

    state.set_pending_task_conflict(
        RunConflictState(
            existing_run_id="run_1",
            existing_objective="旧任务",
            incoming_text="新任务：创建 youtube 页面",
            incoming_run_items=[],
        )
    )
    conflict_reply = build_runtime_status_reply(state)
    assert "待确认的新任务" in conflict_reply
    assert "替换" in conflict_reply


def test_verify_run_item_requires_observed_file_read(tmp_path):
    state = RuntimeV2State(session_id="session:verify-item")
    state.ingress_context = {
        "runtime_action": "execute_task",
        "requested_output": {"target_directory": str(tmp_path)},
    }
    target = tmp_path / "demo.txt"
    target.write_text(
        f"hello\n{current_date_string()}\nautonomous chain test",
        encoding="utf-8",
    )

    state.set_run_items(
        build_run_items_from_request(
            f"在 {tmp_path} 目录下创建 demo.txt，写入三行内容：第一行是 hello，第二行是当前日期，第三行是 autonomous chain test。然后读取这个文件确认内容。",
            ingress_context=state.ingress_context,
        )
    )
    state.ensure_active_run_item_started()
    state.mark_active_run_item_verified({"passed": True, "reason": "run_item_verified"})
    verify_item = state.ensure_active_run_item_started()

    assert verify_item is not None
    assert verify_item.kind == "file_verify"
    assert verify_item.execution_mode == "host_deterministic"

    observation = state.observe_active_run_item_progress()
    assert observation["reason"] == "verify_read_pending"
    assert state.get_active_run_item() is not None
    assert state.get_active_run_item().status == "running"

    observation = state.observe_active_run_item_progress(
        tool_result={
            "success": True,
            "tool": "file",
            "stdout": target.read_text(encoding="utf-8"),
            "stderr": "",
            "exit_code": 0,
            "metadata": {"path": str(target)},
        },
        tool_name="file",
        tool_input={"operation": "read", "path": str(target)},
    )

    assert observation["reason"] == "verify_read_observed"
    assert state.get_active_run_item() is not None
    assert state.get_active_run_item().status == "completed"


@pytest.mark.asyncio
async def test_runtime_v2_loop_blocks_when_tool_writes_non_frontier_path(monkeypatch, tmp_path):
    loop = RuntimeV2Loop()
    state = loop.get_state("session:frontier-authority")
    prompt = (
        f"在 {tmp_path} 目录下创建 demo.txt，写入 hello。"
        "然后再创建一个参照youtube的html页面,只是看着像,不用做真正的功能."
    )
    state.ingress_context = {
        "runtime_action": "execute_task",
        "requested_output": {"target_directory": str(tmp_path)},
    }
    state.begin_execute_task(prompt, build_run_items_from_request(prompt, ingress_context=state.ingress_context), state.ingress_context)

    actions = iter(
        [
            RuntimeV2Action.from_model_output(
                json.dumps(
                    {
                        "type": "act",
                        "tool": "file",
                        "input": {
                            "operation": "write",
                            "path": str(tmp_path / "youtube_lookalike.html"),
                            "content": "<html><body>youtube</body></html>",
                        },
                    },
                    ensure_ascii=False,
                )
            ),
        ]
    )

    async def fake_decide(_state):
        return next(actions)

    async def fake_execute(_tool, tool_input):
        path = Path(tool_input["path"])
        path.write_text(tool_input["content"], encoding="utf-8")
        return {
            "success": True,
            "tool": "file",
            "stdout": f"Successfully wrote to {path}",
            "stderr": "",
            "exit_code": 0,
            "metadata": {"path": str(path)},
        }

    monkeypatch.setattr(loop, "_decide", fake_decide)
    monkeypatch.setattr(loop.tool_broker, "execute", fake_execute)

    result = await loop.run_turn_typed("session:frontier-authority", prompt, max_steps=1)

    assert result.status == "blocked"
    assert state.last_verification_result["reason"] == "blocked_unexpected_output_path"
    assert state.last_verification_result["target"].endswith("demo.txt")
    assert state.last_verification_result["evidence"]["actual_path"].endswith("youtube_lookalike.html")


@pytest.mark.asyncio
async def test_runtime_v2_loop_promotes_frontier_after_write_without_model_complete(monkeypatch, tmp_path):
    loop = RuntimeV2Loop()
    prompt = (
        f"在 {tmp_path} 目录下创建 demo.txt，写入三行内容：第一行是 hello，第二行是当前日期，第三行是 autonomous chain test。"
        "然后读取这个文件确认内容。然后再创建一个参照youtube的html页面,只是看着像,不用做真正的功能."
        "最后做一个print hello world.py文件"
    )
    state = loop.get_state("session:frontier-promotion")
    state.ingress_context = {
        "runtime_action": "execute_task",
        "requested_output": {"target_directory": str(tmp_path)},
    }
    state.begin_execute_task(prompt, build_run_items_from_request(prompt, ingress_context=state.ingress_context), state.ingress_context)

    actions = iter(
        [
            RuntimeV2Action.from_model_output(
                json.dumps(
                    {
                        "type": "act",
                        "tool": "file",
                        "input": {
                            "operation": "write",
                            "path": str(tmp_path / "youtube_lookalike.html"),
                            "content": "<!doctype html><html><body>youtube</body></html>",
                        },
                    },
                    ensure_ascii=False,
                )
            ),
        ]
    )
    run_events = []

    async def fake_decide(_state):
        active_item = _state.get_active_run_item()
        assert active_item is not None
        assert active_item.kind == "page_generate"
        assert active_item.canonical_path.endswith("youtube_lookalike.html")
        assert (tmp_path / "demo.txt").read_text(encoding="utf-8") == (
            f"hello\n{current_date_string()}\nautonomous chain test"
        )
        return next(actions)

    async def fake_execute(_tool, tool_input):
        path = Path(tool_input["path"])
        path.write_text(tool_input["content"], encoding="utf-8")
        return {
            "success": True,
            "tool": "file",
            "stdout": f"Successfully wrote to {path}",
            "stderr": "",
            "exit_code": 0,
            "metadata": {"path": str(path)},
        }

    async def run_event_callback(event):
        run_events.append((event.event_type, event.text))

    monkeypatch.setattr(loop, "_decide", fake_decide)
    monkeypatch.setattr(loop.tool_broker, "execute", fake_execute)

    result = await loop.run_turn_typed(
        "session:frontier-promotion",
        prompt,
        max_steps=1,
        run_event_callback=run_event_callback,
    )

    assert result.status == "resumable_pause"
    active_item = state.get_active_run_item()
    assert active_item is not None
    assert active_item.kind == "script_generate"
    assert active_item.description == "创建 print hello world.py"
    assert state.active_item_id == active_item.item_id
    assert run_events == [
        ("item_started", "开始处理 demo.txt。"),
        ("item_verified", "已写入 demo.txt。"),
        ("item_started", "开始验证 demo.txt。"),
        ("item_verified", "已确认 demo.txt 内容。"),
        ("item_started", "开始处理 youtube_lookalike.html。"),
        ("item_verified", "已验证 youtube_lookalike.html。"),
        ("item_started", "开始处理 print hello world.py。"),
    ]


@pytest.mark.asyncio
async def test_runtime_v2_loop_completes_host_owned_run_items_even_if_model_complete_has_no_target(monkeypatch, tmp_path):
    loop = RuntimeV2Loop()
    prompt = (
        f"在 {tmp_path} 目录下创建 demo.txt，写入三行内容：第一行是 hello，第二行是当前日期，第三行是 autonomous chain test。"
        "然后读取这个文件确认内容。然后再创建一个参照youtube的html页面,只是看着像,不用做真正的功能."
        "最后做一个print hello world.py文件"
    )
    state = loop.get_state("session:host-owned-complete")
    state.ingress_context = {
        "runtime_action": "execute_task",
        "requested_output": {"target_directory": str(tmp_path)},
    }
    state.begin_execute_task(prompt, build_run_items_from_request(prompt, ingress_context=state.ingress_context), state.ingress_context)

    actions = iter(
        [
            RuntimeV2Action.from_model_output(
                json.dumps(
                    {
                        "type": "act",
                        "tool": "file",
                        "input": {
                            "operation": "write",
                            "path": str(tmp_path / "youtube_lookalike.html"),
                            "content": "<!doctype html><html><body>youtube</body></html>",
                        },
                    },
                    ensure_ascii=False,
                )
            ),
            RuntimeV2Action.from_model_output(
                json.dumps(
                    {
                        "type": "act",
                        "tool": "file",
                        "input": {
                            "operation": "write",
                            "path": str(tmp_path / "print hello world.py"),
                            "content": 'print("hello world")\n',
                        },
                    },
                    ensure_ascii=False,
                )
            ),
            RuntimeV2Action.from_model_output(
                json.dumps(
                    {
                        "type": "complete",
                        "summary": "全部完成",
                        "verification": {},
                    },
                    ensure_ascii=False,
                )
            ),
        ]
    )

    async def fake_decide(_state):
        return next(actions)

    async def fake_execute(_tool, tool_input):
        path = Path(tool_input["path"])
        path.write_text(tool_input["content"], encoding="utf-8")
        return {
            "success": True,
            "tool": "file",
            "stdout": f"Successfully wrote to {path}",
            "stderr": "",
            "exit_code": 0,
            "metadata": {"path": str(path)},
        }

    monkeypatch.setattr(loop, "_decide", fake_decide)
    monkeypatch.setattr(loop.tool_broker, "execute", fake_execute)

    result = await loop.run_turn_typed(
        "session:host-owned-complete",
        prompt,
        max_steps=3,
    )

    assert result.status == "completed_verified"
    assert result.reply_text == "\n".join(
        [
            "已完成这些任务：",
            "1. 已写入 demo.txt",
            "2. 已确认 demo.txt 内容",
            "3. 已验证 youtube_lookalike.html",
            "4. 已验证 print hello world.py",
        ]
    )
    assert state.last_verification_result["reason"] == "run_items_verified"


def test_run_item_rendering_distinguishes_write_and_verify():
    write_item = RunItem(
        item_id="item_write",
        order_index=1,
        kind="file_write",
        description="创建 demo.txt",
        canonical_path=r"D:\Project\AIProject\MyProject\Test2\demo.txt",
    )
    verify_item = RunItem(
        item_id="item_verify",
        order_index=2,
        kind="file_verify",
        description="验证 demo.txt",
        canonical_path=r"D:\Project\AIProject\MyProject\Test2\demo.txt",
    )

    assert build_run_item_summary_text(write_item) == "已写入 demo.txt"
    assert build_run_item_verified_text(write_item) == "已写入 demo.txt。"
    assert build_run_item_summary_text(verify_item) == "已确认 demo.txt 内容"
    assert build_run_item_verified_text(verify_item) == "已确认 demo.txt 内容。"


def test_host_completion_summary_uses_item_semantics(tmp_path):
    state = RuntimeV2State(session_id="session:completion-summary")
    prompt = (
        f"在 {tmp_path} 目录下创建 demo.txt，写入三行内容：第一行是 hello，第二行是当前日期，第三行是 autonomous chain test。"
        "然后读取这个文件确认内容。然后再创建一个参照youtube的html页面,只是看着像,不用做真正的功能."
        "最后做一个print hello world.py文件"
    )
    state.ingress_context = {
        "runtime_action": "execute_task",
        "requested_output": {"target_directory": str(tmp_path)},
    }
    state.begin_execute_task(prompt, build_run_items_from_request(prompt, ingress_context=state.ingress_context), state.ingress_context)
    items = state.get_run_items()
    for item in items:
        item.status = "verified"
    state.set_run_items(items)

    assert _build_host_completion_summary(state, None) == "\n".join(
        [
            "已完成这些任务：",
            "1. 已写入 demo.txt",
            "2. 已确认 demo.txt 内容",
            "3. 已验证 youtube_lookalike.html",
            "4. 已验证 print hello world.py",
        ]
    )


def test_host_deterministic_verify_reuses_frozen_current_date(monkeypatch, tmp_path):
    state = RuntimeV2State(session_id="session:frozen-date")
    prompt = (
        f"在 {tmp_path} 目录下创建 demo.txt，写入三行内容：第一行是 hello，第二行是当前日期，第三行是 autonomous chain test。"
        "然后读取这个文件确认内容。"
    )
    state.ingress_context = {
        "runtime_action": "execute_task",
        "requested_output": {"target_directory": str(tmp_path)},
    }
    state.begin_execute_task(prompt, build_run_items_from_request(prompt, ingress_context=state.ingress_context), state.ingress_context)

    write_item = state.ensure_active_run_item_started()
    assert write_item is not None
    frozen_date = write_item.resolved_values["current_date"]

    monkeypatch.setattr("app.runtime_v2.run_items.current_date_string", lambda: "2099-01-01")

    first_promotion = state.advance_run_item_frontier()
    assert first_promotion["blocked"] is False
    assert state.get_active_run_item() is None
    verify_item = state.get_run_items()[1]
    assert verify_item.kind == "file_verify"
    assert verify_item.resolved_values["current_date"] == frozen_date
    assert verify_item.status == "verified"


@pytest.mark.asyncio
async def test_runtime_v2_loop_executes_explicit_analyze_with_file_tool(monkeypatch):
    loop = RuntimeV2Loop()
    target = r"D:\Project\AIProject\MyProject\Ego\PROJECT_MEMORY.md"
    state = loop.get_state("session:explicit-read-turn")
    state.ingress_context = {
        "request_mode": "analyze",
        "runtime_action": "execute_task",
        "resolved_target": {
            "source": "explicit_path",
            "path": target,
            "filename": "PROJECT_MEMORY.md",
        },
    }

    actions = iter(
        [
            RuntimeV2Action.from_model_output(
                json.dumps(
                    {
                        "type": "act",
                        "tool": "shell",
                        "input": {"command": f'type "{target}"'},
                    },
                    ensure_ascii=False,
                )
            ),
            RuntimeV2Action.from_model_output(
                json.dumps(
                    {
                        "type": "complete",
                        "summary": "已读取完成",
                        "verification": {"target": target, "expected": "项目记忆"},
                    },
                    ensure_ascii=False,
                )
            ),
        ]
    )

    async def fake_decide(_state):
        return next(actions)

    async def fake_execute(tool, tool_input):
        assert tool == "file"
        assert tool_input == {"operation": "read", "path": target}
        return {
            "success": True,
            "tool": "file",
            "stdout": "项目记忆",
            "stderr": "",
            "exit_code": 0,
            "metadata": {},
        }

    monkeypatch.setattr(loop, "_decide", fake_decide)
    monkeypatch.setattr(loop.tool_broker, "execute", fake_execute)
    monkeypatch.setattr(
        loop.verifier,
        "verify_complete",
        lambda verification, last_tool_result: {"passed": True, "reason": "stubbed"},
    )

    result = await loop.run_turn_typed("session:explicit-read-turn", f'看看这个文件 "{target}"')

    assert result.status == "completed_verified"
    assert result.reply_text == "已读取完成"


@pytest.mark.asyncio
async def test_runtime_v2_loop_max_steps_exhausted_returns_resumable_pause(monkeypatch):
    loop = RuntimeV2Loop()
    state = loop.get_state("session:max-steps")

    async def fake_decide(_state):
        return RuntimeV2Action.from_model_output(
            json.dumps({"type": "plan", "goal": "继续推进", "steps": ["a", "b"]}, ensure_ascii=False)
        )

    monkeypatch.setattr(loop, "_decide", fake_decide)

    result = await loop.run_turn_typed("session:max-steps", "继续这个执行任务", max_steps=2)

    assert result.status == "resumable_pause"
    assert result.finish_reason == "max_steps_exhausted"
    assert result.checkpoint_payload["state_snapshot"]["task_status"] == "resumable_pause"


@pytest.mark.asyncio
async def test_runtime_v2_loop_transient_decision_error_returns_resumable_pause(monkeypatch):
    loop = RuntimeV2Loop()

    async def fake_decide(_state):
        return RuntimeV2Action(
            type="ask",
            question="Runtime v2 模型暂时不可用，我会继续自动重试。",
            raw={
                "type": "ask",
                "kind": "transient_decision_error",
                "retryable": True,
                "error": "Server error 500",
                "error_class": "HTTPStatusError",
                "status_code": 500,
            },
        )

    monkeypatch.setattr(loop, "_decide", fake_decide)

    result = await loop.run_turn_typed("session:transient-decision-error", "继续这个执行任务", max_steps=2)

    assert result.status == "resumable_pause"
    assert result.finish_reason == "transient_decision_error"
    assert result.checkpoint_payload["state_snapshot"]["task_status"] == "resumable_pause"
