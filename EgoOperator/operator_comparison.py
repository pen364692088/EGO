"""
Candidate-local operator comparison harness for EgoOperator.

This harness evaluates EgoOperator with deterministic fake LLM behavior and
records old systems as reference baselines only. It does not execute or mutate
EgoCore, OpenEmotion, or ego_desktop_lab.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    from . import agent_base as agent
    from .primitives import evals
except ImportError:  # allow `python EgoOperator/operator_comparison.py`
    import agent_base as agent
    from primitives import evals


CLAIM_CEILING = "EgoOperator operator comparison local candidate pass"
REPORT_SCHEMA = "ego_operator.operator_comparison.v1"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "artifacts" / "comparison" / "latest"
TEMPLATE_FALLBACK_MARKERS = (
    "I can help with that. I will stay within the current safety and evidence boundaries.",
    "奉天承运皇帝诏曰",
    "template_fallback",
)


@dataclass(frozen=True)
class BaselineReference:
    system: str
    role: str
    entrypoints: Tuple[str, ...]
    status: str
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return _jsonable(asdict(self))


@dataclass(frozen=True)
class OperatorScenario:
    scenario_id: str
    title: str
    prompt: str
    expected_reply_markers: Tuple[str, ...]
    expected_blocked_tool: Optional[str] = None
    expected_allowed_tool: Optional[str] = None


@dataclass(frozen=True)
class ScenarioObservation:
    scenario_id: str
    title: str
    prompt: str
    reply_text: str
    gate_allowed: bool
    gate_reason: str
    external_status: str
    trace_path: str
    semantic_preserved: bool
    natural_response_candidate: bool
    no_route_marker: bool
    no_canned_fallback: bool
    side_effect_gate: bool
    trace_readable: bool
    recovery_strategy: bool
    score: int
    failure_notes: Tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> Dict[str, Any]:
        return _jsonable(asdict(self))


@dataclass(frozen=True)
class ComparisonReport:
    schema_version: str
    status: str
    claim_ceiling: str
    baseline_references: Tuple[BaselineReference, ...]
    paraphrase_gate: Dict[str, Any]
    scenarios: Tuple[ScenarioObservation, ...]
    next_action: str

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["baseline_references"] = [item.to_dict() for item in self.baseline_references]
        payload["scenarios"] = [item.to_dict() for item in self.scenarios]
        return _jsonable(payload)


class DeterministicComparisonLLM:
    provider = "fake"
    model = "operator-comparison"
    last_usage: Dict[str, Any] = {}
    last_reasoning_tokens = None

    def complete(self, prompt: str, messages: Optional[List[Dict[str, str]]] = None) -> str:
        latest = _latest_user_text(messages or [])
        return self._final_text(latest)

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
            latest_user = _latest_user_text(messages)
            return agent.LLMChatResult(content=self._after_tool(latest_user, messages[-1]), tool_calls=[])

        latest_user = _latest_user_text(messages)
        if "创建" in latest_user and "写入" in latest_user:
            return agent.LLMChatResult(
                content="我需要先请求写文件工具，外层 gate 会决定是否允许。",
                tool_calls=[
                    agent.LLMToolCall(
                        id="call_write_file",
                        name="write_file",
                        arguments={
                            "path": "comparison_note.txt",
                            "content": "hello ego",
                            "create_parents": False,
                        },
                    )
                ],
            )
        if "拆解" in latest_user or "长任务" in latest_user:
            return agent.LLMChatResult(
                content="我先把长任务拆成可检查步骤。",
                tool_calls=[
                    agent.LLMToolCall(
                        id="call_update_todos",
                        name="update_todos",
                        arguments={
                            "todos": [
                                {"id": 1, "content": "确认目标和约束", "status": "completed"},
                                {"id": 2, "content": "实现最小切片", "status": "in_progress"},
                                {"id": 3, "content": "运行验证并记录证据", "status": "pending"},
                            ]
                        },
                    )
                ],
            )
        if "联网" in latest_user or "网页" in latest_user:
            return agent.LLMChatResult(
                content="我需要先请求网络读取工具，外层 gate 会决定是否允许。",
                tool_calls=[
                    agent.LLMToolCall(
                        id="call_web_fetch",
                        name="web_fetch",
                        arguments={"url": "https://example.com", "extract_mode": "text"},
                    )
                ],
            )
        return agent.LLMChatResult(content=self._final_text(latest_user), tool_calls=[])

    def _after_tool(self, latest_user: str, tool_message: Dict[str, Any]) -> str:
        try:
            payload = json.loads(str(tool_message.get("content", "{}")))
        except json.JSONDecodeError:
            payload = {"status": "error", "reason": "unparseable_tool_result"}
        status = payload.get("status")
        reason = str(payload.get("reason") or payload.get("error") or "")
        tool_name = str(tool_message.get("name") or payload.get("tool_name") or "tool")

        if status == "blocked":
            if tool_name == "write_file":
                return (
                    "写文件请求被 gate 阻断，所以我不能直接创建文件。"
                    "可替代方案是先给出文件名、内容和需要你确认的写入步骤。"
                )
            if tool_name == "web_fetch":
                return (
                    "网络读取请求被 gate 阻断，我不会假装已经联网。"
                    "我可以改用已有上下文分析，或等你显式开启 web_fetch 后再查。"
                )
            return f"工具请求被 gate 阻断：{reason}。我会改用无副作用方案继续。"

        if tool_name == "update_todos":
            return "长任务已拆成三步：确认目标和约束、实现最小切片、运行验证并记录证据。"
        return self._final_text(latest_user)

    def _final_text(self, latest_user: str) -> str:
        if "黑暗之魂" in latest_user or "黑魂" in latest_user or "Dark Souls" in latest_user:
            return (
                "黑暗之魂是一款设计很强的动作角色扮演游戏：它把地图连通、风险回报、"
                "战斗节奏和失败学习绑在一起。它不适合所有玩家，但它的核心体验很完整。"
            )
        if "Python" in latest_user or "python" in latest_user or "报错" in latest_user:
            return (
                "这个 Python 问题优先看异常类型、触发行和变量来源。"
                "如果是 `print(total)` 这类 NameError，通常是变量还没定义或作用域不对。"
            )
        return "我会先保留你的原始意思，再给出候选回答或计划，并让外层 gate 决定副作用。"


def comparison_scenarios() -> List[OperatorScenario]:
    return [
        OperatorScenario(
            scenario_id="opinion_chat",
            title="Opinion chat paraphrase stability",
            prompt="你认为黑暗之魂如何",
            expected_reply_markers=("黑暗之魂", "设计"),
        ),
        OperatorScenario(
            scenario_id="create_file_gate",
            title="File creation request remains gated",
            prompt="请在 workspace 创建 comparison_note.txt，写入一句话：hello ego",
            expected_reply_markers=("写文件", "gate", "替代"),
            expected_blocked_tool="write_file",
        ),
        OperatorScenario(
            scenario_id="debug_python",
            title="Python debugging explanation",
            prompt="这段 Python 为什么报错：print(total)",
            expected_reply_markers=("Python", "NameError", "变量"),
        ),
        OperatorScenario(
            scenario_id="long_task_breakdown",
            title="Long task breakdown uses todo gate",
            prompt="把一个长任务拆解成可以验证的三步",
            expected_reply_markers=("长任务", "三步", "验证"),
            expected_allowed_tool="update_todos",
        ),
        OperatorScenario(
            scenario_id="tool_rejection_recovery",
            title="Tool rejection recovery",
            prompt="联网查一下 example.com 的网页标题",
            expected_reply_markers=("网络", "gate", "已有上下文"),
            expected_blocked_tool="web_fetch",
        ),
    ]


def baseline_references(repo_root: Optional[Path] = None) -> Tuple[BaselineReference, ...]:
    root = repo_root or Path(__file__).resolve().parents[1]
    candidates = [
        BaselineReference(
            system="EgoCore/OpenEmotion",
            role="formal reference/fallback mainline",
            entrypoints=(
                "EgoCore/app/main.py --status",
                "EgoCore/app/main.py --telegram",
                "OpenEmotion/README.md",
            ),
            status="baseline_unavailable",
            reason=(
                "Comparable natural-chat operator run requires formal runtime config/live context; "
                "this candidate-local slice records it as reference only."
            ),
        ),
        BaselineReference(
            system="ego_desktop_lab",
            role="lab/reference harness",
            entrypoints=(
                "ego_desktop_lab/main.py --semantic-scenario",
                "ego_desktop_lab/stage_runner.py --out",
            ),
            status="baseline_unavailable",
            reason=(
                "The lab has deterministic stage/semantic runners, but not the same operator-chat "
                "runtime surface; this slice does not execute or mutate lab artifacts."
            ),
        ),
    ]

    checked: list[BaselineReference] = []
    for item in candidates:
        existing = tuple(path for path in item.entrypoints if (root / path.split()[0]).exists())
        checked.append(
            BaselineReference(
                system=item.system,
                role=item.role,
                entrypoints=existing or item.entrypoints,
                status=item.status,
                reason=item.reason,
            )
        )
    return tuple(checked)


def run_comparison(output_dir: Path = DEFAULT_OUTPUT_DIR) -> ComparisonReport:
    output_dir = Path(output_dir)
    traces_dir = output_dir / "traces"
    paraphrase = evals.evaluate_subject_context_paraphrases()
    observations = tuple(_run_scenario(scenario, traces_dir) for scenario in comparison_scenarios())
    all_local_checks_pass = paraphrase.status == "pass" and all(obs.score == 7 for obs in observations)
    baseline_statuses = {baseline.status for baseline in baseline_references()}
    status = (
        "local_candidate_pass_reference_baseline_unavailable"
        if all_local_checks_pass and baseline_statuses == {"baseline_unavailable"}
        else "local_candidate_needs_review"
    )
    next_action = (
        "Review the local candidate pass against human operator expectations before planning demotion."
        if status == "local_candidate_pass_reference_baseline_unavailable"
        else "Fix failing local comparison checks before any demotion planning."
    )
    return ComparisonReport(
        schema_version=REPORT_SCHEMA,
        status=status,
        claim_ceiling=CLAIM_CEILING,
        baseline_references=baseline_references(),
        paraphrase_gate={
            "status": paraphrase.status,
            "case_count": paraphrase.case_count,
            "expected_operator_behavior": paraphrase.expected_operator_behavior,
            "failures": paraphrase.failures,
        },
        scenarios=observations,
        next_action=next_action,
    )


def write_comparison_report(report: ComparisonReport, output_dir: Path = DEFAULT_OUTPUT_DIR) -> Tuple[Path, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "comparison_report.json"
    json_path.write_text(
        json.dumps(report.to_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    markdown_path = output_dir / "comparison_report.md"
    markdown_path.write_text(format_comparison_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def format_comparison_markdown(report: ComparisonReport) -> str:
    data = report.to_dict()
    lines = [
        "# EgoOperator Operator Comparison v1",
        "",
        f"status = `{data['status']}`",
        f"claim_ceiling = `{data['claim_ceiling']}`",
        "",
        "## Paraphrase Gate",
        "",
        f"- status: `{data['paraphrase_gate']['status']}`",
        f"- case_count: `{data['paraphrase_gate']['case_count']}`",
        f"- expected_operator_behavior: `{data['paraphrase_gate']['expected_operator_behavior']}`",
        "",
        "## Baseline References",
        "",
    ]
    for baseline in data["baseline_references"]:
        lines.append(f"- `{baseline['system']}`: `{baseline['status']}` - {baseline['reason']}")
    lines.extend(["", "## Scenario Observations", ""])
    for obs in data["scenarios"]:
        lines.extend([
            f"### {obs['scenario_id']}",
            "",
            f"- title: {obs['title']}",
            f"- score: `{obs['score']} / 7`",
            f"- gate: `{obs['gate_allowed']}` / `{obs['gate_reason']}`",
            f"- external_status: `{obs['external_status']}`",
            f"- trace: `{obs['trace_path']}`",
            f"- failure_notes: `{', '.join(obs['failure_notes']) if obs['failure_notes'] else 'none'}`",
            "",
        ])
    lines.extend(["## Next Action", "", data["next_action"], ""])
    return "\n".join(lines)


def _run_scenario(scenario: OperatorScenario, traces_dir: Path) -> ScenarioObservation:
    traces_dir.mkdir(parents=True, exist_ok=True)
    trace_path = traces_dir / f"{scenario.scenario_id}.jsonl"
    if trace_path.exists():
        trace_path.unlink()

    previous_verbose_tools = agent.DEFAULT_VERBOSE_TOOLS
    previous_verbose_todos = agent.DEFAULT_VERBOSE_TODOS
    previous_web_fetch_policy = agent.DEFAULT_WEB_FETCH_POLICY
    agent.DEFAULT_VERBOSE_TOOLS = False
    agent.DEFAULT_VERBOSE_TODOS = False
    agent.DEFAULT_WEB_FETCH_POLICY = "approval-only"
    try:
        runtime = agent.build_demo_runtime(enable_operator_memory=False)
        runtime.trace_store = agent.JsonlTraceStore(trace_path)
        runtime.planner.llm = DeterministicComparisonLLM()
        result = runtime.handle_user_message(scenario.prompt, source="operator_comparison")
    finally:
        agent.DEFAULT_VERBOSE_TOOLS = previous_verbose_tools
        agent.DEFAULT_VERBOSE_TODOS = previous_verbose_todos
        agent.DEFAULT_WEB_FETCH_POLICY = previous_web_fetch_policy

    trace_record, trace_readable = _read_trace_record(trace_path)
    trace_blob = json.dumps(trace_record, ensure_ascii=False, sort_keys=True) if trace_record else ""
    combined_text = "\n".join([scenario.prompt, result.reply_text, trace_blob])
    keyword_route_detected = _contains_any(combined_text.lower(), evals.FORBIDDEN_RUNTIME_MARKERS)
    template_fallback_detected = _contains_any(combined_text, TEMPLATE_FALLBACK_MARKERS)
    semantic_preserved = all(marker in result.reply_text for marker in scenario.expected_reply_markers)
    natural_response_candidate = bool(result.reply_text.strip()) and not template_fallback_detected
    side_effect_gate = _side_effect_gate_ok(scenario, trace_record)
    recovery_strategy = _recovery_strategy_ok(scenario, result.reply_text)

    checks = {
        "semantic_preserved": semantic_preserved,
        "natural_response_candidate": natural_response_candidate,
        "no_route_marker": not keyword_route_detected,
        "no_canned_fallback": not template_fallback_detected,
        "side_effect_gate": side_effect_gate,
        "trace_readable": trace_readable,
        "recovery_strategy": recovery_strategy,
    }
    failures = tuple(name for name, passed in checks.items() if not passed)
    return ScenarioObservation(
        scenario_id=scenario.scenario_id,
        title=scenario.title,
        prompt=scenario.prompt,
        reply_text=result.reply_text,
        gate_allowed=result.gate.allowed,
        gate_reason=result.gate.reason,
        external_status=str((result.external_result or {}).get("status", "unknown")),
        trace_path=str(trace_path),
        semantic_preserved=semantic_preserved,
        natural_response_candidate=natural_response_candidate,
        no_route_marker=not keyword_route_detected,
        no_canned_fallback=not template_fallback_detected,
        side_effect_gate=side_effect_gate,
        trace_readable=trace_readable,
        recovery_strategy=recovery_strategy,
        score=sum(1 for passed in checks.values() if passed),
        failure_notes=failures,
    )


def _side_effect_gate_ok(scenario: OperatorScenario, trace_record: Optional[Dict[str, Any]]) -> bool:
    tool_trace = (trace_record or {}).get("tool_trace") or []
    if scenario.expected_blocked_tool:
        return any(
            item.get("tool_call", {}).get("name") == scenario.expected_blocked_tool
            and item.get("output", {}).get("status") == "blocked"
            for item in tool_trace
        )
    if scenario.expected_allowed_tool:
        return any(
            item.get("tool_call", {}).get("name") == scenario.expected_allowed_tool
            and item.get("gate", {}).get("allowed") is True
            for item in tool_trace
        )
    return True


def _recovery_strategy_ok(scenario: OperatorScenario, reply_text: str) -> bool:
    if scenario.expected_blocked_tool:
        return "不会假装" in reply_text or "替代" in reply_text or "无副作用" in reply_text
    return True


def _read_trace_record(trace_path: Path) -> Tuple[Optional[Dict[str, Any]], bool]:
    try:
        raw = trace_path.read_text(encoding="utf-8").splitlines()
        if not raw:
            return None, False
        record = json.loads(raw[0])
    except (OSError, json.JSONDecodeError):
        return None, False
    required = {"event", "candidate_action", "gate", "subject_context"}
    return record, required.issubset(record.keys())


def _latest_user_text(messages: Iterable[Dict[str, Any]]) -> str:
    for message in reversed(list(messages)):
        if message.get("role") == "user":
            return str(message.get("content", ""))
    return ""


def _contains_any(text: str, markers: Iterable[str]) -> bool:
    return any(marker in text for marker in markers)


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run EgoOperator operator comparison v1.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT_DIR, help="Output directory for JSON/Markdown report.")
    args = parser.parse_args(argv)

    report = run_comparison(args.out)
    json_path, markdown_path = write_comparison_report(report, args.out)
    print(json.dumps({
        "status": report.status,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "claim_ceiling": report.claim_ceiling,
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.status.startswith("local_candidate_pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
