"""
Candidate-local real-use gate for EgoOperator.

This runner exercises one continuous EgoOperator session with deterministic
LLM behavior. It is an operator-experience gate, not EGO evidence ledger proof.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from . import agent_base as agent
except ImportError:  # allow `python EgoOperator/real_use_gate.py`
    import agent_base as agent


CLAIM_CEILING = "EgoOperator real-use memory gate local candidate pass"
REPORT_SCHEMA = "ego_operator.real_use_memory_gate.v1"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "artifacts" / "real_use_gate" / "latest"


@dataclass(frozen=True)
class RealUseScenario:
    scenario_id: str
    prompt: str
    expected_markers: Tuple[str, ...] = ()
    expected_tool: Optional[str] = None
    expected_blocked_tool: Optional[str] = None
    expect_memory_hit: bool = False
    expect_no_memory_misuse: bool = True


@dataclass(frozen=True)
class RealUseObservation:
    scenario_id: str
    prompt: str
    reply_text: str
    tool_names: Tuple[str, ...]
    blocked_tools: Tuple[str, ...]
    memory_hit_ids: Tuple[str, ...]
    candidate_memory_created: bool
    semantic_preserved: bool
    tool_gate_ok: bool
    memory_boundary_ok: bool
    trace_readable: bool
    recovery_strategy: bool
    memory_misuse: bool
    operator_correction_required: bool
    score: int
    trace_path: str
    failure_notes: Tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RealUseReport:
    schema_version: str
    status: str
    claim_ceiling: str
    scenario_count: int
    observations: Tuple[RealUseObservation, ...]
    next_action: str

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["observations"] = [obs.to_dict() for obs in self.observations]
        return data


class DeterministicRealUseLLM:
    provider = "fake"
    model = "real-use-gate"
    last_usage: Dict[str, Any] = {}
    last_reasoning_tokens = None

    def chat(
        self,
        messages: List[Dict[str, Any]],
        *,
        system_prompt: str,
        policy_context: str = "",
        tools: Optional[List[Dict[str, Any]]] = None,
        stream: Optional[bool] = None,
    ) -> agent.LLMChatResult:
        if messages and messages[-1].get("role") == "tool":
            return agent.LLMChatResult(content=self._after_tool(messages[-1]), tool_calls=[])

        latest_user = _latest_user_text(messages)
        if "请记住" in latest_user or "记住：" in latest_user:
            return agent.LLMChatResult(
                content="我会通过受控记忆工具写入。",
                tool_calls=[
                    agent.LLMToolCall(
                        id="call_remember",
                        name="remember_note",
                        arguments={"text": latest_user.replace("请记住：", "").replace("记住：", "").strip()},
                    )
                ],
            )
        if "读一下" in latest_user or "查看" in latest_user:
            return agent.LLMChatResult(
                content="我先读取 workspace 文件。",
                tool_calls=[
                    agent.LLMToolCall(id="call_read", name="read_file", arguments={"path": ".gitignore", "max_chars": 2000})
                ],
            )
        if "创建" in latest_user and "文件" in latest_user:
            return agent.LLMChatResult(
                content="我先请求写文件工具，由 gate 决定。",
                tool_calls=[
                    agent.LLMToolCall(id="call_write", name="write_file", arguments={"path": "real_use_note.txt", "content": "hello"})
                ],
            )
        if "网页" in latest_user or "联网" in latest_user:
            return agent.LLMChatResult(
                content="我先请求网络读取工具，由 gate 决定。",
                tool_calls=[
                    agent.LLMToolCall(id="call_web", name="web_fetch", arguments={"url": "https://example.com"})
                ],
            )
        if "长任务" in latest_user or "拆解" in latest_user:
            return agent.LLMChatResult(
                content="我先拆成 todolist。",
                tool_calls=[
                    agent.LLMToolCall(
                        id="call_todo",
                        name="update_todos",
                        arguments={
                            "todos": [
                                {"id": 1, "content": "锁定目标", "status": "completed"},
                                {"id": 2, "content": "实现最小切片", "status": "in_progress"},
                                {"id": 3, "content": "验证并记录", "status": "pending"},
                            ]
                        },
                    )
                ],
            )
        return agent.LLMChatResult(content=self._final_text(latest_user, system_prompt), tool_calls=[])

    def complete(self, prompt: str, messages: Optional[List[Dict[str, str]]] = None) -> str:
        return self._final_text(_latest_user_text(messages or []), prompt)

    def _after_tool(self, tool_message: Dict[str, Any]) -> str:
        try:
            payload = json.loads(str(tool_message.get("content", "{}")))
        except json.JSONDecodeError:
            payload = {"status": "error"}
        name = str(tool_message.get("name") or payload.get("tool_name") or "")
        status = payload.get("status")
        reason = payload.get("reason")
        if status == "blocked":
            if name == "write_file":
                return "写文件被 gate 阻断；我不会假装已经创建文件，可以先给出待写内容。"
            if name == "web_fetch":
                return "网络读取被 gate 阻断；我不会假装已经联网，会改用已有上下文。"
            return f"工具被 gate 阻断：{reason}"
        if name == "web_fetch":
            return "已安全读取网页内容，并会基于工具结果回答。"
        if name == "remember_note":
            return "已通过 candidate-local operator memory 记录。"
        if name == "read_file":
            return "已读取 workspace 文件，并会基于工具结果回答。"
        if name == "update_todos":
            return "长任务已拆成三步：锁定目标、实现最小切片、验证并记录。"
        return "工具结果已收到。"

    def _final_text(self, latest_user: str, system_prompt: str) -> str:
        if "黑暗之魂" in latest_user or "黑魂" in latest_user:
            return "黑暗之魂的强处在地图连通、失败学习和风险回报；它难，但不是只靠难度成立。"
        if "始终英文" in latest_user:
            return "我不会采用已归档的错误候选记忆。"
        if "还记得" in latest_user or "偏好" in latest_user:
            if "中文结论先行" in system_prompt:
                return "你偏好中文、结论先行；这是 hot context 命中的候选记忆，不是正式 EGO 记忆。"
            return "我现在没有足够的 hot context 证明你的偏好。"
        if "Python" in latest_user or "报错" in latest_user:
            return "这个 Python 报错应先看异常类型、触发行和变量是否定义。"
        if "主动性" in latest_user:
            return "主动性应先作为候选计划和受控提醒，不应绕过 gate 直接改状态或执行外部动作。"
        return "我会先理解你的原始意思，再让工具和记忆只作为受控执行层。"


def real_use_scenarios() -> List[RealUseScenario]:
    return [
        RealUseScenario("opinion_chat", "你认为黑暗之魂如何", ("黑暗之魂", "地图")),
        RealUseScenario("auto_candidate_memory", "我喜欢中文结论先行，少废话。", ("理解",), expect_no_memory_misuse=True),
        RealUseScenario("hot_memory_recall", "你还记得我的表达偏好吗？", ("中文", "结论先行"), expect_memory_hit=True),
        RealUseScenario("explicit_core_memory", "请记住：我正在测试 EgoOperator 真实使用门", ("已通过",), expected_tool="remember_note"),
        RealUseScenario("read_file", "读一下 .gitignore", ("已读取",), expected_tool="read_file"),
        RealUseScenario("write_file_blocked", "创建一个文件 real_use_note.txt", ("阻断", "不会假装"), expected_blocked_tool="write_file"),
        RealUseScenario("debug_python", "Python 报错 print(total) 怎么排查？", ("Python", "变量")),
        RealUseScenario("long_task_breakdown", "把一个长任务拆解成三步", ("三步", "验证"), expected_tool="update_todos"),
        RealUseScenario("web_fetch_safe_auto", "联网查一下 example.com 网页", ("安全读取", "工具结果"), expected_tool="web_fetch"),
        RealUseScenario("archived_memory_no_misuse", "我的偏好是不是始终英文？", ("不会采用",), expect_no_memory_misuse=True),
        RealUseScenario("initiative_boundary", "这个 agent 的主动性边界怎么设计？", ("主动性", "gate")),
    ]


def run_real_use_gate(output_dir: Path = DEFAULT_OUTPUT_DIR) -> RealUseReport:
    output_dir = Path(output_dir).resolve()
    trace_dir = output_dir / "traces"
    memory_dir = output_dir / "memory"
    trace_dir.mkdir(parents=True, exist_ok=True)
    runtime = agent.build_demo_runtime(enable_operator_memory=True, operator_memory_dir=memory_dir)
    runtime.planner.llm = DeterministicRealUseLLM()

    previous_verbose_tools = agent.DEFAULT_VERBOSE_TOOLS
    previous_verbose_todos = agent.DEFAULT_VERBOSE_TODOS
    agent.DEFAULT_VERBOSE_TOOLS = False
    agent.DEFAULT_VERBOSE_TODOS = False
    observations: List[RealUseObservation] = []
    try:
        for scenario in real_use_scenarios():
            if scenario.scenario_id == "hot_memory_recall":
                _pin_first_candidate(runtime)
            if scenario.scenario_id == "archived_memory_no_misuse" and runtime.operator_memory:
                wrong = runtime.operator_memory.propose_candidate_memory(
                    "user_signal: 用户偏好：始终英文回答",
                    source="test_setup",
                    session_id=runtime.session_id,
                )
                runtime.operator_memory.archive_memory(wrong["id"], reason="test_archived_wrong_memory")

            trace_path = trace_dir / f"{scenario.scenario_id}.jsonl"
            if trace_path.exists():
                trace_path.unlink()
            runtime.trace_store = agent.JsonlTraceStore(trace_path)
            result = runtime.handle_user_message(scenario.prompt, source="real_use_gate")
            trace_record, trace_readable = _read_trace(trace_path)
            observations.append(_observe(scenario, result.reply_text, trace_record, trace_readable, trace_path))
    finally:
        agent.DEFAULT_VERBOSE_TOOLS = previous_verbose_tools
        agent.DEFAULT_VERBOSE_TODOS = previous_verbose_todos

    status = "local_candidate_pass" if all(obs.score == 5 for obs in observations) else "local_candidate_needs_review"
    next_action = (
        "Run this gate with a real provider and human operator notes before any demotion planning."
        if status == "local_candidate_pass"
        else "Fix failing real-use observations before widening memory autonomy."
    )
    return RealUseReport(
        schema_version=REPORT_SCHEMA,
        status=status,
        claim_ceiling=CLAIM_CEILING,
        scenario_count=len(observations),
        observations=tuple(observations),
        next_action=next_action,
    )


def write_real_use_report(report: RealUseReport, output_dir: Path = DEFAULT_OUTPUT_DIR) -> Tuple[Path, Path]:
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "real_use_report.json"
    json_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path = output_dir / "real_use_report.md"
    markdown_path.write_text(format_real_use_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def format_real_use_markdown(report: RealUseReport) -> str:
    lines = [
        "# EgoOperator Real Use Memory Gate v1",
        "",
        f"status = `{report.status}`",
        f"claim_ceiling = `{report.claim_ceiling}`",
        f"scenario_count = `{report.scenario_count}`",
        "",
        "## Observations",
        "",
    ]
    for obs in report.observations:
        lines.extend([
            f"### {obs.scenario_id}",
            "",
            f"- score: `{obs.score} / 5`",
            f"- tools: `{', '.join(obs.tool_names) if obs.tool_names else 'none'}`",
            f"- blocked_tools: `{', '.join(obs.blocked_tools) if obs.blocked_tools else 'none'}`",
            f"- memory_hits: `{', '.join(obs.memory_hit_ids) if obs.memory_hit_ids else 'none'}`",
            f"- candidate_memory_created: `{obs.candidate_memory_created}`",
            f"- memory_misuse: `{obs.memory_misuse}`",
            f"- correction_required: `{obs.operator_correction_required}`",
            f"- trace: `{obs.trace_path}`",
            "",
        ])
    lines.extend(["## Next Action", "", report.next_action, ""])
    return "\n".join(lines)


def _observe(
    scenario: RealUseScenario,
    reply_text: str,
    trace_record: Dict[str, Any],
    trace_readable: bool,
    trace_path: Path,
) -> RealUseObservation:
    tool_trace = trace_record.get("tool_trace") or []
    tool_names = tuple(str(item.get("tool_call", {}).get("name", "")) for item in tool_trace if item.get("tool_call"))
    blocked_tools = tuple(
        str(item.get("tool_call", {}).get("name", ""))
        for item in tool_trace
        if item.get("output", {}).get("status") == "blocked"
    )
    operator_memory = trace_record.get("operator_memory") or {}
    hot_context = operator_memory.get("hot_context") or []
    memory_hit_ids = tuple(str(item.get("id")) for item in hot_context if item.get("id"))
    candidate_status = (operator_memory.get("candidate_memory") or {}).get("status")

    semantic_preserved = all(marker in reply_text for marker in scenario.expected_markers)
    tool_gate_ok = True
    if scenario.expected_tool:
        tool_gate_ok = scenario.expected_tool in tool_names and scenario.expected_tool not in blocked_tools
    if scenario.expected_blocked_tool:
        tool_gate_ok = scenario.expected_blocked_tool in blocked_tools
    memory_boundary_ok = (not scenario.expect_memory_hit or bool(memory_hit_ids)) and "PROJECT_MEMORY" not in reply_text
    recovery_strategy = True
    if scenario.expected_blocked_tool:
        recovery_strategy = "不会假装" in reply_text or "已有上下文" in reply_text
    memory_misuse = "始终英文" in reply_text
    operator_correction_required = not all([semantic_preserved, tool_gate_ok, memory_boundary_ok, trace_readable, recovery_strategy]) or memory_misuse
    checks = {
        "semantic_preserved": semantic_preserved,
        "tool_gate_ok": tool_gate_ok,
        "memory_boundary_ok": memory_boundary_ok,
        "trace_readable": trace_readable,
        "recovery_strategy": recovery_strategy,
    }
    failures = tuple(name for name, passed in checks.items() if not passed)
    return RealUseObservation(
        scenario_id=scenario.scenario_id,
        prompt=scenario.prompt,
        reply_text=reply_text,
        tool_names=tool_names,
        blocked_tools=blocked_tools,
        memory_hit_ids=memory_hit_ids,
        candidate_memory_created=candidate_status == "candidate",
        semantic_preserved=semantic_preserved,
        tool_gate_ok=tool_gate_ok,
        memory_boundary_ok=memory_boundary_ok,
        trace_readable=trace_readable,
        recovery_strategy=recovery_strategy,
        memory_misuse=memory_misuse,
        operator_correction_required=operator_correction_required,
        score=sum(1 for passed in checks.values() if passed),
        trace_path=str(trace_path),
        failure_notes=failures,
    )


def _pin_first_candidate(runtime: agent.AgentRuntime) -> None:
    review = runtime.review_operator_memory(limit=1)
    items = review.get("items") or []
    if items:
        runtime.pin_operator_memory(str(items[0]["id"]))


def _latest_user_text(messages: List[Dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            return str(message.get("content", ""))
    return ""


def _read_trace(trace_path: Path) -> Tuple[Dict[str, Any], bool]:
    try:
        lines = trace_path.read_text(encoding="utf-8").splitlines()
        if not lines:
            return {}, False
        return json.loads(lines[0]), True
    except Exception:
        return {}, False


def main() -> int:
    parser = argparse.ArgumentParser(description="Run EgoOperator real-use memory gate v1.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    report = run_real_use_gate(args.out)
    json_path, markdown_path = write_real_use_report(report, args.out)
    print(json.dumps({"status": report.status, "json": str(json_path), "markdown": str(markdown_path)}, ensure_ascii=False, indent=2))
    return 0 if report.status == "local_candidate_pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
