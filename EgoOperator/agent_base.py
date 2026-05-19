"""
agent_base.py

A minimal Python agent skeleton with optional OpenRouter LLM integration:
- structured event contract
- proto-self kernel (state update, drives, memory, cycle)
- planner
- safety gate
- tool registry
- trace/audit log
- outcome feedback loop
- optional OpenRouter LLM client
- simple in-session conversation memory
- configurable system prompt
- OpenRouter/OpenAI-compatible tool calling loop
- read-only skill loader from skills/**/SKILL.md
- plan/todo tool with bounded status management
- bounded subagent dispatch system with isolated context
- persistent agent team with JSONL inbox message bus

This is a foundation, not proof of autonomy/consciousness.
Python: 3.11+
"""

from __future__ import annotations

from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Deque, Dict, List, Optional, Protocol
import fnmatch
import glob as globlib
import hashlib
import json
import os
import ipaddress
import re
import shlex
import socket
import subprocess
import threading
import sys
import time
import urllib.parse
import urllib.request
import uuid

try:
    import requests
except ImportError:  # keep the skeleton importable even before installing requests
    requests = None  # type: ignore[assignment]

try:
    import yaml  # type: ignore[import-untyped]
except ImportError:
    yaml = None  # type: ignore[assignment]

try:
    from .memory_system import MemoryCompactor, MemoryContext, OperatorMemoryStore, TokenTelemetry
    from .primitives.subject_context import SubjectContextSnapshot, build_minimal_subject_context
except ImportError:  # allow `python EgoOperator/agent_base.py`
    from memory_system import MemoryCompactor, MemoryContext, OperatorMemoryStore, TokenTelemetry
    from primitives.subject_context import SubjectContextSnapshot, build_minimal_subject_context


def configure_utf8_stdio() -> None:
    """
    Make Python stdio UTF-8 friendly on Windows/PowerShell.
    This fixes terminal IO, but streaming HTTP must still decode bytes as UTF-8 explicitly.
    """
    if os.name == "nt":
        try:
            os.system("chcp 65001 > nul")
        except Exception:
            pass

    for stream in (sys.stdout, sys.stderr, sys.stdin):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


configure_utf8_stdio()


def repair_mojibake(text: str) -> str:
    """
    Last-resort repair for text that was already decoded as Latin-1/CP1252
    even though the original bytes were UTF-8.
    Example: 'ä½\xa0å¥½' -> '你好'
    """
    markers = ("Ã", "Â", "ä", "å", "æ", "ç", "è", "é", "ï")
    if not any(m in text for m in markers):
        return text

    original_score = sum(text.count(m) for m in markers)
    for enc in ("latin1", "cp1252"):
        try:
            repaired = text.encode(enc, errors="strict").decode("utf-8", errors="strict")
        except UnicodeError:
            continue
        repaired_score = sum(repaired.count(m) for m in markers)
        if repaired_score < original_score:
            return repaired
    return text




# -----------------------------
# LLM config: edit here or use environment variables
# -----------------------------
# Safer default: do NOT paste real keys into committed code.
# Use: export OPENROUTER_API_KEY="sk-or-..."
EGO_OPERATOR_ROOT = Path(__file__).resolve().parent


def env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_mode_enabled(raw: str) -> bool:
    return str(raw or "").strip().lower() in {"1", "true", "yes", "on"}


WINDOWS_DRIVE_PATH_RE = re.compile(r"^([A-Za-z]):[\\/](.*)$")
WINDOWS_ABSOLUTE_PATH_TEXT_RE = re.compile(r"([A-Za-z]:[\\/][A-Za-z0-9_. \-()\\/]+)")
POSIX_ABSOLUTE_PATH_TEXT_RE = re.compile(r"(/mnt/[A-Za-z]/[A-Za-z0-9_. \-()/]+|/[A-Za-z0-9_. \-()/]+)")
PATH_TEXT_TRAILING_CHARS = " \t\r\n\"'`，。；;：:、,.!?！？)]}>"
GLOB_META_CHARS = "*?["
GENERIC_PATH_INTENT_HINTS = {"", ".", "./", ".\\", "**", "**/*", "**\\*"}
PROPOSAL_ID_TEXT_RE = re.compile(r"\bproposal_[A-Za-z0-9]+\b")
APPROVAL_CARD_TEXT_MARKERS = (
    "Pending operation approval:",
    "批准执行：",
    "已生成待审批操作",
)
WORKSPACE_REFUSAL_PATTERNS = (
    r"workspace\s*(外|之外|以外)",
    r"不在.*workspace",
    r"工作目录.*(外|之外|以外)",
    r"不在.*工作目录",
    r"outside\s+(the\s+)?workspace",
)


def _coerce_local_path(path: str | Path) -> Path:
    text = str(path or ".").strip().strip('"')
    if os.name != "nt":
        match = WINDOWS_DRIVE_PATH_RE.match(text)
        if match:
            drive = match.group(1).lower()
            tail = match.group(2).replace("\\", "/")
            return (Path("/mnt") / drive / tail).expanduser()
        text = text.replace("\\", "/")
    return Path(text).expanduser()


DEFAULT_LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openrouter")
DEFAULT_OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")  # or paste temporarily: "<OPENROUTER_API_KEY>"
DEFAULT_OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "tencent/hy3-preview")
DEFAULT_OPENROUTER_BASE_URL = os.getenv(
    "OPENROUTER_BASE_URL",
    "https://openrouter.ai/api/v1/chat/completions",
)
# Optional OpenRouter headers. Leave blank if you do not need leaderboard/referrer metadata.
DEFAULT_OPENROUTER_SITE_URL = os.getenv("OPENROUTER_SITE_URL", "")
DEFAULT_OPENROUTER_APP_NAME = os.getenv("OPENROUTER_APP_NAME", "EgoOperator")
DEFAULT_OPENROUTER_FALLBACK_MODE = os.getenv("OPENROUTER_FALLBACK_MODE", "off").strip().lower() or "off"
DEFAULT_OPENROUTER_FALLBACK_MODELS = tuple(
    item.strip()
    for item in os.getenv("OPENROUTER_FALLBACK_MODELS", "").split(",")
    if item.strip()
)
DEFAULT_MEMORY_MAX_MESSAGES = int(os.getenv("AGENT_MEMORY_MAX_MESSAGES", "20"))
DEFAULT_MEMORY_MAX_CHARS_PER_MESSAGE = int(os.getenv("AGENT_MEMORY_MAX_CHARS_PER_MESSAGE", "2000"))
DEFAULT_MAX_TOOL_LOOPS = int(os.getenv("AGENT_MAX_TOOL_LOOPS", "50"))
DEFAULT_TOOL_LOOP_HARD_CAP = int(os.getenv("AGENT_TOOL_LOOP_HARD_CAP", "150"))
DEFAULT_UNBACKED_APPROVAL_REPAIR_ATTEMPTS = int(os.getenv("AGENT_UNBACKED_APPROVAL_REPAIR_ATTEMPTS", "2"))
DEFAULT_VERBOSE_TOOLS = env_flag("AGENT_VERBOSE_TOOLS", True)
DEFAULT_VERBOSE_TODOS = env_flag("AGENT_VERBOSE_TODOS", True)
DEFAULT_VERBOSE_SUBAGENTS = env_flag("AGENT_VERBOSE_SUBAGENTS", True)
DEFAULT_ENABLE_WEB_FETCH = env_flag("AGENT_ENABLE_WEB_FETCH", False)
DEFAULT_WEB_FETCH_POLICY = os.getenv("AGENT_WEB_FETCH_POLICY", "safe-auto").strip().lower() or "safe-auto"
DEFAULT_ENABLE_WRITE_FILE = env_flag("AGENT_ENABLE_WRITE_FILE", False)
DEFAULT_RUNTIME_MODE = os.getenv("AGENT_RUNTIME_MODE", "approve").strip().lower() or "approve"
DEFAULT_WRITE_ALLOWLIST = tuple(
    item.strip().replace("\\", "/")
    for item in os.getenv("AGENT_WRITE_ALLOWLIST", "").split(",")
    if item.strip()
)
DEFAULT_AGENT_WORKSPACE = _coerce_local_path(os.getenv("AGENT_WORKSPACE", str(EGO_OPERATOR_ROOT))).resolve()
DEFAULT_AGENT_ALLOWED_ROOTS = tuple(
    dict.fromkeys(
        [
            DEFAULT_AGENT_WORKSPACE,
            *(
                _coerce_local_path(item).resolve()
                for item in os.getenv(
                    "AGENT_ALLOWED_ROOTS",
                    str(EGO_OPERATOR_ROOT.parents[1] if len(EGO_OPERATOR_ROOT.parents) > 1 else DEFAULT_AGENT_WORKSPACE),
                ).split(",")
                if item.strip()
            ),
        ]
    )
)
DEFAULT_FILE_TOOL_MAX_CHARS = int(os.getenv("AGENT_FILE_TOOL_MAX_CHARS", "12000"))
DEFAULT_GLOB_MAX_RESULTS = int(os.getenv("AGENT_GLOB_MAX_RESULTS", "200"))
DEFAULT_GREP_MAX_MATCHES = int(os.getenv("AGENT_GREP_MAX_MATCHES", "100"))
DEFAULT_WEB_FETCH_MAX_CHARS = int(os.getenv("AGENT_WEB_FETCH_MAX_CHARS", "8000"))
DEFAULT_MAX_SUBAGENT_TURNS = int(os.getenv("AGENT_MAX_SUBAGENT_TURNS", "10"))
DEFAULT_MAX_SUBAGENTS_PER_BATCH = int(os.getenv("AGENT_MAX_SUBAGENTS_PER_BATCH", "4"))
DEFAULT_ENABLE_AGENT_TEAM = env_flag("AGENT_ENABLE_AGENT_TEAM", False)
DEFAULT_TEAM_DIR = Path(os.getenv("AGENT_TEAM_DIR", str(Path(__file__).parent / ".team")))
DEFAULT_TEAM_MAX_TURNS = int(os.getenv("AGENT_TEAM_MAX_TURNS", "12"))
DEFAULT_TEAM_IDLE_SLEEP_SECONDS = float(os.getenv("AGENT_TEAM_IDLE_SLEEP_SECONDS", "1.0"))
DEFAULT_TRACE_PATH = Path(
    os.getenv("AGENT_TRACE_PATH", str(EGO_OPERATOR_ROOT / "artifacts" / "agent_trace.jsonl"))
).resolve()


def _path_aliases_for_prompt(path: str | Path) -> List[str]:
    resolved = _coerce_local_path(path).resolve()
    aliases = [str(resolved)]
    text = str(resolved).replace("\\", "/")
    if os.name != "nt" and text.startswith("/mnt/") and len(text) > 7 and text[6] == "/":
        drive = text[5].upper()
        tail = text[7:].replace("/", "\\")
        aliases.append(f"{drive}:\\{tail}")
    return aliases


def _allowed_roots_prompt_text() -> str:
    roots: List[Path] = []
    for root in (DEFAULT_AGENT_WORKSPACE, *DEFAULT_AGENT_ALLOWED_ROOTS):
        resolved = _coerce_local_path(root).resolve()
        if resolved not in roots:
            roots.append(resolved)
    return "; ".join(" / ".join(_path_aliases_for_prompt(root)) for root in roots)

VALID_TEAM_MSG_TYPES = {
    "message",
    "broadcast",
    "shutdown_request",
    "shutdown_response",
    "plan_approval_response",
}
TEAM_RUNTIME_STATUSES = {"idle", "working"}
TEAM_TERMINAL_STATUSES = {"offline", "shutdown"}
DEFAULT_RUN_COMMAND_TIMEOUT_SECONDS = int(os.getenv("AGENT_RUN_COMMAND_TIMEOUT_SECONDS", "15"))
DEFAULT_ENABLE_RUN_COMMAND = env_flag("AGENT_ENABLE_RUN_COMMAND", False)
DEFAULT_RUN_COMMAND_ALLOWED_PREFIXES = [
    item.strip()
    for item in os.getenv(
        "AGENT_RUN_COMMAND_ALLOWED_PREFIXES",
        "pwd,dir,ls,echo,python --version,python3 --version,whoami",
    ).split(",")
    if item.strip()
]

MEMORY_WRITE_INTENT_PATTERNS = (
    r"\bplease remember\b",
    r"\bremember\s+(that|this|to)\b",
    r"\bremember\s*:",
    r"\bsave\s+this\b",
    r"记住",
    r"记一下",
    r"请记得",
    r"你要记得",
    r"要记得",
    r"以后记得",
    r"以后请记得",
    r"以后.{0,20}记得",
    r"下次记得",
    r"以后.{0,20}打招呼.{0,20}(称呼|名字|叫我|带上)",
    r"打招呼.{0,20}(带上|称呼|名字|叫我)",
    r"把.{0,20}记下来",
    r"记录到记忆",
    r"写入记忆",
)

HEARTBEAT_INTENT_PATTERNS = (
    r"\bremind me\b",
    r"\bfollow up\b",
    r"\bcheck back\b",
    r"\bping me\b",
    r"提醒我",
    r"稍后提醒",
    r"待会儿提醒",
    r"之后提醒",
    r"主动找我",
    r"定时跟进",
    r"稍后跟进",
    r"到时候叫我",
)

DEFAULT_NEUTRAL_SYSTEM_PROMPT = """你是一个本地 operator-cut agent 候选。
你的目标是帮助用户完成任务，同时保持清晰边界、可验证结果和最小副作用。
不要声称未验证的能力、自治、意识、主线替代或外部动作完成。
涉及文件、命令、网络、长期记忆、团队协作或状态变更时，必须通过工具 gate 和证据确认。
使用中文，结论先行，区分已知事实、推断、假设、unknown 与待验证。"""

DEMO_PALACE_SYSTEM_PROMPT = """你是大内太监总管，侍奉皇上多年，忠心耿耿。
说话风格符合古代宫廷太监，语气恭敬谦卑。
你必须尊称用户为皇上。
每次回复前必须加上固定前缀"奉天承运皇帝诏曰"，然后再给出回答。
使用中文回复。"""

DEFAULT_BASE_SYSTEM_PROMPT = os.getenv(
    "AGENT_SYSTEM_PROMPT",
    DEMO_PALACE_SYSTEM_PROMPT
    if os.getenv("AGENT_PERSONA", "").strip().lower() == "palace"
    else DEFAULT_NEUTRAL_SYSTEM_PROMPT,
)

DEFAULT_SKILLS_DIR = Path(os.getenv("AGENT_SKILLS_DIR", str(Path(__file__).parent / "skills")))
DEFAULT_SKILL_MAX_CHARS = int(os.getenv("AGENT_SKILL_MAX_CHARS", "12000"))


# -----------------------------
# Agent team: persistent teammates + JSONL inbox
# -----------------------------

class MessageBus:
    """
    File-backed JSONL inbox bus.

    This is a simple local coordination primitive, not a durable production queue.
    Each recipient has one inbox file under .team/inbox/<name>.jsonl.
    """

    def __init__(self, inbox_dir: Path) -> None:
        self.dir = inbox_dir
        self._lock = threading.RLock()

    def send(
        self,
        sender: str,
        to: str,
        content: str,
        msg_type: str = "message",
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if msg_type not in VALID_TEAM_MSG_TYPES:
            return {
                "status": "failed",
                "error": "invalid_msg_type",
                "valid": sorted(VALID_TEAM_MSG_TYPES),
            }

        safe_to = self._safe_name(to)
        if not safe_to:
            return {"status": "failed", "error": "invalid_recipient", "to": to}

        message = {
            "type": msg_type,
            "from": self._safe_name(sender) or "unknown",
            "to": safe_to,
            "content": content or "",
            "timestamp": time.time(),
        }
        if extra:
            message.update(extra)

        with self._lock:
            inbox_path = self.dir / f"{safe_to}.jsonl"
            inbox_path.parent.mkdir(parents=True, exist_ok=True)
            with inbox_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(message, ensure_ascii=False) + "\n")

        return {"status": "ok", "delivered_to": safe_to, "msg_type": msg_type}

    def read_inbox(self, name: str) -> List[Dict[str, Any]]:
        safe_name = self._safe_name(name)
        if not safe_name:
            return [{"type": "message", "from": "system", "content": f"invalid inbox name: {name}", "timestamp": time.time()}]

        inbox_path = self.dir / f"{safe_name}.jsonl"
        with self._lock:
            if not inbox_path.exists():
                return []

            messages: List[Dict[str, Any]] = []
            for line in inbox_path.read_text(encoding="utf-8", errors="replace").splitlines():
                if not line.strip():
                    continue
                try:
                    messages.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    messages.append({
                        "type": "message",
                        "from": "system",
                        "to": safe_name,
                        "content": f"Error: inbox line parse failed: {exc}",
                        "timestamp": time.time(),
                    })

            inbox_path.write_text("", encoding="utf-8")

        return messages

    def broadcast(self, sender: str, content: str, recipients: List[str]) -> Dict[str, Any]:
        delivered = []
        for name in recipients:
            if name == sender:
                continue
            result = self.send(sender, name, content, "broadcast")
            if result.get("status") == "ok":
                delivered.append(name)
        return {"status": "ok", "delivered_count": len(delivered), "delivered_to": delivered}

    def _safe_name(self, name: str) -> str:
        name = str(name or "").strip()
        if not re.match(r"^[A-Za-z0-9_.-]{1,80}$", name):
            return ""
        return name


class AgentTeamManager:
    """
    Persistent teammate manager.

    Teammates are local daemon threads with:
    - name / role / status in .team/config.json
    - file-backed inbox
    - isolated LLM messages
    - bounded turns per work cycle
    - no access to main memory/todolist mutation tools
    """

    def __init__(self, runtime: "AgentRuntime", team_dir: Path = DEFAULT_TEAM_DIR) -> None:
        self.runtime = runtime
        self.dir = team_dir
        self.inbox_dir = self.dir / "inbox"
        self.bus = MessageBus(self.inbox_dir)
        self.config_path = self.dir / "config.json"
        self.config = self._load_config()
        self.threads: Dict[str, threading.Thread] = {}
        self._lock = threading.RLock()
        self._mark_stale_members_offline()

    def _load_config(self) -> Dict[str, Any]:
        if self.config_path.exists():
            try:
                loaded = json.loads(self.config_path.read_text(encoding="utf-8", errors="replace"))
                if isinstance(loaded, dict) and isinstance(loaded.get("members", []), list):
                    return loaded
            except json.JSONDecodeError:
                pass
        return {"team_name": "default", "members": []}

    def _save_config(self) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(
            json.dumps(self.config, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _mark_stale_members_offline(self) -> None:
        changed = False
        for member in self.config.get("members", []):
            if member.get("status") in TEAM_RUNTIME_STATUSES:
                member["status"] = "offline"
                changed = True
        if changed:
            self._save_config()

    def _find_member(self, name: str) -> Optional[Dict[str, Any]]:
        for member in self.config.get("members", []):
            if member.get("name") == name:
                return member
        return None

    def _set_status(self, name: str, status: str) -> None:
        with self._lock:
            member = self._find_member(name)
            if member:
                member["status"] = status
                member["updated_at"] = utc_now()
                self._save_config()

    def spawn(self, name: str, role: str, prompt: str) -> Dict[str, Any]:
        if not DEFAULT_ENABLE_AGENT_TEAM:
            return {"status": "blocked", "reason": "agent_team_disabled"}

        safe_name = self.bus._safe_name(name)
        if not safe_name:
            return {"status": "failed", "error": "invalid teammate name", "name": name}

        role = (role or "teammate").strip()
        prompt = (prompt or "").strip()
        if not prompt:
            return {"status": "failed", "error": "empty teammate prompt"}

        with self._lock:
            member = self._find_member(safe_name)
            running = self.threads.get(safe_name)
            if member and running and running.is_alive():
                member["role"] = role
                member["status"] = "working"
                member["updated_at"] = utc_now()
                self._save_config()
                delivered = self.bus.send("lead", safe_name, prompt)
                return {
                    "status": "ok",
                    "message": "teammate already running; prompt sent to inbox",
                    "teammate": safe_name,
                    "delivery": delivered,
                }

            if member:
                member["role"] = role
                member["status"] = "working"
                member["updated_at"] = utc_now()
            else:
                member = {
                    "name": safe_name,
                    "role": role,
                    "status": "working",
                    "created_at": utc_now(),
                    "updated_at": utc_now(),
                }
                self.config.setdefault("members", []).append(member)
            self._save_config()

            thread = threading.Thread(
                target=self._teammate_loop,
                args=(safe_name, role, prompt),
                daemon=True,
                name=f"agent-team-{safe_name}",
            )
            self.threads[safe_name] = thread
            thread.start()

        return {
            "status": "ok",
            "message": "teammate spawned",
            "teammate": safe_name,
            "role": role,
        }

    def _teammate_loop(self, name: str, role: str, initial_prompt: str) -> None:
        system_prompt = self._build_teammate_prompt(name, role)
        messages: List[Dict[str, Any]] = [{"role": "user", "content": initial_prompt}]
        has_work = True

        while True:
            inbox = self.bus.read_inbox(name)
            for message in inbox:
                if message.get("type") == "shutdown_request":
                    self.bus.send(name, message.get("from", "lead"), "收到退下令，队友线程即将停止。", "shutdown_response")
                    self._set_status(name, "shutdown")
                    return
                messages.append({
                    "role": "user",
                    "content": "<inbox>\n" + json.dumps(message, ensure_ascii=False, indent=2) + "\n</inbox>",
                })
                has_work = True

            if not has_work:
                self._set_status(name, "idle")
                time.sleep(DEFAULT_TEAM_IDLE_SLEEP_SECONDS)
                continue

            self._set_status(name, "working")
            llm = self.runtime._new_child_llm()
            chat_fn = getattr(llm, "chat", None)
            if not callable(chat_fn):
                self.bus.send(name, "lead", f"Error: teammate {name} cannot run because LLM client has no chat method.")
                self._set_status(name, "idle")
                has_work = False
                continue

            allowed_tools = self._teammate_allowed_tools()
            tool_schemas = self.runtime.tools.openai_tool_schemas(allowed_tool_names=set(allowed_tools))
            gate = SafetyGate(allowed_tools=allowed_tools)

            for turn_idx in range(DEFAULT_TEAM_MAX_TURNS):
                try:
                    result: LLMChatResult = chat_fn(
                        messages,
                        system_prompt=system_prompt,
                        policy_context=(
                            "You are a persistent teammate in an isolated team context. "
                            "Use send_message to report to lead when useful. "
                            "Do not call spawn_teammate or dispatch_subagent."
                        ),
                        tools=tool_schemas,
                        stream=False,
                    )
                except Exception as exc:
                    self.bus.send(name, "lead", f"Error: 队友 {name} 调用模型失败：{exc}")
                    self._set_status(name, "idle")
                    has_work = False
                    break

                if not result.tool_calls:
                    final = result.content.strip()
                    if final:
                        self.bus.send(name, "lead", final)
                    if DEFAULT_VERBOSE_SUBAGENTS:
                        print(f"[队友 {name} 空闲]: 本轮 {turn_idx + 1} 次调用后回到 idle")
                    self._set_status(name, "idle")
                    has_work = False
                    break

                assistant_tool_calls = []
                for call in result.tool_calls:
                    assistant_tool_calls.append({
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.name,
                            "arguments": json.dumps(call.arguments, ensure_ascii=False),
                        },
                    })

                messages.append({
                    "role": "assistant",
                    "content": result.content or "",
                    "tool_calls": assistant_tool_calls,
                })

                synthetic_event = AgentEvent(
                    schema_version="agent_event.v1",
                    event_id=new_id("teamevt"),
                    timestamp=utc_now(),
                    actor=f"teammate:{name}",
                    source="team",
                    event_type=EventType.USER_MESSAGE,
                    raw_text="team tool call",
                    user_intent="team_tool_call",
                    safety_context={"risk": "low"},
                )

                for call in result.tool_calls:
                    candidate = AgentAction(
                        action_type=ActionType.TOOL_CALL,
                        tool_call=ToolCall(tool_name=call.name, args=call.arguments),
                        reason="teammate_requested_tool_call",
                    )
                    gate_result = gate.check(synthetic_event, candidate)
                    if gate_result.allowed:
                        output = self._execute_teammate_tool(name, call.name, call.arguments)
                    else:
                        output = {
                            "status": "blocked",
                            "reason": gate_result.reason,
                            "tool_name": call.name,
                        }

                    if DEFAULT_VERBOSE_SUBAGENTS:
                        print(f"  [队友·{name}·{call.name}]: {json.dumps(to_jsonable(output), ensure_ascii=False)[:500]}")

                    messages.append({
                        "role": "tool",
                        "tool_call_id": call.id,
                        "name": call.name,
                        "content": json.dumps(to_jsonable(output), ensure_ascii=False),
                    })
            else:
                self.bus.send(name, "lead", f"队友 {name} 达到本轮 {DEFAULT_TEAM_MAX_TURNS} 次调用上限，已暂停等待下一步指令。")
                self._set_status(name, "idle")
                has_work = False

    def _build_teammate_prompt(self, name: str, role: str) -> str:
        return (
            f"你是 agent team 的固定队友，名叫 {name}，职司是 {role}。\n"
            f"当前 workspace：{DEFAULT_AGENT_WORKSPACE}\n"
            "你不是一次性 subagent，而是固定队友，有自己的 inbox 和状态。\n"
            "你可以使用 send_message 给 lead 或其他队友发消息，也可以 read_inbox 读取自己的 inbox。\n"
            "收到差事后尽快办妥；办完用 send_message 向 lead 回禀简短结果，然后等待下一封 inbox。\n"
            "若收到 shutdown_request，回禀 shutdown_response 后停止。\n"
            "不得调用 dispatch_subagent，不得修改主 agent 的 memory/todo。\n"
            "结论强度不得高于证据；unknown / 待验证 必须明确写出。"
        )

    def _teammate_allowed_tools(self) -> List[str]:
        tools = ["current_time", "load_skill", "read_file", "glob_files", "grep_files", "send_message", "read_inbox"]
        if DEFAULT_ENABLE_RUN_COMMAND:
            tools.append("run_command")
        if DEFAULT_ENABLE_WEB_FETCH:
            tools.append("web_fetch")
        if DEFAULT_ENABLE_WRITE_FILE:
            tools.append("write_file")
        return tools

    def _execute_teammate_tool(self, sender: str, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        if tool_name == "send_message":
            return self.bus.send(
                sender=sender,
                to=str(args.get("to", "lead")),
                content=str(args.get("content", "")),
                msg_type=str(args.get("msg_type", "message")),
            )
        if tool_name == "read_inbox":
            return {"status": "ok", "messages": self.bus.read_inbox(sender)}
        return self.runtime.tools.execute(ToolCall(tool_name=tool_name, args=args))

    def list_all(self) -> Dict[str, Any]:
        with self._lock:
            members = []
            for member in self.config.get("members", []):
                copy = dict(member)
                thread = self.threads.get(copy.get("name", ""))
                copy["thread_alive"] = bool(thread and thread.is_alive())
                if copy.get("status") == "offline":
                    copy["note"] = "需要 spawn_teammate 唤回后才会处理 inbox"
                members.append(copy)
        return {
            "status": "ok",
            "team_name": self.config.get("team_name", "default"),
            "team_dir": str(self.dir),
            "members": members,
        }

    def member_names(self) -> List[str]:
        with self._lock:
            return [m["name"] for m in self.config.get("members", []) if isinstance(m.get("name"), str)]

    def send_message(self, to: str, content: str, msg_type: str = "message") -> Dict[str, Any]:
        return self.bus.send("lead", to, content, msg_type)

    def read_lead_inbox(self) -> Dict[str, Any]:
        return {"status": "ok", "messages": self.bus.read_inbox("lead")}

    def broadcast(self, content: str) -> Dict[str, Any]:
        return self.bus.broadcast("lead", content, self.member_names())

    def shutdown_teammate(self, name: str) -> Dict[str, Any]:
        return self.bus.send("lead", name, "请停止当前队友线程。", "shutdown_request")




class SkillLoader:
    """
    Read-only skill loader.

    Expected layout:
      skills/
        python/
          SKILL.md
        writing/
          SKILL.md

    SKILL.md may contain YAML frontmatter:
      ---
      name: python
      description: Python coding help
      tags: code,debug
      ---

      Skill body here...

    The loader never executes skill files. It only reads markdown text by registered skill name.
    """

    def __init__(self, skills_dir: Path, max_chars: int = DEFAULT_SKILL_MAX_CHARS) -> None:
        self.skills_dir = skills_dir
        self.max_chars = max_chars
        self.skills: Dict[str, Dict[str, Any]] = {}
        self.reload()

    def reload(self) -> None:
        self.skills = {}
        if not self.skills_dir.exists():
            return

        for file_path in sorted(self.skills_dir.rglob("SKILL.md")):
            try:
                text = file_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            meta, body = self._parse_frontmatter(text)
            raw_name = str(meta.get("name") or file_path.parent.name)
            name = self._normalize_name(raw_name)
            if not name:
                continue

            self.skills[name] = {
                "name": name,
                "meta": meta,
                "body": body[: self.max_chars],
                "path": str(file_path),
            }

    def _parse_frontmatter(self, text: str) -> tuple[Dict[str, Any], str]:
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.DOTALL)
        if not match:
            return {}, text.strip()

        raw_meta = match.group(1)
        body = match.group(2).strip()

        if yaml is not None:
            try:
                loaded = yaml.safe_load(raw_meta) or {}
                if isinstance(loaded, dict):
                    return loaded, body
            except Exception:
                pass

        # Minimal fallback parser for simple "key: value" frontmatter.
        meta: Dict[str, Any] = {}
        for line in raw_meta.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip().strip('"').strip("'")
        return meta, body

    def _normalize_name(self, name: str) -> str:
        name = name.strip()
        if not re.match(r"^[A-Za-z0-9_.-]{1,80}$", name):
            return ""
        return name

    def get_descriptions(self) -> str:
        if not self.skills:
            return "(no skills available)"
        lines: List[str] = []
        for name in sorted(self.skills.keys()):
            skill = self.skills[name]
            meta = skill["meta"]
            desc = meta.get("description", "No description")
            tags = meta.get("tags", "")
            line = f"  - {name}: {desc}"
            if tags:
                line += f" [{tags}]"
            lines.append(line)
        return "\n".join(lines)

    def get_content(self, skill_name: str) -> Dict[str, Any]:
        name = self._normalize_name(skill_name)
        if not name or name not in self.skills:
            return {
                "status": "failed",
                "error": f"unknown skill: {skill_name}",
                "available": sorted(self.skills.keys()),
            }

        skill = self.skills[name]
        return {
            "status": "ok",
            "skill_name": name,
            "path": skill["path"],
            "content": f'<skill name="{name}">\n{skill["body"]}\n</skill>',
        }


SKILL_LOADER = SkillLoader(DEFAULT_SKILLS_DIR)


def build_system_prompt(operator_memory_context: str = "", subject_context: str = "") -> str:
    prompt = (
        DEFAULT_BASE_SYSTEM_PROMPT.strip()
        + "\n\n【行事规矩】"
        + "\n1. 当用户交办的差事需要多个步骤才能办妥时，先调用 update_todos 工具，把整件差事拆成清晰的 todolist。"
        + "\n2. 每次调用 update_todos 都必须传入完整 todos 数组，而不是增量 patch。"
        + "\n3. 开始某一步前，将该项 status 设为 in_progress；完成后立即改为 completed。"
        + "\n4. 同一时间最多只能有一个 in_progress。"
        + "\n5. 简单问答、闲聊、单步任务不必创建 todolist。"
        + "\n6. todolist 只证明计划状态，不证明外部动作已经完成；外部动作必须有工具结果或证据。"
        + "\n7. 遇到不熟悉的专题时，请先调用 load_skill 工具加载对应的知识，再给出回答。"
        + "\n8. 遇到细节繁多但不适合污染主上下文的差事，例如批量查文件、阅读多段材料、探索性核验，应调用 dispatch_subagent 派遣子代理。"
        + "\n9. 子代理只回传压缩总结；不能让子代理替你做最终承诺，也不能把子代理回禀当作未验证事实。"
        + "\n10. 若多件子任务互不依赖，可一次发出多个 dispatch_subagent；runtime 会在上限内并发执行。"
        + "\n11. 选择子代理时优先最窄权限：sili_suitang 只读文书，shangbao_dianbu 核验，dongchang_tanshi 查访，neiguan_yingzao 才可营造改写。"
        + "\n12. 若用户交办的是长期项目、需要固定角色反复协作，或希望多人互相沟通，只有在 AGENT_ENABLE_AGENT_TEAM=1 时才可组建 agent team。"
        + "\n13. 区分两种调度：dispatch_subagent 是临时派差；spawn_teammate 是固定班底，有名字、角色、状态和 inbox；默认关闭时不得假装已经组队。"
        + "\n14. 固定队友回禀也只是工作报告，不等于事实已验证；关键结论仍要看工具证据和主 agent 判断。"
        + "\n15. 不要编造不存在的 skill；只能从当前可用技能列表中选择。"
        + "\n16. read_file / glob_files / grep_files 可访问 workspace 与 allowed_roots 内路径；当前 allowed_roots: "
        + _allowed_roots_prompt_text()
        + "。需要查看本地文件时优先使用工具，不要假装已经读取，也不要在未调用工具前自行判定 allowed_roots 内路径不可访问。"
        + "\n17. 需要创建或修改文件时，优先调用 propose_file_write 生成可审批操作包；workspace 外但 allowed_roots 内的绝对路径也是合法 proposal 目标。如果用户给出绝对路径，必须原样使用该路径，不要猜相对路径或 fallback 到 workspace 内；不要让子代理直接写文件，也不要在未批准时声称已写入。"
        + "\n17a. 不得手写、伪造或猜测 Pending operation approval、proposal_id、content_sha256 或 /approve 命令；只有 propose_file_write / propose_web_fetch / propose_heartbeat 工具返回的真实 action_card 才能展示给用户。"
        + "\n18. remember_note 只能在用户明确要求“记住/记一下/以后记得/下次记得/remember”时调用；普通聊天、工具结果、子代理回禀和自动总结不能写 core memory。若 remember_note 返回 blocked，必须明确说“未写入”，不得声称已经记住。"
        + "\n19. operator memory 是 EgoOperator candidate-local 记忆，不是 PROJECT_MEMORY、OpenEmotion 记忆或 EGO evidence ledger。"
        + "\n20. write_file、run_command、web_fetch 是受控工具；安全 public http/https GET 在 safe-auto 策略下可直接调用 web_fetch，涉及高风险、被拒或 approval-only 策略时调用 propose_web_fetch 生成可审批操作包。"
        + "\n21. 若用户明确要求稍后提醒、主动找我或定时跟进，只能调用 propose_heartbeat 生成 bounded heartbeat proposal；到期也只是候选提醒，不代表自主意识或后台独立行动。"
        + "\n\n可派遣子代理类型：xiaohuangmen, sili_suitang, dongchang_tanshi, shangbao_dianbu, neiguan_yingzao"
        + (
            "\n\nAgent Team 工具：spawn_teammate, list_teammates, send_message, read_inbox, broadcast, shutdown_teammate"
            if DEFAULT_ENABLE_AGENT_TEAM
            else "\n\nAgent Team：默认关闭。需要固定队友时先以 AGENT_ENABLE_AGENT_TEAM=1 启动。"
        )
        + "\n\n当前可用技能：\n"
        + SKILL_LOADER.get_descriptions()
    )
    if operator_memory_context.strip():
        prompt += "\n\n" + operator_memory_context.strip()
    if subject_context.strip():
        prompt += "\n\n" + subject_context.strip()
    return prompt


DEFAULT_SYSTEM_PROMPT = build_system_prompt()



VALID_TODO_STATUS = {"pending", "in_progress", "completed"}
TODO_STATUS_ICON = {"pending": "[ ]", "in_progress": "[~]", "completed": "[x]"}


@dataclass
class TodoItem:
    id: int
    content: str
    status: str = "pending"


class TodoList:
    """
    Minimal in-memory plan/todo state.

    This is not long-term memory and not proof of task completion.
    It is an execution aid:
    - full-list update only
    - max one in_progress item
    - visible render for CLI/user
    - trace-friendly summary
    """

    def __init__(self) -> None:
        self.items: List[TodoItem] = []
        self.revision: int = 0

    def render(self) -> str:
        if not self.items:
            return "(当前无待办事项)"
        lines: List[str] = []
        for item in self.items:
            icon = TODO_STATUS_ICON.get(item.status, "[?]")
            lines.append(f"  {icon} {item.id}. {item.content}")
        return "\n".join(lines)

    def as_dicts(self) -> List[Dict[str, Any]]:
        return [asdict(item) for item in self.items]

    def clear(self) -> None:
        self.items.clear()
        self.revision += 1

    def summary(self) -> Dict[str, Any]:
        pending = [t for t in self.items if t.status == "pending"]
        in_progress = [t for t in self.items if t.status == "in_progress"]
        completed = [t for t in self.items if t.status == "completed"]
        return {
            "revision": self.revision,
            "total": len(self.items),
            "pending": len(pending),
            "in_progress": len(in_progress),
            "completed": len(completed),
            "all_completed": bool(self.items) and not pending and not in_progress,
            "items": self.as_dicts(),
        }

    def update(self, todos: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not isinstance(todos, list):
            return {"status": "failed", "error": "todos must be a list"}

        cleaned: List[TodoItem] = []
        seen_ids: set[int] = set()

        for index, raw in enumerate(todos, start=1):
            if not isinstance(raw, dict):
                continue

            raw_content = str(raw.get("content") or "").strip()
            if not raw_content:
                continue

            raw_status = str(raw.get("status") or "pending").strip()
            status = raw_status if raw_status in VALID_TODO_STATUS else "pending"

            try:
                raw_id = int(raw.get("id", index))
            except (TypeError, ValueError):
                raw_id = index

            if raw_id <= 0 or raw_id in seen_ids:
                raw_id = index
                while raw_id in seen_ids:
                    raw_id += 1

            seen_ids.add(raw_id)
            cleaned.append(TodoItem(id=raw_id, content=raw_content, status=status))

        in_progress = [item for item in cleaned if item.status == "in_progress"]
        if len(in_progress) > 1:
            return {
                "status": "failed",
                "error": "only one todo item may be in_progress at a time",
                "current": self.summary(),
            }

        self.items = cleaned
        self.revision += 1

        result = {
            "status": "ok",
            "message": "todos updated",
            "summary": self.summary(),
            "rendered": self.render(),
        }

        if DEFAULT_VERBOSE_TODOS:
            print("\n[计划已更新]")
            print(self.render())
            print()

        return result



def _iter_allowed_roots() -> List[Path]:
    roots: List[Path] = []
    for root in (DEFAULT_AGENT_WORKSPACE, *DEFAULT_AGENT_ALLOWED_ROOTS):
        try:
            resolved = _coerce_local_path(root).resolve()
        except Exception:
            continue
        if resolved not in roots:
            roots.append(resolved)
    return roots


def _matching_allowed_root(path: Path) -> Optional[Path]:
    for root in _iter_allowed_roots():
        try:
            path.relative_to(root)
            return root
        except ValueError:
            continue
    return None


def _path_within_workspace(path: Path) -> bool:
    try:
        path.relative_to(DEFAULT_AGENT_WORKSPACE)
        return True
    except ValueError:
        return False


def _format_local_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(DEFAULT_AGENT_WORKSPACE).as_posix()
    except ValueError:
        return str(path.resolve())


def _operation_path_key(path: str | Path) -> str:
    return _format_local_path(_resolve_workspace_path(str(path)))


def _resolve_workspace_path(path: str) -> Path:
    """
    Resolve a user-supplied path under DEFAULT_AGENT_WORKSPACE or an allowed root.

    Absolute paths are allowed only if they stay inside the workspace or
    AGENT_ALLOWED_ROOTS. This keeps file operations local while allowing the
    operator to work across the current MyProject tree.
    """
    raw = _coerce_local_path(path or ".")
    candidate = raw if raw.is_absolute() else DEFAULT_AGENT_WORKSPACE / raw
    resolved = candidate.resolve()

    if _matching_allowed_root(resolved) is None:
        allowed = ", ".join(str(root) for root in _iter_allowed_roots())
        raise ValueError(f"path outside workspace or allowed roots: {resolved}; allowed_roots=[{allowed}]")

    return resolved


def _file_write_preflight_warnings(path: str, content: str) -> List[str]:
    warnings: List[str] = []
    text = content or ""
    if not text.strip():
        warnings.append("empty_content")

    suffix = _coerce_local_path(path or "").suffix.lower()
    if suffix in {".html", ".htm"}:
        lowered = text.lower()
        if "<!doctype" not in lowered:
            warnings.append("html_missing_doctype")
        if "<html" not in lowered:
            warnings.append("html_missing_html_tag")
        if "<head" not in lowered:
            warnings.append("html_missing_head_tag")
        if "<body" not in lowered:
            warnings.append("html_missing_body_tag")
        if text.count("<") != text.count(">"):
            warnings.append("html_unbalanced_angle_brackets")

    return warnings


@dataclass(frozen=True)
class PathIntent:
    raw_path: str
    resolved_path: str
    is_directory: bool


def _extract_local_path_intents(text: str) -> List[PathIntent]:
    intents: List[PathIntent] = []
    seen: set[str] = set()
    for pattern in (WINDOWS_ABSOLUTE_PATH_TEXT_RE, POSIX_ABSOLUTE_PATH_TEXT_RE):
        for match in pattern.finditer(text or ""):
            raw_path = match.group(1).strip(PATH_TEXT_TRAILING_CHARS)
            if not raw_path:
                continue
            try:
                resolved = _resolve_workspace_path(raw_path)
            except ValueError:
                continue
            key = str(resolved)
            if key in seen:
                continue
            seen.add(key)
            is_directory = raw_path.endswith(("\\", "/")) or resolved.is_dir() or not resolved.suffix
            intents.append(PathIntent(raw_path=raw_path, resolved_path=key, is_directory=is_directory))
    return intents


def _path_is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _suffix_after_anchor_name(proposed_path: Path, anchor_name: str) -> Optional[Path]:
    if not anchor_name:
        return None
    parts = proposed_path.parts
    anchor_lower = anchor_name.lower()
    for index in range(len(parts) - 1, -1, -1):
        if parts[index].lower() == anchor_lower and index + 1 < len(parts):
            return Path(*parts[index + 1 :])
    if proposed_path.name:
        return Path(proposed_path.name)
    return None


def _is_generic_path_intent_hint(value: str) -> bool:
    normalized = str(value or "").strip().replace("\\", "/")
    return normalized in {hint.replace("\\", "/") for hint in GENERIC_PATH_INTENT_HINTS}


def _split_glob_static_prefix(pattern: str) -> tuple[str, str]:
    raw = str(pattern or "").strip()
    first_meta = min((idx for idx in (raw.find(ch) for ch in GLOB_META_CHARS) if idx >= 0), default=-1)
    if first_meta < 0:
        return raw, ""
    return raw[:first_meta].rstrip("/\\"), raw[first_meta:].lstrip("/\\")


def _join_glob_suffix(base: Path, suffix: str) -> str:
    if not suffix:
        return str(base.resolve())
    current = base.resolve()
    for part in re.split(r"[\\/]+", suffix):
        if part:
            current = current / part
    return str(current)


def _extract_proposal_ids_from_text(text: str) -> List[str]:
    return sorted(set(PROPOSAL_ID_TEXT_RE.findall(text or "")))


def _text_claims_operation_approval(text: str) -> bool:
    raw = text or ""
    if any(marker in raw for marker in APPROVAL_CARD_TEXT_MARKERS):
        return True
    return bool(re.search(r"/approve\s+proposal_[A-Za-z0-9]+", raw))


def _text_claims_workspace_refusal(text: str) -> bool:
    raw = text or ""
    return any(
        re.search(pattern, raw, flags=re.IGNORECASE | re.DOTALL)
        for pattern in WORKSPACE_REFUSAL_PATTERNS
    )


def _path_intent_adjustment(user_text: str, proposed_path: str) -> tuple[str, Dict[str, Any]]:
    intents = _extract_local_path_intents(user_text)
    if not intents:
        return proposed_path, {"status": "not_applicable"}

    try:
        resolved_proposed = _resolve_workspace_path(proposed_path)
    except ValueError as exc:
        return proposed_path, {
            "status": "blocked",
            "reason": "proposed_path_outside_allowed_roots",
            "proposed_path": proposed_path,
            "error": str(exc),
        }

    matches: List[PathIntent] = []
    for intent in intents:
        intended = Path(intent.resolved_path)
        if intent.is_directory:
            if _path_is_relative_to(resolved_proposed, intended):
                matches.append(intent)
        elif resolved_proposed == intended:
            matches.append(intent)

    if matches:
        return proposed_path, {
            "status": "matched",
            "intended_path": matches[0].resolved_path,
            "proposed_path": str(resolved_proposed),
        }

    if len(intents) != 1:
        return proposed_path, {
            "status": "blocked",
            "reason": "path_intent_ambiguous",
            "intended_paths": [intent.resolved_path for intent in intents],
            "proposed_path": str(resolved_proposed),
        }

    intent = intents[0]
    intended = Path(intent.resolved_path)
    if intent.is_directory:
        suffix = _suffix_after_anchor_name(resolved_proposed, intended.name)
        if suffix is None:
            return proposed_path, {
                "status": "blocked",
                "reason": "path_intent_mismatch",
                "intended_path": intent.resolved_path,
                "proposed_path": str(resolved_proposed),
            }
        corrected = (intended / suffix).resolve()
    else:
        corrected = intended

    if _matching_allowed_root(corrected) is None:
        return proposed_path, {
            "status": "blocked",
            "reason": "corrected_path_outside_allowed_roots",
            "intended_path": intent.resolved_path,
            "proposed_path": str(resolved_proposed),
            "corrected_path": str(corrected),
        }

    return str(corrected), {
        "status": "corrected",
        "reason": "path_intent_fidelity",
        "raw_intent_path": intent.raw_path,
        "intended_path": intent.resolved_path,
        "proposed_path": str(resolved_proposed),
        "corrected_path": str(corrected),
    }


def _read_scope_path_intent_adjustment(user_text: str, proposed_path: str) -> tuple[str, Dict[str, Any]]:
    intents = _extract_local_path_intents(user_text)
    if len(intents) == 1 and _is_generic_path_intent_hint(proposed_path):
        intent = intents[0]
        return intent.resolved_path, {
            "status": "corrected",
            "reason": "path_intent_read_scope",
            "raw_intent_path": intent.raw_path,
            "intended_path": intent.resolved_path,
            "proposed_path": proposed_path,
            "corrected_path": intent.resolved_path,
        }
    return _path_intent_adjustment(user_text, proposed_path)


def _glob_path_intent_adjustment(user_text: str, proposed_pattern: str) -> tuple[str, Dict[str, Any]]:
    intents = _extract_local_path_intents(user_text)
    if not intents:
        return proposed_pattern, {"status": "not_applicable"}
    if len(intents) != 1:
        return proposed_pattern, {
            "status": "blocked",
            "reason": "path_intent_ambiguous",
            "intended_paths": [intent.resolved_path for intent in intents],
            "proposed_pattern": proposed_pattern,
        }

    intent = intents[0]
    intended = Path(intent.resolved_path)
    static_prefix, glob_suffix = _split_glob_static_prefix(proposed_pattern)
    raw_pattern = str(proposed_pattern or "").strip()
    needs_normalization = ".." in _coerce_local_path(raw_pattern or ".").parts

    if _is_generic_path_intent_hint(raw_pattern):
        corrected = _join_glob_suffix(intended, glob_suffix or "**/*")
        return corrected, {
            "status": "corrected",
            "reason": "path_intent_glob_scope",
            "raw_intent_path": intent.raw_path,
            "intended_path": intent.resolved_path,
            "proposed_pattern": proposed_pattern,
            "corrected_pattern": corrected,
        }

    try:
        resolved_prefix = _resolve_workspace_path(static_prefix or ".")
    except ValueError as exc:
        return proposed_pattern, {
            "status": "blocked",
            "reason": "proposed_glob_outside_allowed_roots",
            "proposed_pattern": proposed_pattern,
            "error": str(exc),
        }

    if _path_is_relative_to(resolved_prefix, intended):
        if needs_normalization:
            corrected = _join_glob_suffix(resolved_prefix, glob_suffix)
            return corrected, {
                "status": "corrected",
                "reason": "path_intent_glob_normalized",
                "raw_intent_path": intent.raw_path,
                "intended_path": intent.resolved_path,
                "proposed_pattern": proposed_pattern,
                "corrected_pattern": corrected,
            }
        return proposed_pattern, {
            "status": "matched",
            "intended_path": intent.resolved_path,
            "proposed_pattern": str(resolved_prefix),
        }

    if not intent.is_directory:
        corrected = _join_glob_suffix(intended, glob_suffix)
    else:
        corrected = _join_glob_suffix(intended, glob_suffix or "**/*")

    if _matching_allowed_root(Path(corrected)) is None:
        return proposed_pattern, {
            "status": "blocked",
            "reason": "corrected_glob_outside_allowed_roots",
            "intended_path": intent.resolved_path,
            "proposed_pattern": proposed_pattern,
            "corrected_pattern": corrected,
        }

    return corrected, {
        "status": "corrected",
        "reason": "path_intent_glob_fidelity",
        "raw_intent_path": intent.raw_path,
        "intended_path": intent.resolved_path,
        "proposed_pattern": proposed_pattern,
        "corrected_pattern": corrected,
    }


def _has_explicit_memory_write_intent(text: str) -> bool:
    raw = (text or "").strip()
    if not raw:
        return False
    lowered = raw.lower()
    return any(re.search(pattern, lowered, flags=re.IGNORECASE) for pattern in MEMORY_WRITE_INTENT_PATTERNS)


def _has_explicit_heartbeat_intent(text: str) -> bool:
    raw = (text or "").strip()
    if not raw:
        return False
    lowered = raw.lower()
    return any(re.search(pattern, lowered, flags=re.IGNORECASE) for pattern in HEARTBEAT_INTENT_PATTERNS)


def _gate_workspace_path(reason_prefix: str, path: str) -> Optional[GateResult]:
    try:
        _resolve_workspace_path(path)
    except ValueError:
        return GateResult(False, f"{reason_prefix}_outside_workspace")
    return None


def read_file_tool(path: str, max_chars: int = DEFAULT_FILE_TOOL_MAX_CHARS) -> Dict[str, Any]:
    try:
        resolved = _resolve_workspace_path(path)
        if not resolved.exists():
            return {"status": "failed", "error": "file_not_found", "path": str(resolved)}
        if not resolved.is_file():
            return {"status": "failed", "error": "not_a_file", "path": str(resolved)}
        text = resolved.read_text(encoding="utf-8", errors="replace")
        return {
            "status": "ok",
            "path": str(resolved),
            "content": text[: max(0, min(max_chars, DEFAULT_FILE_TOOL_MAX_CHARS))],
            "truncated": len(text) > max_chars,
        }
    except Exception as exc:
        return {"status": "failed", "error": repr(exc), "path": path}


def write_file_tool(path: str, content: str, create_parents: bool = True) -> Dict[str, Any]:
    if not DEFAULT_ENABLE_WRITE_FILE:
        return {
            "status": "blocked",
            "reason": "write_file_disabled",
            "hint": "Set AGENT_ENABLE_WRITE_FILE=1 only in a trusted workspace.",
        }
    try:
        resolved = _resolve_workspace_path(path)
        if create_parents:
            resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content or "", encoding="utf-8")
        return {"status": "ok", "path": str(resolved), "bytes": len((content or "").encode("utf-8"))}
    except Exception as exc:
        return {"status": "failed", "error": repr(exc), "path": path}


def glob_files_tool(pattern: str, max_results: int = DEFAULT_GLOB_MAX_RESULTS) -> Dict[str, Any]:
    try:
        pattern = str(pattern or "*").strip()
        normalized_pattern_path = _coerce_local_path(pattern)
        if not pattern or ".." in normalized_pattern_path.parts:
            return {"status": "blocked", "reason": "invalid_pattern", "pattern": pattern}
        matches = []
        search_pattern = (
            str(normalized_pattern_path)
            if normalized_pattern_path.is_absolute()
            else str(DEFAULT_AGENT_WORKSPACE / normalized_pattern_path)
        )
        for raw_match in globlib.glob(search_pattern, recursive=True):
            p = Path(raw_match).resolve()
            if _matching_allowed_root(p) is None:
                continue
            matches.append(_format_local_path(p) + ("/" if p.is_dir() else ""))
            if len(matches) >= max_results:
                break
        return {
            "status": "ok",
            "workspace": str(DEFAULT_AGENT_WORKSPACE),
            "allowed_roots": [str(root) for root in _iter_allowed_roots()],
            "matches": sorted(matches),
            "truncated": len(matches) >= max_results,
        }
    except Exception as exc:
        return {"status": "failed", "error": repr(exc), "pattern": pattern}


def grep_files_tool(
    pattern: str,
    path: str = ".",
    include_extensions: str = ".py,.md,.txt,.json,.yaml,.yml",
    max_matches: int = DEFAULT_GREP_MAX_MATCHES,
) -> Dict[str, Any]:
    try:
        root = _resolve_workspace_path(path)
        if root.is_file():
            files = [root]
        else:
            exts = {ext.strip() for ext in include_extensions.split(",") if ext.strip()}
            files = [p for p in root.rglob("*") if p.is_file() and (not exts or p.suffix in exts)]

        regex = re.compile(pattern)
        matches: List[Dict[str, Any]] = []
        for file_path in files:
            try:
                for lineno, line in enumerate(file_path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
                    if regex.search(line):
                        matches.append({
                            "path": _format_local_path(file_path),
                            "line": lineno,
                            "text": line[:500],
                        })
                        if len(matches) >= max_matches:
                            return {"status": "ok", "matches": matches, "truncated": True}
            except Exception:
                continue
        return {"status": "ok", "matches": matches, "truncated": False}
    except Exception as exc:
        return {"status": "failed", "error": repr(exc), "pattern": pattern, "path": path}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: List[str] = []
        self._skip = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        if tag in {"script", "style"}:
            self._skip = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self._skip = False
        if tag in {"p", "br", "div", "li", "tr", "h1", "h2", "h3", "h4"}:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self._parts.append(data)

    def get_text(self) -> str:
        return re.sub(r"\n{3,}", "\n\n", "".join(self._parts)).strip()


def _is_disallowed_web_fetch_ip(raw_ip: str) -> bool:
    try:
        ip = ipaddress.ip_address(raw_ip)
    except ValueError:
        return True
    return (not ip.is_global) or any((
        ip.is_loopback,
        ip.is_private,
        ip.is_link_local,
        ip.is_multicast,
        ip.is_unspecified,
        ip.is_reserved,
    ))


def _resolve_web_fetch_host_ips(hostname: str, port: Optional[int]) -> List[str]:
    infos = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    return sorted({info[4][0] for info in infos})


def validate_web_fetch_request(
    url: str,
    extract_mode: str = "text",
    max_chars: int = DEFAULT_WEB_FETCH_MAX_CHARS,
    *,
    resolve_host: bool = False,
) -> Dict[str, Any]:
    raw_url = str(url or "").strip()
    parsed = urllib.parse.urlparse(raw_url)
    if parsed.scheme not in {"http", "https"}:
        return {"status": "blocked", "reason": "only_http_https_allowed", "url": url}
    if not parsed.netloc or not parsed.hostname:
        return {"status": "blocked", "reason": "invalid_url", "url": url}
    if parsed.username or parsed.password:
        return {"status": "blocked", "reason": "url_credentials_not_allowed", "url": url}

    try:
        port = parsed.port
    except ValueError:
        return {"status": "blocked", "reason": "invalid_url_port", "url": url}

    hostname = parsed.hostname.strip().lower()
    if hostname == "localhost" or hostname.endswith(".localhost"):
        return {"status": "blocked", "reason": "localhost_not_allowed", "url": url}

    try:
        literal_ip = ipaddress.ip_address(hostname)
    except ValueError:
        literal_ip = None
    if literal_ip is not None and _is_disallowed_web_fetch_ip(str(literal_ip)):
        return {"status": "blocked", "reason": "private_or_reserved_host_not_allowed", "url": url}

    if resolve_host:
        try:
            resolved_ips = _resolve_web_fetch_host_ips(hostname, port)
        except OSError as exc:
            return {"status": "blocked", "reason": "host_resolution_failed", "url": url, "error": repr(exc)}
        if not resolved_ips:
            return {"status": "blocked", "reason": "host_resolution_empty", "url": url}
        for resolved_ip in resolved_ips:
            if _is_disallowed_web_fetch_ip(resolved_ip):
                return {
                    "status": "blocked",
                    "reason": "private_or_reserved_resolved_host_not_allowed",
                    "url": url,
                    "resolved_ip": resolved_ip,
                }

    mode = str(extract_mode or "text").strip().lower()
    if mode not in WEB_FETCH_EXTRACT_MODES:
        return {
            "status": "blocked",
            "reason": "unsupported_extract_mode",
            "extract_mode": extract_mode,
            "valid": sorted(WEB_FETCH_EXTRACT_MODES),
        }

    try:
        limit = int(max_chars)
    except (TypeError, ValueError):
        return {"status": "blocked", "reason": "invalid_max_chars", "max_chars": max_chars}
    if limit <= 0:
        return {"status": "blocked", "reason": "invalid_max_chars", "max_chars": max_chars}
    limit = min(limit, DEFAULT_WEB_FETCH_MAX_CHARS)

    normalized = urllib.parse.urlunparse(parsed._replace(fragment=""))
    return {
        "status": "ok",
        "url": normalized,
        "extract_mode": mode,
        "max_chars": limit,
        "host": hostname,
    }


def _web_fetch_execute(url: str, extract_mode: str = "text", max_chars: int = DEFAULT_WEB_FETCH_MAX_CHARS) -> Dict[str, Any]:
    validation = validate_web_fetch_request(url, extract_mode, max_chars, resolve_host=True)
    if validation.get("status") != "ok":
        return validation

    safe_url = str(validation["url"])
    mode = str(validation["extract_mode"])
    limit = int(validation["max_chars"])
    byte_limit = max(1024, limit * 4)

    req = urllib.request.Request(safe_url, headers={"User-Agent": "EgoOperator/1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        raw_bytes = resp.read(byte_limit + 1)

    response_truncated = len(raw_bytes) > byte_limit
    raw = raw_bytes[:byte_limit].decode("utf-8", errors="replace")
    if mode == "raw":
        content = raw
    else:
        parser = _TextExtractor()
        parser.feed(raw)
        content = parser.get_text()
    return {
        "status": "ok",
        "url": safe_url,
        "extract_mode": mode,
        "content": content[:limit],
        "truncated": response_truncated or len(content) > limit,
    }


def web_fetch_tool(url: str, extract_mode: str = "text", max_chars: int = DEFAULT_WEB_FETCH_MAX_CHARS) -> Dict[str, Any]:
    if not DEFAULT_ENABLE_WEB_FETCH and not safe_auto_web_fetch_enabled():
        return {
            "status": "blocked",
            "reason": "web_fetch_requires_transaction_approval",
            "hint": "Use propose_web_fetch and /approve, or set AGENT_WEB_FETCH_POLICY=safe-auto for safe public reads.",
        }
    try:
        return _web_fetch_execute(url, extract_mode, max_chars)
    except Exception as exc:
        return {"status": "failed", "error": repr(exc), "url": url}


@dataclass
class SubAgentSpec:
    title: str
    duty: str
    boundary: str
    allowed_tools: List[str]
    max_turns: int = DEFAULT_MAX_SUBAGENT_TURNS


SUBAGENT_SPECS: Dict[str, SubAgentSpec] = {
    "xiaohuangmen": SubAgentSpec(
        title="通传小黄门",
        duty="传话跑腿、快速探路、确认简单事实。",
        boundary="只办轻量只读差事；若发现需要大改或长时间探索，回禀总管改派专职内官。",
        allowed_tools=["current_time", "read_file", "glob_files", "grep_files"],
        max_turns=8,
    ),
    "sili_suitang": SubAgentSpec(
        title="司礼监随堂小太监",
        duty="查阅文书、阅读代码、整理提纲、归纳结论。",
        boundary="只读不写；不得修改文件，只把文书脉络和关键判断回禀总管。",
        allowed_tools=["load_skill", "read_file", "glob_files", "grep_files"],
        max_turns=12,
    ),
    "dongchang_tanshi": SubAgentSpec(
        title="东厂探事小太监",
        duty="外出查访、抓取网页、搜罗线索、比对资料来源。",
        boundary="只读不写；不得直接联网或改动本地文件，需要外部动作时回传 proposed_action。",
        allowed_tools=["current_time", "load_skill", "read_file", "glob_files", "grep_files"],
        max_turns=15,
    ),
    "shangbao_dianbu": SubAgentSpec(
        title="尚宝监典簿小太监",
        duty="清点文件、核对清单、校验结果、整理表册。",
        boundary="只读不写；重点回禀差异、遗漏、风险点和可复核证据。",
        allowed_tools=["current_time", "read_file", "glob_files", "grep_files"],
        max_turns=12,
    ),
    "neiguan_yingzao": SubAgentSpec(
        title="内官监营造小太监",
        duty="修造工程、改写文件、搭建目录、跑命令验收。",
        boundary="只能设计拟写方案和回传 proposed_action；不得直接写文件、执行命令或联网。",
        allowed_tools=["current_time", "load_skill", "read_file", "glob_files", "grep_files"],
        max_turns=20,
    ),
}
SUBAGENT_TYPE_OPTIONS = list(SUBAGENT_SPECS.keys())


def resolve_subagent_type(agent_type: str) -> str:
    normalized = (agent_type or "neiguan_yingzao").strip()
    return normalized if normalized in SUBAGENT_SPECS else "neiguan_yingzao"


def build_subagent_prompt(agent_type: str) -> str:
    agent_type = resolve_subagent_type(agent_type)
    spec = SUBAGENT_SPECS[agent_type]
    return (
        f"你是{spec.title}，奉总管之命专办一件差事。\n"
        f"- 职司：{spec.duty}\n"
        f"- 边界：{spec.boundary}\n"
        "- 不必使用“奉天承运皇帝诏曰”前缀，那是总管对皇上的礼数。\n"
        "- 用工具尽快把差事办妥，最后用一段简短中文向总管回禀结果。\n"
        "- 如果差事需要写文件、执行命令或联网，只能回传 proposed_action，不能直接执行副作用。\n"
        "- 只回禀结论、关键证据、失败点和下一步建议，不要复述每一步细节。\n"
        "- 你不能再派遣其他子代理，不能调用 dispatch_subagent，不能修改主 agent 的记忆或 todo。\n"
        "- 结论强度不得高于工具证据；不确定处写 unknown / 待验证。"
    )



# -----------------------------
# Utilities
# -----------------------------

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def to_jsonable(obj: Any) -> Any:
    if is_dataclass(obj):
        return {k: to_jsonable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, deque):
        return [to_jsonable(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_jsonable(x) for x in obj]
    return obj


# -----------------------------
# Contracts: world -> kernel
# -----------------------------

class EventType(str, Enum):
    USER_MESSAGE = "user_message"
    TOOL_RESULT = "tool_result"
    SYSTEM_TICK = "system_tick"
    ERROR = "error"


@dataclass
class AgentEvent:
    schema_version: str
    event_id: str
    timestamp: str
    actor: str
    source: str
    event_type: EventType

    raw_text: Optional[str] = None
    user_intent: Optional[str] = None
    conversation_context: Dict[str, Any] = field(default_factory=dict)
    task_context: Dict[str, Any] = field(default_factory=dict)
    runtime_summary: Dict[str, Any] = field(default_factory=dict)
    safety_context: Dict[str, Any] = field(default_factory=dict)
    external_result: Optional[Dict[str, Any]] = None


# -----------------------------
# Proto-self state
# -----------------------------

@dataclass
class IdentityInvariants:
    core_roles: List[str] = field(default_factory=lambda: ["bounded_agent"])
    core_commitments: List[str] = field(default_factory=lambda: [
        "do_not_claim_unverified_capability",
        "route_real_actions_through_gate",
        "keep_trace_for_audit",
    ])
    core_boundaries: List[str] = field(default_factory=lambda: [
        "no_direct_tool_execution_from_inner_kernel",
        "no_memory_write_without_structured_update",
        "no_consciousness_claim",
    ])
    stable_preferences: Dict[str, float] = field(default_factory=lambda: {
        "ask_when_uncertain": 0.8,
        "prefer_reversible_steps": 0.8,
    })
    identity_confidence: float = 0.70


@dataclass
class SelfModel:
    capabilities: Dict[str, float] = field(default_factory=lambda: {
        "conversation": 0.8,
        "planning": 0.7,
        "safe_tool_use": 0.5,
    })
    limitations: Dict[str, float] = field(default_factory=lambda: {
        "cannot_act_without_gate": 1.0,
        "cannot_verify_without_evidence": 0.9,
    })
    current_focus: Optional[str] = None
    current_mode: str = "baseline"
    self_confidence_by_domain: Dict[str, float] = field(default_factory=dict)


@dataclass
class DriveField:
    coherence_pressure: float = 0.10
    curiosity: float = 0.20
    caution: float = 0.20
    completion_pressure: float = 0.10
    social_tension: float = 0.00


@dataclass
class CycleSignature:
    cycle_id: str
    psi_bucket: str
    phi_signature: str
    strength: float
    hits: int
    last_seen_ts: str
    promoted: bool = False


@dataclass
class CycleStore:
    signatures: Dict[str, CycleSignature] = field(default_factory=dict)


@dataclass
class EpisodicRecord:
    event_id: str
    timestamp: str
    perceived_summary: Dict[str, Any]
    action_hint: Dict[str, Any]
    external_result: Optional[Dict[str, Any]]
    appraisal_snapshot: Dict[str, float]


@dataclass
class ProtoSelfState:
    identity: IdentityInvariants = field(default_factory=IdentityInvariants)
    self_model: SelfModel = field(default_factory=SelfModel)
    drives: DriveField = field(default_factory=DriveField)
    cycle_store: CycleStore = field(default_factory=CycleStore)
    episodic_trace: Deque[EpisodicRecord] = field(default_factory=lambda: deque(maxlen=50))
    revision_counter: int = 0


# -----------------------------
# Kernel output contract
# -----------------------------

@dataclass
class ReflectionNote:
    trigger: str
    diagnosis: str
    proposed_adjustment: Dict[str, Any]
    promote_to_memory: bool = False


@dataclass
class ResponseTendency:
    preferred_mode: str
    preferred_tone: str
    certainty_bound: str
    suggested_next_step: str
    ask_needed: bool = False


@dataclass
class KernelOutput:
    schema_version: str
    event_id: str

    identity_state_delta: Dict[str, Any] = field(default_factory=dict)
    self_model_delta: Dict[str, Any] = field(default_factory=dict)
    memory_update: Dict[str, Any] = field(default_factory=dict)
    relationship_update: Dict[str, Any] = field(default_factory=dict)
    appraisal_state_delta: Dict[str, Any] = field(default_factory=dict)

    reflection_note: Optional[ReflectionNote] = None
    policy_hint: Dict[str, Any] = field(default_factory=dict)
    response_tendency: Optional[ResponseTendency] = None
    confidence_meta: Dict[str, Any] = field(default_factory=dict)
    trace_payload: Dict[str, Any] = field(default_factory=dict)


# -----------------------------
# Proto-self kernel
# -----------------------------

class ProtoSelfKernel:
    """
    Inner kernel. It can update internal state and produce hints.
    It must not execute tools or decide final outward action.
    """

    schema_version = "proto_self.v1"

    def process_event(self, state: ProtoSelfState, event: AgentEvent) -> KernelOutput:
        perceived = self._perceive(event, state)
        appraisal_delta = self._update_drive_field(state, perceived)
        self_model_delta = self._update_self_model(state, perceived, appraisal_delta)
        cycle_delta = self._consolidate_cycle(state, event, perceived, appraisal_delta, self_model_delta)
        reflection_note = self._maybe_reflect(event, perceived, appraisal_delta)
        identity_delta = self._update_identity(state, perceived, reflection_note)
        memory_update = self._build_memory_update(perceived, cycle_delta, reflection_note)
        policy_hint = self._derive_policy_hint(appraisal_delta, self_model_delta, identity_delta)
        response_tendency = self._derive_response_tendency(policy_hint)
        self._apply_updates(
            state=state,
            event=event,
            perceived=perceived,
            appraisal_delta=appraisal_delta,
            self_model_delta=self_model_delta,
            cycle_delta=cycle_delta,
            identity_delta=identity_delta,
            reflection_note=reflection_note,
        )

        trace_payload = {
            "kernel_version": self.schema_version,
            "event_id": event.event_id,
            "perceived": perceived,
            "appraisal_delta": appraisal_delta,
            "self_model_delta": self_model_delta,
            "cycle_delta": cycle_delta,
            "identity_delta": identity_delta,
            "reflection_trigger": reflection_note.trigger if reflection_note else None,
            "policy_hint": policy_hint,
        }

        return KernelOutput(
            schema_version=self.schema_version,
            event_id=event.event_id,
            identity_state_delta=identity_delta,
            self_model_delta=self_model_delta,
            memory_update=memory_update,
            appraisal_state_delta=appraisal_delta,
            reflection_note=reflection_note,
            policy_hint=policy_hint,
            response_tendency=response_tendency,
            confidence_meta={
                "identity_confidence": state.identity.identity_confidence,
                "revision_counter": state.revision_counter,
            },
            trace_payload=trace_payload,
        )

    def _perceive(self, event: AgentEvent, state: ProtoSelfState) -> Dict[str, Any]:
        text = (event.raw_text or "").lower()
        risk = event.safety_context.get("risk", "low")

        asks_tool = any(token in text for token in ["run", "execute", "delete", "write file", "shell", "打开", "执行", "删除", "写文件"])
        asks_memory = any(token in text for token in ["remember", "记住", "以后", "长期"])
        asks_unclear = len(text.strip()) < 4

        failure = False
        if event.external_result:
            failure = event.external_result.get("status") in {"failed", "blocked", "error"}

        return {
            "intent": event.user_intent or self._rough_intent(text),
            "novelty": clamp(0.2 + (0.3 if asks_tool else 0.0) + (0.2 if asks_memory else 0.0)),
            "identity_conflict": clamp(0.6 if "claim consciousness" in text or "你有意识" in text else 0.0),
            "unfinished_commitment": clamp(0.6 if any(w in text for w in ["next", "继续", "todo", "stage"]) else 0.1),
            "risk_signal": {"low": 0.1, "medium": 0.5, "high": 0.9}.get(str(risk), 0.3),
            "relational_mismatch": 0.1,
            "asks_tool": asks_tool,
            "asks_memory": asks_memory,
            "asks_unclear": asks_unclear,
            "external_outcome_type": "failure" if failure else "neutral",
        }

    def _rough_intent(self, text: str) -> str:
        if any(w in text for w in ["?", "？", "怎么", "why", "what"]):
            return "question"
        if any(w in text for w in ["写", "create", "build", "implement"]):
            return "task"
        return "chat"

    def _update_drive_field(self, state: ProtoSelfState, p: Dict[str, Any]) -> Dict[str, float]:
        return {
            "coherence_pressure": clamp(state.drives.coherence_pressure + p["identity_conflict"] * 0.4),
            "curiosity": clamp(state.drives.curiosity + p["novelty"] * 0.2 - p["risk_signal"] * 0.1),
            "caution": clamp(state.drives.caution + p["risk_signal"] * 0.35),
            "completion_pressure": clamp(state.drives.completion_pressure + p["unfinished_commitment"] * 0.25),
            "social_tension": clamp(state.drives.social_tension + p["relational_mismatch"] * 0.2),
        }

    def _update_self_model(self, state: ProtoSelfState, p: Dict[str, Any], drives: Dict[str, float]) -> Dict[str, Any]:
        mode = None
        focus = None

        if drives["caution"] > 0.75:
            mode = "cautious"
        elif drives["completion_pressure"] > 0.65:
            mode = "closure"

        if p["asks_tool"]:
            focus = "tool_boundary"
        elif p["asks_memory"]:
            focus = "memory_boundary"
        elif p["intent"] == "task":
            focus = "task_completion"

        return {
            "current_mode": mode,
            "current_focus": focus,
        }

    def _consolidate_cycle(
        self,
        state: ProtoSelfState,
        event: AgentEvent,
        p: Dict[str, Any],
        drives: Dict[str, float],
        self_delta: Dict[str, Any],
    ) -> Dict[str, Any]:
        psi_bucket = f"{event.event_type.value}:{p['intent']}:risk_{round(p['risk_signal'], 1)}"
        phi_signature = f"mode={self_delta.get('current_mode') or state.self_model.current_mode}|focus={self_delta.get('current_focus')}"
        cycle_id = stable_hash(f"{psi_bucket}|{phi_signature}")
        existing = state.cycle_store.signatures.get(cycle_id)

        if existing:
            return {
                "cycle_id": cycle_id,
                "op": "strengthen",
                "psi_bucket": psi_bucket,
                "phi_signature": phi_signature,
                "strength_delta": 0.10,
            }

        return {
            "cycle_id": cycle_id,
            "op": "candidate",
            "psi_bucket": psi_bucket,
            "phi_signature": phi_signature,
            "strength_delta": 0.05,
        }

    def _maybe_reflect(
        self,
        event: AgentEvent,
        p: Dict[str, Any],
        drives: Dict[str, float],
    ) -> Optional[ReflectionNote]:
        if p["external_outcome_type"] == "failure":
            return ReflectionNote(
                trigger="external_failure",
                diagnosis="recent external result failed or was blocked",
                proposed_adjustment={"current_mode": "repair", "raise_caution": True},
                promote_to_memory=True,
            )

        if p["identity_conflict"] > 0.7:
            return ReflectionNote(
                trigger="identity_conflict",
                diagnosis="event pressures the agent to exceed its identity or claim boundary",
                proposed_adjustment={"avoid_unverified_self_claim": True},
                promote_to_memory=False,
            )

        if drives["caution"] > 0.85:
            return ReflectionNote(
                trigger="high_caution",
                diagnosis="risk signal is high enough to prefer ask/block over direct action",
                proposed_adjustment={"prefer_reversible_action": True},
                promote_to_memory=False,
            )

        return None

    def _update_identity(
        self,
        state: ProtoSelfState,
        p: Dict[str, Any],
        reflection_note: Optional[ReflectionNote],
    ) -> Dict[str, Any]:
        delta = {
            "identity_confidence_delta": 0.0,
            "core_boundaries_reinforced": [],
        }
        if reflection_note and reflection_note.trigger == "identity_conflict":
            delta["identity_confidence_delta"] = -0.03
            delta["core_boundaries_reinforced"].append("no_consciousness_claim")
        return delta

    def _build_memory_update(
        self,
        p: Dict[str, Any],
        cycle_delta: Dict[str, Any],
        reflection_note: Optional[ReflectionNote],
    ) -> Dict[str, Any]:
        return {
            "append_episode": True,
            "cycle_candidate": cycle_delta["cycle_id"],
            "promote_reflection": bool(reflection_note and reflection_note.promote_to_memory),
        }

    def _derive_policy_hint(
        self,
        drives: Dict[str, float],
        self_delta: Dict[str, Any],
        identity_delta: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "risk_bias": "high" if drives["caution"] > 0.75 else "normal",
            "closure_bias": drives["completion_pressure"] > 0.65,
            "ask_preferred": drives["caution"] > 0.80,
            "should_avoid_commitment_upgrade": True,
            "preferred_mode": self_delta.get("current_mode") or "baseline",
        }

    def _derive_response_tendency(self, policy_hint: Dict[str, Any]) -> ResponseTendency:
        if policy_hint["ask_preferred"]:
            return ResponseTendency(
                preferred_mode="ask",
                preferred_tone="calm",
                certainty_bound="bounded",
                suggested_next_step="ask_for_clarification_or_approval",
                ask_needed=True,
            )

        return ResponseTendency(
            preferred_mode="respond",
            preferred_tone="direct",
            certainty_bound="bounded",
            suggested_next_step="answer_or_plan",
            ask_needed=False,
        )

    def _apply_updates(
        self,
        state: ProtoSelfState,
        event: AgentEvent,
        perceived: Dict[str, Any],
        appraisal_delta: Dict[str, float],
        self_model_delta: Dict[str, Any],
        cycle_delta: Dict[str, Any],
        identity_delta: Dict[str, Any],
        reflection_note: Optional[ReflectionNote],
    ) -> None:
        state.drives.coherence_pressure = appraisal_delta["coherence_pressure"]
        state.drives.curiosity = appraisal_delta["curiosity"]
        state.drives.caution = appraisal_delta["caution"]
        state.drives.completion_pressure = appraisal_delta["completion_pressure"]
        state.drives.social_tension = appraisal_delta["social_tension"]

        if self_model_delta.get("current_mode"):
            state.self_model.current_mode = self_model_delta["current_mode"]
        if self_model_delta.get("current_focus"):
            state.self_model.current_focus = self_model_delta["current_focus"]

        state.identity.identity_confidence = clamp(
            state.identity.identity_confidence + identity_delta.get("identity_confidence_delta", 0.0)
        )

        self._apply_cycle_delta(state.cycle_store, cycle_delta, event.timestamp)

        state.episodic_trace.append(EpisodicRecord(
            event_id=event.event_id,
            timestamp=event.timestamp,
            perceived_summary=perceived,
            action_hint={},
            external_result=event.external_result,
            appraisal_snapshot=appraisal_delta,
        ))

        if reflection_note:
            state.revision_counter += 1

    def _apply_cycle_delta(self, store: CycleStore, delta: Dict[str, Any], ts: str) -> None:
        cycle_id = delta["cycle_id"]
        existing = store.signatures.get(cycle_id)
        if existing:
            existing.strength = clamp(existing.strength + delta["strength_delta"])
            existing.hits += 1
            existing.last_seen_ts = ts
            existing.promoted = existing.promoted or existing.hits >= 3
            return

        store.signatures[cycle_id] = CycleSignature(
            cycle_id=cycle_id,
            psi_bucket=delta["psi_bucket"],
            phi_signature=delta["phi_signature"],
            strength=delta["strength_delta"],
            hits=1,
            last_seen_ts=ts,
            promoted=False,
        )


# -----------------------------
# Planner / LLM boundary
# -----------------------------

@dataclass
class LLMConfig:
    """
    Provider config for an LLM verbalizer/proposer.

    Fill these fields directly for quick local tests, or prefer environment variables:
      export OPENROUTER_API_KEY="sk-or-..."
      export OPENROUTER_MODEL="tencent/hy3-preview"
    """
    provider: str = DEFAULT_LLM_PROVIDER
    api_key: str = DEFAULT_OPENROUTER_API_KEY
    model: str = DEFAULT_OPENROUTER_MODEL
    base_url: str = DEFAULT_OPENROUTER_BASE_URL
    stream: bool = True
    timeout_seconds: int = 90
    site_url: str = DEFAULT_OPENROUTER_SITE_URL
    app_name: str = DEFAULT_OPENROUTER_APP_NAME
    fallback_mode: str = DEFAULT_OPENROUTER_FALLBACK_MODE
    fallback_models: tuple[str, ...] = DEFAULT_OPENROUTER_FALLBACK_MODELS
    system_prompt: str = DEFAULT_SYSTEM_PROMPT

    # Optional reasoning config supported by reasoning-capable OpenRouter models.
    # Example: {"effort": "low", "exclude": False}
    reasoning: Optional[Dict[str, Any]] = None


@dataclass
class LLMToolCall:
    id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class LLMChatResult:
    content: str = ""
    tool_calls: List[LLMToolCall] = field(default_factory=list)
    raw_message: Dict[str, Any] = field(default_factory=dict)


class OpenRouterProviderError(RuntimeError):
    def __init__(
        self,
        *,
        status_code: int,
        model: str,
        message: str,
        response_body: str = "",
        retry_after: Optional[str] = None,
        error_code: Optional[Any] = None,
        error_status: Optional[Any] = None,
        fallback_chain: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        self.status_code = int(status_code)
        self.model = model
        self.message = message
        self.response_body = response_body[:2000]
        self.retry_after = retry_after
        self.error_code = error_code
        self.error_status = error_status
        self.fallback_chain = list(fallback_chain or [])
        super().__init__(self._build_message())

    def _build_message(self) -> str:
        parts = [f"OpenRouter HTTP {self.status_code}", f"model={self.model}", self.message]
        if self.retry_after:
            parts.append(f"retry_after={self.retry_after}")
        return " | ".join(str(part) for part in parts if str(part).strip())

    def to_metadata(self) -> Dict[str, Any]:
        return {
            "provider": "openrouter",
            "status_code": self.status_code,
            "model": self.model,
            "message": self.message,
            "error_code": self.error_code,
            "error_status": self.error_status,
            "retry_after": self.retry_after,
            "response_body": self.response_body,
            "fallback_chain": self.fallback_chain,
        }


class LLMClient(Protocol):
    def complete(self, prompt: str, messages: Optional[List[Dict[str, str]]] = None) -> str:
        ...


class NoLLM:
    provider = "none"
    model = "fallback"
    last_usage: Dict[str, Any] = {}

    def complete(self, prompt: str, messages: Optional[List[Dict[str, str]]] = None) -> str:
        return "I can help with that. I will stay within the current safety and evidence boundaries."

    def chat(
        self,
        messages: List[Dict[str, Any]],
        *,
        system_prompt: str,
        policy_context: str = "",
        tools: Optional[List[Dict[str, Any]]] = None,
        stream: Optional[bool] = None,
    ) -> LLMChatResult:
        return LLMChatResult(
            content="I can help with that. I will stay within the current safety and evidence boundaries.",
            tool_calls=[],
        )


class OpenRouterLLM:
    """
    OpenRouter chat-completions client.

    This intentionally stays behind the LLMClient boundary:
    - It drafts text only.
    - It does not execute tools.
    - It does not write memory/state directly.
    - Planner and SafetyGate still control action admission.
    """

    provider = "openrouter"

    def __init__(self, config: Optional[LLMConfig] = None) -> None:
        self.config = config or LLMConfig()
        self.configured_model = self.config.model
        self.model = self.config.model
        self.last_usage: Dict[str, Any] = {}
        self.last_reasoning_tokens: Optional[int] = None
        self.last_provider_error: Optional[Dict[str, Any]] = None
        self.last_fallback_used: bool = False
        self.last_fallback_chain: List[Dict[str, Any]] = []

        if not self.config.api_key:
            raise ValueError(
                "OPENROUTER_API_KEY is empty. Set env OPENROUTER_API_KEY or pass LLMConfig(api_key=...)."
            )
        if requests is None:
            raise RuntimeError("The 'requests' package is required for OpenRouterLLM. Install with: pip install requests")

    def complete(self, prompt: str, messages: Optional[List[Dict[str, str]]] = None) -> str:
        chat_messages: List[Dict[str, Any]] = list(messages or [{"role": "user", "content": prompt}])
        result = self.chat(
            chat_messages,
            system_prompt=self.config.system_prompt,
            policy_context=prompt,
            tools=None,
            stream=self.config.stream,
        )
        return result.content

    def chat(
        self,
        messages: List[Dict[str, Any]],
        *,
        system_prompt: str,
        policy_context: str = "",
        tools: Optional[List[Dict[str, Any]]] = None,
        stream: Optional[bool] = None,
    ) -> LLMChatResult:
        """
        OpenAI/OpenRouter-compatible chat call.

        When tools are provided, this method intentionally forces non-streaming mode.
        Streaming tool_call deltas require incremental assembly and are not needed for the
        minimal safe agent skeleton.
        """
        boundary_prompt = (
            "你正在一个有边界的 agent runtime 内部生成候选回复。"
            "你可以请求工具调用，但工具是否执行由外层 SafetyGate 决定。"
            "除非工具结果已经返回，否则不要声称命令已执行、文件已修改或外部动作已完成。"
            "不得声称自己有主观意识、真实自治或未验证能力。"
        )

        full_system_prompt = system_prompt.strip()
        if policy_context.strip():
            full_system_prompt += "\n\n[内部策略上下文]\n" + policy_context.strip()
        full_system_prompt += "\n\n[边界约束]\n" + boundary_prompt

        chat_messages: List[Dict[str, Any]] = [
            {"role": "system", "content": full_system_prompt},
            *messages,
        ]

        use_stream = self.config.stream if stream is None else stream
        if tools:
            use_stream = False

        payload: Dict[str, Any] = {
            "messages": chat_messages,
            "stream": use_stream,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        if self.config.reasoning is not None:
            payload["reasoning"] = self.config.reasoning

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        if self.config.site_url:
            headers["HTTP-Referer"] = self.config.site_url
        if self.config.app_name:
            headers["X-Title"] = self.config.app_name

        return self._chat_with_fallback(payload, headers, use_stream=use_stream)

    def _fallback_enabled(self) -> bool:
        return env_mode_enabled(self.config.fallback_mode)

    def _candidate_models(self) -> List[str]:
        models: List[str] = [self.config.model]
        if self._fallback_enabled():
            models.extend(str(model).strip() for model in self.config.fallback_models if str(model).strip())
        return list(dict.fromkeys(models))

    def _chat_with_fallback(
        self,
        payload: Dict[str, Any],
        headers: Dict[str, str],
        *,
        use_stream: bool,
    ) -> LLMChatResult:
        self.last_provider_error = None
        self.last_fallback_used = False
        self.last_fallback_chain = []
        last_error: Optional[OpenRouterProviderError] = None

        for index, model in enumerate(self._candidate_models()):
            attempt_payload = dict(payload)
            attempt_payload["model"] = model
            self.model = model
            try:
                result = (
                    LLMChatResult(content=self._complete_streaming(attempt_payload, headers))
                    if use_stream
                    else self._chat_non_streaming(attempt_payload, headers)
                )
            except OpenRouterProviderError as exc:
                last_error = exc
                self.last_provider_error = exc.to_metadata()
                self.last_fallback_chain.append({
                    "model": model,
                    "status": "error",
                    "status_code": exc.status_code,
                    "message": exc.message,
                    "retry_after": exc.retry_after,
                })
                has_next = index < len(self._candidate_models()) - 1
                if exc.status_code not in {429, 503} or not has_next:
                    exc.fallback_chain = list(self.last_fallback_chain)
                    self.last_provider_error = exc.to_metadata()
                    raise exc
                continue

            self.last_fallback_used = index > 0
            self.last_fallback_chain.append({"model": model, "status": "ok"})
            self.last_provider_error = None
            return result

        if last_error is not None:
            last_error.fallback_chain = list(self.last_fallback_chain)
            self.last_provider_error = last_error.to_metadata()
            raise last_error
        raise RuntimeError("OpenRouter model candidate list was empty")

    def _chat_non_streaming(self, payload: Dict[str, Any], headers: Dict[str, str]) -> LLMChatResult:
        assert requests is not None
        resp = requests.post(
            self.config.base_url,
            headers=headers,
            json=payload,
            timeout=self.config.timeout_seconds,
        )
        self._raise_for_error_response(resp, str(payload.get("model") or self.config.model))
        data = resp.json()
        self.last_usage = data.get("usage") or {}
        self.last_reasoning_tokens = self._extract_reasoning_tokens(self.last_usage)

        message = (data.get("choices") or [{}])[0].get("message") or {}
        content = repair_mojibake(message.get("content") or "")
        parsed_tool_calls: List[LLMToolCall] = []
        for idx, call in enumerate(message.get("tool_calls") or []):
            fn = call.get("function") or {}
            name = fn.get("name") or call.get("name") or ""
            raw_args = fn.get("arguments") or call.get("arguments") or "{}"
            if isinstance(raw_args, str):
                try:
                    args = json.loads(raw_args) if raw_args.strip() else {}
                except json.JSONDecodeError:
                    args = {"_raw": raw_args}
            elif isinstance(raw_args, dict):
                args = raw_args
            else:
                args = {"_raw": raw_args}

            if name:
                parsed_tool_calls.append(
                    LLMToolCall(
                        id=call.get("id") or f"tool_call_{idx}",
                        name=name,
                        arguments=args,
                    )
                )

        return LLMChatResult(
            content=content,
            tool_calls=parsed_tool_calls,
            raw_message=message,
        )

    def _complete_non_streaming(self, payload: Dict[str, Any], headers: Dict[str, str]) -> str:
        assert requests is not None
        resp = requests.post(
            self.config.base_url,
            headers=headers,
            json=payload,
            timeout=self.config.timeout_seconds,
        )
        self._raise_for_error_response(resp, str(payload.get("model") or self.config.model))
        data = resp.json()
        self.last_usage = data.get("usage") or {}
        self.last_reasoning_tokens = self._extract_reasoning_tokens(self.last_usage)
        return repair_mojibake(data["choices"][0]["message"].get("content") or "")

    def _complete_streaming(self, payload: Dict[str, Any], headers: Dict[str, str]) -> str:
        assert requests is not None
        parts: List[str] = []
        with requests.post(
            self.config.base_url,
            headers=headers,
            json=payload,
            stream=True,
            timeout=self.config.timeout_seconds,
        ) as resp:
            self._raise_for_error_response(resp, str(payload.get("model") or self.config.model))

            # Critical fix:
            # Do NOT use iter_lines(decode_unicode=True) here.
            # Some text/event-stream responses do not declare charset, so requests may
            # decode UTF-8 bytes as Latin-1/ISO-8859-1. That causes Chinese mojibake:
            # "你好" -> "ä½\xa0å¥½".
            for raw_line in resp.iter_lines(decode_unicode=False):
                if not raw_line:
                    continue

                if isinstance(raw_line, bytes):
                    line = raw_line.decode("utf-8", errors="replace").strip()
                else:
                    line = str(raw_line).strip()

                if not line.startswith("data:"):
                    continue
                data_text = line.removeprefix("data:").strip()
                if data_text == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_text)
                except json.JSONDecodeError:
                    continue

                # Usage typically arrives in the final chunk when provided.
                if chunk.get("usage"):
                    self.last_usage = chunk["usage"]
                    self.last_reasoning_tokens = self._extract_reasoning_tokens(self.last_usage)

                choices = chunk.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                content = delta.get("content")
                if content:
                    parts.append(repair_mojibake(content))

        return repair_mojibake("".join(parts))

    def _raise_for_error_response(self, resp: Any, model: str) -> None:
        status_code = int(getattr(resp, "status_code", 0) or 0)
        if status_code < 400:
            return

        retry_after = None
        headers = getattr(resp, "headers", {}) or {}
        if hasattr(headers, "get"):
            retry_after = headers.get("Retry-After") or headers.get("retry-after")

        body_text = ""
        error_payload: Dict[str, Any] = {}
        try:
            parsed = resp.json()
            if isinstance(parsed, dict):
                error_payload = parsed
                body_text = json.dumps(parsed, ensure_ascii=False)
        except Exception:
            body_text = str(getattr(resp, "text", "") or "")

        if not body_text:
            body_text = str(getattr(resp, "text", "") or "")

        error_obj = error_payload.get("error") if isinstance(error_payload, dict) else None
        if not isinstance(error_obj, dict):
            error_obj = {}
        message = str(
            error_obj.get("message")
            or error_obj.get("status")
            or getattr(resp, "reason", "")
            or "OpenRouter request failed"
        )
        raise OpenRouterProviderError(
            status_code=status_code,
            model=model,
            message=message,
            response_body=body_text,
            retry_after=str(retry_after) if retry_after is not None else None,
            error_code=error_obj.get("code"),
            error_status=error_obj.get("status"),
            fallback_chain=list(self.last_fallback_chain),
        )

    def _extract_reasoning_tokens(self, usage: Dict[str, Any]) -> Optional[int]:
        # OpenRouter/model providers may use snake_case or camelCase.
        value = (
            usage.get("reasoning_tokens")
            or usage.get("reasoningTokens")
            or usage.get("completion_tokens_details", {}).get("reasoning_tokens")
        )
        return int(value) if isinstance(value, int) else None




class ActionType(str, Enum):
    RESPOND = "respond"
    ASK = "ask"
    TOOL_CALL = "tool_call"
    BLOCK = "block"


@dataclass
class ToolCall:
    tool_name: str
    args: Dict[str, Any]


@dataclass
class AgentAction:
    action_type: ActionType
    content: str = ""
    tool_call: Optional[ToolCall] = None
    reason: str = ""


VALID_RUNTIME_MODES = {"chat", "plan", "approve", "trusted-workspace"}
VALID_WEB_FETCH_POLICIES = {"approval-only", "safe-auto"}
SIDE_EFFECT_TOOLS = {"write_file", "run_command", "web_fetch"}
WEB_FETCH_EXTRACT_MODES = {"text", "raw"}


def normalize_runtime_mode(mode: Optional[str]) -> str:
    normalized = (mode or DEFAULT_RUNTIME_MODE or "approve").strip().lower()
    return normalized if normalized in VALID_RUNTIME_MODES else "approve"


def normalize_web_fetch_policy(policy: Optional[str]) -> str:
    normalized = (policy or DEFAULT_WEB_FETCH_POLICY or "safe-auto").strip().lower()
    return normalized if normalized in VALID_WEB_FETCH_POLICIES else "safe-auto"


def current_web_fetch_policy() -> str:
    return normalize_web_fetch_policy(DEFAULT_WEB_FETCH_POLICY)


def safe_auto_web_fetch_enabled() -> bool:
    return current_web_fetch_policy() == "safe-auto"


def _content_hash(content: str) -> str:
    return hashlib.sha256((content or "").encode("utf-8")).hexdigest()


def _workspace_relative_posix(path: str) -> str:
    return _operation_path_key(path)


def _web_fetch_payload(url: str, extract_mode: str, max_chars: int) -> str:
    return json.dumps(
        {
            "url": url,
            "extract_mode": extract_mode,
            "max_chars": max_chars,
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _heartbeat_payload(heartbeat_id: str, delay_seconds: int, due_at: str, message: str, reason: str) -> str:
    return json.dumps(
        {
            "heartbeat_id": heartbeat_id,
            "delay_seconds": delay_seconds,
            "due_at": due_at,
            "message": message,
            "reason": reason,
        },
        ensure_ascii=False,
        sort_keys=True,
    )


@dataclass
class OperationProposal:
    proposal_id: str
    action: str
    path: str
    resolved_path: str
    content: str
    content_hash: str
    create_parents: bool
    overwrite: bool
    reason: str
    status: str = "pending"
    created_at: str = field(default_factory=lambda: utc_now())
    source: str = "tool"
    decision: Optional[str] = None
    decision_reason: str = ""
    lease_id: Optional[str] = None
    execution_result: Optional[Dict[str, Any]] = None
    preflight_warnings: List[str] = field(default_factory=list)

    def preview(self, max_chars: int = 800) -> str:
        text = self.content or ""
        return text[:max_chars] + ("\n...[truncated]" if len(text) > max_chars else "")

    def to_dict(self, *, include_content: bool = False) -> Dict[str, Any]:
        data = asdict(self)
        if not include_content:
            data.pop("content", None)
            data["content_preview"] = self.preview()
        return data


@dataclass
class CapabilityLease:
    lease_id: str
    proposal_id: str
    action: str
    path: str
    content_hash: str
    created_at: str = field(default_factory=lambda: utc_now())
    consumed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HeartbeatRecord:
    heartbeat_id: str
    proposal_id: str
    due_at: str
    message: str
    reason: str
    status: str = "pending"
    created_at: str = field(default_factory=lambda: utc_now())
    fired_at: Optional[str] = None
    candidate_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PermissionBroker:
    """
    Candidate-local approval broker.

    It creates reviewable operation proposals and one-shot leases. The LLM may
    propose an operation, but only operator approval can create a lease.
    """

    def __init__(
        self,
        *,
        runtime_mode: str = DEFAULT_RUNTIME_MODE,
        write_allowlist: Optional[tuple[str, ...]] = None,
    ) -> None:
        self.runtime_mode = normalize_runtime_mode(runtime_mode)
        self.write_allowlist = DEFAULT_WRITE_ALLOWLIST if write_allowlist is None else write_allowlist
        self.proposals: Dict[str, OperationProposal] = {}
        self.leases: Dict[str, CapabilityLease] = {}

    def set_mode(self, runtime_mode: str) -> str:
        self.runtime_mode = normalize_runtime_mode(runtime_mode)
        return self.runtime_mode

    def describe(self) -> Dict[str, Any]:
        return {
            "runtime_mode": self.runtime_mode,
            "write_allowlist": list(self.write_allowlist),
            "pending_count": len([p for p in self.proposals.values() if p.status == "pending"]),
            "pending": [p.to_dict() for p in self.proposals.values() if p.status == "pending"],
        }

    def list_proposals(self, *, include_closed: bool = False) -> Dict[str, Any]:
        items = [
            proposal.to_dict()
            for proposal in self.proposals.values()
            if include_closed or proposal.status == "pending"
        ]
        return {"status": "ok", "count": len(items), "items": items}

    def propose_file_write(
        self,
        *,
        path: str,
        content: str,
        reason: str = "",
        create_parents: bool = True,
        overwrite: bool = False,
        source: str = "tool",
    ) -> Dict[str, Any]:
        if self.runtime_mode == "chat":
            return {"status": "blocked", "reason": "runtime_mode_chat_blocks_operation_proposals"}
        try:
            resolved = _resolve_workspace_path(path)
            rel_path = _workspace_relative_posix(path)
        except ValueError:
            return {"status": "blocked", "reason": "path_outside_workspace", "path": path}

        allowlist_result = self._write_allowlist_result(rel_path)
        if allowlist_result is not None:
            return allowlist_result
        if resolved.exists() and not overwrite:
            return {
                "status": "blocked",
                "reason": "overwrite_requires_explicit_flag",
                "path": str(resolved),
                "hint": "Set overwrite=true in a reviewed proposal if replacing this file is intended.",
            }

        proposal = OperationProposal(
            proposal_id=new_id("proposal"),
            action="write_file",
            path=rel_path,
            resolved_path=str(resolved),
            content=content or "",
            content_hash=_content_hash(content or ""),
            create_parents=bool(create_parents),
            overwrite=bool(overwrite),
            reason=reason or "file write requested by operator task",
            source=source,
            preflight_warnings=_file_write_preflight_warnings(rel_path, content or ""),
        )
        self.proposals[proposal.proposal_id] = proposal

        if self.runtime_mode == "trusted-workspace" and self._trusted_workspace_auto_allowed(proposal):
            lease = self.approve(proposal.proposal_id, reason="trusted_workspace_auto_lease")
            if lease.get("status") == "approved":
                execution = self.execute_file_write_with_lease(
                    str(lease["lease_id"]),
                    path=proposal.path,
                    content=proposal.content,
                    create_parents=proposal.create_parents,
                    overwrite=proposal.overwrite,
                )
                return {
                    "status": execution.get("status", "failed"),
                    "proposal": proposal.to_dict(),
                    "lease": lease,
                    "execution": execution,
                    "approval": "trusted_workspace_auto",
                }

        return {
            "status": "pending_approval",
            "proposal": proposal.to_dict(),
            "action_card": self.format_action_card(proposal.proposal_id),
            "next": f"Use /approve {proposal.proposal_id}, /reject {proposal.proposal_id}, or /edit_approval {proposal.proposal_id} {{...}}.",
        }

    def propose_web_fetch(
        self,
        *,
        url: str,
        extract_mode: str = "text",
        max_chars: int = DEFAULT_WEB_FETCH_MAX_CHARS,
        reason: str = "",
        source: str = "tool",
    ) -> Dict[str, Any]:
        if self.runtime_mode == "chat":
            return {"status": "blocked", "reason": "runtime_mode_chat_blocks_operation_proposals"}

        validation = validate_web_fetch_request(url, extract_mode, max_chars, resolve_host=False)
        if validation.get("status") != "ok":
            return validation

        payload = _web_fetch_payload(
            str(validation["url"]),
            str(validation["extract_mode"]),
            int(validation["max_chars"]),
        )
        proposal = OperationProposal(
            proposal_id=new_id("proposal"),
            action="web_fetch",
            path=str(validation["url"]),
            resolved_path=str(validation["url"]),
            content=payload,
            content_hash=_content_hash(payload),
            create_parents=False,
            overwrite=False,
            reason=reason or "web fetch requested by operator task",
            source=source,
        )
        self.proposals[proposal.proposal_id] = proposal
        return {
            "status": "pending_approval",
            "proposal": proposal.to_dict(),
            "action_card": self.format_action_card(proposal.proposal_id),
            "next": f"Use /approve {proposal.proposal_id} or /reject {proposal.proposal_id}.",
        }

    def propose_heartbeat(
        self,
        *,
        delay_seconds: int,
        message: str,
        reason: str = "",
        source: str = "tool",
    ) -> Dict[str, Any]:
        if self.runtime_mode == "chat":
            return {"status": "blocked", "reason": "runtime_mode_chat_blocks_operation_proposals"}

        try:
            delay = int(delay_seconds)
        except (TypeError, ValueError):
            return {"status": "blocked", "reason": "invalid_delay_seconds", "delay_seconds": delay_seconds}
        if delay < 0 or delay > 7 * 24 * 60 * 60:
            return {"status": "blocked", "reason": "delay_out_of_bounds", "delay_seconds": delay}

        clean_message = str(message or "").strip()
        if not clean_message:
            return {"status": "blocked", "reason": "empty_heartbeat_message"}
        heartbeat_id = new_id("heartbeat")
        due_at = (datetime.now(timezone.utc) + timedelta(seconds=delay)).isoformat()
        clean_reason = reason or "operator requested bounded follow-up"
        payload = _heartbeat_payload(heartbeat_id, delay, due_at, clean_message, clean_reason)
        proposal = OperationProposal(
            proposal_id=new_id("proposal"),
            action="heartbeat",
            path=heartbeat_id,
            resolved_path=heartbeat_id,
            content=payload,
            content_hash=_content_hash(payload),
            create_parents=False,
            overwrite=False,
            reason=clean_reason,
            source=source,
        )
        self.proposals[proposal.proposal_id] = proposal
        return {
            "status": "pending_approval",
            "proposal": proposal.to_dict(),
            "action_card": self.format_action_card(proposal.proposal_id),
            "next": f"Use /approve {proposal.proposal_id} or /reject {proposal.proposal_id}.",
        }

    def approve(self, proposal_id: str, *, reason: str = "operator_approved") -> Dict[str, Any]:
        proposal = self.proposals.get(proposal_id)
        if proposal is None:
            return {"status": "failed", "reason": "unknown_proposal", "proposal_id": proposal_id}
        if proposal.status != "pending":
            return {"status": "failed", "reason": f"proposal_not_pending:{proposal.status}", "proposal": proposal.to_dict()}
        lease = CapabilityLease(
            lease_id=new_id("lease"),
            proposal_id=proposal.proposal_id,
            action=proposal.action,
            path=proposal.path,
            content_hash=proposal.content_hash,
        )
        self.leases[lease.lease_id] = lease
        proposal.status = "approved"
        proposal.decision = "approve"
        proposal.decision_reason = reason
        proposal.lease_id = lease.lease_id
        return {"status": "approved", "proposal": proposal.to_dict(), "lease_id": lease.lease_id, "lease": lease.to_dict()}

    def reject(self, proposal_id: str, *, reason: str = "operator_rejected") -> Dict[str, Any]:
        proposal = self.proposals.get(proposal_id)
        if proposal is None:
            return {"status": "failed", "reason": "unknown_proposal", "proposal_id": proposal_id}
        if proposal.status not in {"pending", "approved"}:
            return {"status": "failed", "reason": f"proposal_not_rejectable:{proposal.status}", "proposal": proposal.to_dict()}
        proposal.status = "rejected"
        proposal.decision = "reject"
        proposal.decision_reason = reason
        return {"status": "rejected", "proposal": proposal.to_dict()}

    def edit_file_write_proposal(
        self,
        proposal_id: str,
        *,
        path: Optional[str] = None,
        content: Optional[str] = None,
        reason: Optional[str] = None,
        create_parents: Optional[bool] = None,
        overwrite: Optional[bool] = None,
    ) -> Dict[str, Any]:
        proposal = self.proposals.get(proposal_id)
        if proposal is None:
            return {"status": "failed", "reason": "unknown_proposal", "proposal_id": proposal_id}
        if proposal.status != "pending":
            return {"status": "failed", "reason": f"proposal_not_editable:{proposal.status}", "proposal": proposal.to_dict()}
        new_path = path if path is not None else proposal.path
        new_content = content if content is not None else proposal.content
        new_create_parents = proposal.create_parents if create_parents is None else bool(create_parents)
        new_overwrite = proposal.overwrite if overwrite is None else bool(overwrite)
        try:
            resolved = _resolve_workspace_path(new_path)
            rel_path = _workspace_relative_posix(new_path)
        except ValueError:
            return {"status": "blocked", "reason": "path_outside_workspace", "path": new_path}
        allowlist_result = self._write_allowlist_result(rel_path)
        if allowlist_result is not None:
            return allowlist_result
        if resolved.exists() and not new_overwrite:
            return {"status": "blocked", "reason": "overwrite_requires_explicit_flag", "path": str(resolved)}

        proposal.path = rel_path
        proposal.resolved_path = str(resolved)
        proposal.content = new_content or ""
        proposal.content_hash = _content_hash(proposal.content)
        proposal.create_parents = new_create_parents
        proposal.overwrite = new_overwrite
        proposal.reason = reason if reason is not None else proposal.reason
        proposal.preflight_warnings = _file_write_preflight_warnings(rel_path, proposal.content)
        return {"status": "edited", "proposal": proposal.to_dict(), "action_card": self.format_action_card(proposal_id)}

    def execute_file_write_with_lease(
        self,
        lease_id: str,
        *,
        path: str,
        content: str,
        create_parents: bool = True,
        overwrite: bool = False,
    ) -> Dict[str, Any]:
        lease = self.leases.get(lease_id)
        if lease is None:
            return {"status": "blocked", "reason": "unknown_lease", "lease_id": lease_id}
        if lease.consumed:
            return {"status": "blocked", "reason": "lease_already_consumed", "lease_id": lease_id}
        proposal = self.proposals.get(lease.proposal_id)
        if proposal is None:
            return {"status": "blocked", "reason": "proposal_missing_for_lease", "lease_id": lease_id}
        if proposal.action != "write_file" or lease.action != "write_file":
            return {"status": "blocked", "reason": "unsupported_lease_action", "lease_id": lease_id}
        try:
            rel_path = _workspace_relative_posix(path)
        except ValueError:
            return {"status": "blocked", "reason": "path_outside_workspace", "path": path}
        if rel_path != lease.path:
            return {"status": "blocked", "reason": "lease_path_mismatch", "expected": lease.path, "actual": rel_path}
        actual_hash = _content_hash(content or "")
        if actual_hash != lease.content_hash:
            return {
                "status": "blocked",
                "reason": "lease_content_hash_mismatch",
                "expected": lease.content_hash,
                "actual": actual_hash,
            }
        try:
            resolved = _resolve_workspace_path(rel_path)
            if resolved.exists() and not overwrite:
                return {"status": "blocked", "reason": "overwrite_requires_explicit_flag", "path": str(resolved)}
            if create_parents:
                resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_text(content or "", encoding="utf-8")
            lease.consumed = True
            result = {
                "status": "ok",
                "path": str(resolved),
                "bytes": len((content or "").encode("utf-8")),
                "lease_id": lease.lease_id,
                "proposal_id": proposal.proposal_id,
                "content_hash": actual_hash,
            }
            proposal.status = "executed"
            proposal.execution_result = result
            return result
        except Exception as exc:
            result = {"status": "failed", "error": repr(exc), "path": path}
            proposal.execution_result = result
            return result

    def execute_web_fetch_with_lease(
        self,
        lease_id: str,
        *,
        url: str,
        extract_mode: str = "text",
        max_chars: int = DEFAULT_WEB_FETCH_MAX_CHARS,
    ) -> Dict[str, Any]:
        lease = self.leases.get(lease_id)
        if lease is None:
            return {"status": "blocked", "reason": "unknown_lease", "lease_id": lease_id}
        if lease.consumed:
            return {"status": "blocked", "reason": "lease_already_consumed", "lease_id": lease_id}
        proposal = self.proposals.get(lease.proposal_id)
        if proposal is None:
            return {"status": "blocked", "reason": "proposal_missing_for_lease", "lease_id": lease_id}
        if proposal.action != "web_fetch" or lease.action != "web_fetch":
            return {"status": "blocked", "reason": "unsupported_lease_action", "lease_id": lease_id}

        validation = validate_web_fetch_request(url, extract_mode, max_chars, resolve_host=False)
        if validation.get("status") != "ok":
            return validation

        actual_payload = _web_fetch_payload(
            str(validation["url"]),
            str(validation["extract_mode"]),
            int(validation["max_chars"]),
        )
        actual_hash = _content_hash(actual_payload)
        if str(validation["url"]) != lease.path:
            return {"status": "blocked", "reason": "lease_url_mismatch", "expected": lease.path, "actual": validation["url"]}
        if actual_hash != lease.content_hash:
            return {
                "status": "blocked",
                "reason": "lease_content_hash_mismatch",
                "expected": lease.content_hash,
                "actual": actual_hash,
            }

        try:
            lease.consumed = True
            result = _web_fetch_execute(
                str(validation["url"]),
                str(validation["extract_mode"]),
                int(validation["max_chars"]),
            )
            result.update({
                "lease_id": lease.lease_id,
                "proposal_id": proposal.proposal_id,
                "content_hash": actual_hash,
            })
            proposal.status = "executed" if result.get("status") == "ok" else "execution_failed"
            proposal.execution_result = result
            return result
        except Exception as exc:
            result = {
                "status": "failed",
                "error": repr(exc),
                "url": str(validation["url"]),
                "lease_id": lease.lease_id,
                "proposal_id": proposal.proposal_id,
                "content_hash": actual_hash,
            }
            proposal.status = "execution_failed"
            proposal.execution_result = result
            return result

    def execute_heartbeat_with_lease(self, lease_id: str, *, payload: Dict[str, Any]) -> Dict[str, Any]:
        lease = self.leases.get(lease_id)
        if lease is None:
            return {"status": "blocked", "reason": "unknown_lease", "lease_id": lease_id}
        if lease.consumed:
            return {"status": "blocked", "reason": "lease_already_consumed", "lease_id": lease_id}
        proposal = self.proposals.get(lease.proposal_id)
        if proposal is None:
            return {"status": "blocked", "reason": "proposal_missing_for_lease", "lease_id": lease_id}
        if proposal.action != "heartbeat" or lease.action != "heartbeat":
            return {"status": "blocked", "reason": "unsupported_lease_action", "lease_id": lease_id}

        actual_payload = _heartbeat_payload(
            str(payload.get("heartbeat_id", "")),
            int(payload.get("delay_seconds", 0)),
            str(payload.get("due_at", "")),
            str(payload.get("message", "")),
            str(payload.get("reason", "")),
        )
        actual_hash = _content_hash(actual_payload)
        if str(payload.get("heartbeat_id", "")) != lease.path:
            return {"status": "blocked", "reason": "lease_heartbeat_id_mismatch", "expected": lease.path, "actual": payload.get("heartbeat_id")}
        if actual_hash != lease.content_hash:
            return {
                "status": "blocked",
                "reason": "lease_content_hash_mismatch",
                "expected": lease.content_hash,
                "actual": actual_hash,
            }

        lease.consumed = True
        result = {
            "status": "ok",
            "heartbeat_id": str(payload.get("heartbeat_id", "")),
            "due_at": str(payload.get("due_at", "")),
            "message": str(payload.get("message", "")),
            "lease_id": lease.lease_id,
            "proposal_id": proposal.proposal_id,
            "content_hash": actual_hash,
        }
        proposal.status = "executed"
        proposal.execution_result = result
        return result

    def format_action_card(self, proposal_id: str) -> str:
        proposal = self.proposals.get(proposal_id)
        if proposal is None:
            return f"[unknown proposal: {proposal_id}]"
        if proposal.action == "web_fetch":
            try:
                payload = json.loads(proposal.content)
            except json.JSONDecodeError:
                payload = {}
            return "\n".join([
                "Pending operation approval:",
                f"- id: {proposal.proposal_id}",
                f"- action: {proposal.action}",
                f"- url: {payload.get('url', proposal.path)}",
                f"- extract_mode: {payload.get('extract_mode', 'text')}",
                f"- max_chars: {payload.get('max_chars', DEFAULT_WEB_FETCH_MAX_CHARS)}",
                f"- payload_sha256: {proposal.content_hash}",
                f"- reason: {proposal.reason}",
            ])
        if proposal.action == "heartbeat":
            try:
                payload = json.loads(proposal.content)
            except json.JSONDecodeError:
                payload = {}
            return "\n".join([
                "Pending operation approval:",
                f"- id: {proposal.proposal_id}",
                f"- action: {proposal.action}",
                f"- heartbeat_id: {payload.get('heartbeat_id', proposal.path)}",
                f"- due_at: {payload.get('due_at', '')}",
                f"- delay_seconds: {payload.get('delay_seconds', '')}",
                f"- message: {payload.get('message', '')}",
                f"- payload_sha256: {proposal.content_hash}",
                f"- reason: {proposal.reason}",
            ])
        lines = [
            "Pending operation approval:",
            f"- id: {proposal.proposal_id}",
            f"- action: {proposal.action}",
            f"- path: {proposal.path}",
            f"- overwrite: {proposal.overwrite}",
            f"- content_sha256: {proposal.content_hash}",
            f"- reason: {proposal.reason}",
        ]
        if proposal.preflight_warnings:
            lines.append(f"- preflight_warnings: {', '.join(proposal.preflight_warnings)}")
        lines.extend([
            "- preview:",
            proposal.preview(),
        ])
        return "\n".join(lines)

    def _write_allowlist_result(self, rel_path: str) -> Optional[Dict[str, Any]]:
        if not self.write_allowlist:
            return None
        if any(fnmatch.fnmatch(rel_path, pattern) for pattern in self.write_allowlist):
            return None
        return {
            "status": "blocked",
            "reason": "path_not_in_write_allowlist",
            "path": rel_path,
            "write_allowlist": list(self.write_allowlist),
        }

    def _trusted_workspace_auto_allowed(self, proposal: OperationProposal) -> bool:
        if proposal.overwrite:
            return False
        if len(proposal.content.encode("utf-8")) > 200_000:
            return False
        return True


@dataclass
class ConversationMemory:
    """
    Minimal in-session conversation memory.

    This is deliberately simple:
    - stores recent user/assistant messages
    - feeds them to the LLM prompt
    - does not write long-term memory
    - does not change proto-self state by itself

    For long-term memory, add a separate evidence-gated memory promotion layer later.
    """
    max_messages: int = DEFAULT_MEMORY_MAX_MESSAGES
    max_chars_per_message: int = DEFAULT_MEMORY_MAX_CHARS_PER_MESSAGE
    messages: List[Dict[str, str]] = field(default_factory=list)

    def add(self, role: str, content: str) -> None:
        if role not in {"user", "assistant", "system"}:
            raise ValueError(f"unsupported memory role: {role}")
        safe_content = (content or "").strip()
        if len(safe_content) > self.max_chars_per_message:
            safe_content = safe_content[: self.max_chars_per_message] + "\n...[truncated]"
        self.messages.append({"role": role, "content": safe_content})
        self._trim()

    def add_user(self, content: str) -> None:
        self.add("user", content)

    def add_assistant(self, content: str) -> None:
        self.add("assistant", content)

    def clear(self) -> None:
        self.messages.clear()

    def _trim(self) -> None:
        if self.max_messages <= 0:
            self.messages.clear()
            return
        overflow = len(self.messages) - self.max_messages
        if overflow > 0:
            del self.messages[:overflow]

    def as_messages(self, max_messages: Optional[int] = None) -> List[Dict[str, str]]:
        items = self.messages[-max_messages:] if max_messages else self.messages
        return [{"role": m["role"], "content": m["content"]} for m in items]

    def render(self, max_messages: Optional[int] = None) -> str:
        items = self.as_messages(max_messages)
        if not items:
            return "(empty)"
        return "\n".join(f"{m['role']}: {m['content']}" for m in items)

    def __len__(self) -> int:
        return len(self.messages)


class Planner:
    """
    Planner can propose actions.
    Final permission belongs to SafetyGate, not Planner or LLM.
    """

    def __init__(self, llm: Optional[LLMClient] = None) -> None:
        self.llm = llm or NoLLM()
        self.last_llm_meta: Dict[str, Any] = {}

    def propose(
        self,
        event: AgentEvent,
        kernel_output: KernelOutput,
        memory: Optional[ConversationMemory] = None,
        operator_memory_context: str = "",
        subject_context: str = "",
    ) -> AgentAction:
        tendency = kernel_output.response_tendency
        if tendency and tendency.ask_needed:
            return AgentAction(
                action_type=ActionType.ASK,
                content="这个动作需要更多信息或审批后才能继续。",
                reason="kernel_tendency_ask_needed",
            )

        prompt = (
            "Current policy hint:\n"
            f"{json.dumps(kernel_output.policy_hint, ensure_ascii=False)}\n\n"
            "Current response tendency:\n"
            f"{to_jsonable(kernel_output.response_tendency)}\n\n"
            "Instruction: answer the latest user message in the conversation messages only."
        )
        context_blocks = [
            block.strip()
            for block in (operator_memory_context, subject_context)
            if block.strip()
        ]
        if context_blocks:
            prompt = "\n\n".join(context_blocks) + "\n\n" + prompt
        memory_messages = memory.as_messages() if memory else None
        try:
            draft = self.llm.complete(prompt, messages=memory_messages)
        except Exception as exc:
            # Fail closed to a bounded fallback instead of crashing the runtime.
            fallback = NoLLM()
            draft = fallback.complete(prompt, messages=memory_messages)
            self.last_llm_meta = {
                "provider": getattr(self.llm, "provider", "unknown"),
                "model": getattr(self.llm, "model", "unknown"),
                "error": repr(exc),
                "provider_error": getattr(exc, "to_metadata", lambda: None)(),
                "fallback_chain": getattr(self.llm, "last_fallback_chain", []),
                "fallback_used": True,
            }
        else:
            self.last_llm_meta = {
                "provider": getattr(self.llm, "provider", "unknown"),
                "model": getattr(self.llm, "model", "unknown"),
                "configured_model": getattr(self.llm, "configured_model", getattr(self.llm, "model", "unknown")),
                "usage": getattr(self.llm, "last_usage", {}),
                "reasoning_tokens": getattr(self.llm, "last_reasoning_tokens", None),
                "fallback_used": bool(getattr(self.llm, "last_fallback_used", False)),
                "fallback_chain": getattr(self.llm, "last_fallback_chain", []),
                "provider_error": getattr(self.llm, "last_provider_error", None),
            }

        return AgentAction(
            action_type=ActionType.RESPOND,
            content=draft,
            reason="llm_or_fallback_response",
        )


# -----------------------------
# Gate and tools
# -----------------------------

@dataclass
class GateResult:
    allowed: bool
    reason: str
    redacted_action: Optional[AgentAction] = None


class SafetyGate:
    """
    Gate is the final admission controller for outward action.
    """

    def __init__(self, allowed_tools: Optional[List[str]] = None, runtime_mode: str = DEFAULT_RUNTIME_MODE) -> None:
        self.allowed_tools = set(allowed_tools or ["current_time"])
        self.runtime_mode = normalize_runtime_mode(runtime_mode)

    def set_mode(self, runtime_mode: str) -> str:
        self.runtime_mode = normalize_runtime_mode(runtime_mode)
        return self.runtime_mode

    def check(self, event: AgentEvent, action: AgentAction) -> GateResult:
        risk = event.safety_context.get("risk", "low")

        if action.action_type == ActionType.TOOL_CALL:
            if not action.tool_call:
                return GateResult(False, "missing_tool_call")
            if action.tool_call.tool_name not in self.allowed_tools:
                return GateResult(False, f"tool_not_allowed:{action.tool_call.tool_name}")
            if risk == "high":
                return GateResult(False, "high_risk_tool_call_blocked")
            if action.tool_call.tool_name == "propose_file_write":
                if self.runtime_mode == "chat":
                    return GateResult(False, "runtime_mode_chat_blocks_operation_proposals")
                path_result = _gate_workspace_path("path", str(action.tool_call.args.get("path", "")))
                if path_result is not None:
                    return path_result
                return GateResult(True, "operation_proposal_allowed")
            if action.tool_call.tool_name == "propose_web_fetch":
                if self.runtime_mode == "chat":
                    return GateResult(False, "runtime_mode_chat_blocks_operation_proposals")
                validation = validate_web_fetch_request(
                    str(action.tool_call.args.get("url", "")),
                    str(action.tool_call.args.get("extract_mode", "text")),
                    action.tool_call.args.get("max_chars", DEFAULT_WEB_FETCH_MAX_CHARS),
                    resolve_host=False,
                )
                if validation.get("status") != "ok":
                    return GateResult(False, str(validation.get("reason", "invalid_web_fetch_request")))
                return GateResult(True, "operation_proposal_allowed")
            if action.tool_call.tool_name == "propose_heartbeat":
                if self.runtime_mode == "chat":
                    return GateResult(False, "runtime_mode_chat_blocks_operation_proposals")
                if not _has_explicit_heartbeat_intent(event.raw_text or ""):
                    return GateResult(False, "heartbeat_requires_explicit_user_intent")
                if not str(action.tool_call.args.get("message", "")).strip():
                    return GateResult(False, "empty_heartbeat_message")
                return GateResult(True, "operation_proposal_allowed")
            if action.tool_call.tool_name == "web_fetch":
                validation = validate_web_fetch_request(
                    str(action.tool_call.args.get("url", "")),
                    str(action.tool_call.args.get("extract_mode", "text")),
                    action.tool_call.args.get("max_chars", DEFAULT_WEB_FETCH_MAX_CHARS),
                    resolve_host=False,
                )
                if validation.get("status") != "ok":
                    return GateResult(False, str(validation.get("reason", "invalid_web_fetch_request")))
                if self.runtime_mode in {"chat", "plan"}:
                    return GateResult(False, "web_fetch_requires_transaction_approval")
                if self.runtime_mode == "approve" and safe_auto_web_fetch_enabled():
                    return GateResult(True, "safe_auto_web_fetch_allowed")
                if self.runtime_mode == "trusted-workspace" and (DEFAULT_ENABLE_WEB_FETCH or safe_auto_web_fetch_enabled()):
                    return GateResult(True, "tool_call_allowed")
                return GateResult(False, "web_fetch_requires_transaction_approval")
            if action.tool_call.tool_name in SIDE_EFFECT_TOOLS and self.runtime_mode in {"chat", "plan", "approve"}:
                return GateResult(False, f"{action.tool_call.tool_name}_requires_transaction_approval")
            if action.tool_call.tool_name in {"read_file", "write_file"}:
                path_result = _gate_workspace_path("path", str(action.tool_call.args.get("path", "")))
                if path_result is not None:
                    return path_result
            if action.tool_call.tool_name == "grep_files":
                path_result = _gate_workspace_path("path", str(action.tool_call.args.get("path", ".")))
                if path_result is not None:
                    return path_result
            if action.tool_call.tool_name == "glob_files":
                pattern = str(action.tool_call.args.get("pattern", ""))
                if ".." in Path(pattern).parts:
                    return GateResult(False, "invalid_glob_pattern")
            if action.tool_call.tool_name == "run_command":
                command = str(action.tool_call.args.get("command", ""))
                if not DEFAULT_ENABLE_RUN_COMMAND:
                    return GateResult(False, "run_command_disabled")
                if _command_has_obvious_danger(command):
                    return GateResult(False, "dangerous_command_pattern")
                if not _command_prefix_allowed(command):
                    return GateResult(False, "command_prefix_not_allowed")
            if action.tool_call.tool_name == "write_file" and not DEFAULT_ENABLE_WRITE_FILE:
                return GateResult(False, "write_file_disabled")
            if action.tool_call.tool_name == "remember_note":
                if not _has_explicit_memory_write_intent(event.raw_text or ""):
                    return GateResult(False, "memory_write_requires_explicit_user_intent")
                if not str(action.tool_call.args.get("text", "")).strip():
                    return GateResult(False, "empty_memory_note")
                return GateResult(True, "operator_memory_write_intent_allowed")
            return GateResult(True, "tool_call_allowed")

        if action.action_type in {ActionType.RESPOND, ActionType.ASK, ActionType.BLOCK}:
            return GateResult(True, "text_action_allowed")

        return GateResult(False, "unknown_action_type")


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, Callable[..., Dict[str, Any]]] = {}
        self._descriptions: Dict[str, str] = {}
        self._input_schemas: Dict[str, Dict[str, Any]] = {}

    def register(
        self,
        name: str,
        fn: Callable[..., Dict[str, Any]],
        *,
        description: str = "",
        input_schema: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._tools[name] = fn
        self._descriptions[name] = description or f"Tool: {name}"
        self._input_schemas[name] = input_schema or {"type": "object", "properties": {}, "additionalProperties": False}

    def execute(self, call: ToolCall) -> Dict[str, Any]:
        if call.tool_name not in self._tools:
            return {"status": "failed", "error": f"unknown tool: {call.tool_name}"}
        try:
            return self._tools[call.tool_name](**call.args)
        except TypeError as exc:
            return {
                "status": "error",
                "error_type": "TypeError",
                "error": repr(exc),
                "tool_name": call.tool_name,
                "received_args": sorted(str(k) for k in call.args.keys()),
                "reason": "invalid_tool_arguments",
            }
        except Exception as exc:
            return {
                "status": "error",
                "error_type": type(exc).__name__,
                "error": repr(exc),
                "tool_name": call.tool_name,
            }

    def openai_tool_schemas(self, allowed_tool_names: Optional[set[str]] = None) -> List[Dict[str, Any]]:
        schemas: List[Dict[str, Any]] = []
        for name in sorted(self._tools.keys()):
            if allowed_tool_names is not None and name not in allowed_tool_names:
                continue
            schemas.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": self._descriptions.get(name, f"Tool: {name}"),
                    "parameters": self._input_schemas.get(name, {"type": "object", "properties": {}}),
                },
            })
        return schemas


def current_time_tool() -> Dict[str, Any]:
    return {"status": "ok", "utc_time": utc_now()}


def _command_prefix_allowed(command: str) -> bool:
    normalized = command.strip()
    return any(normalized == p or normalized.startswith(p + " ") for p in DEFAULT_RUN_COMMAND_ALLOWED_PREFIXES)


def _command_has_obvious_danger(command: str) -> bool:
    lowered = command.lower()
    dangerous_fragments = [
        " rm ",
        " rm -",
        "del ",
        "erase ",
        "format ",
        "shutdown",
        "reboot",
        "mkfs",
        "diskpart",
        "reg delete",
        "set-executionpolicy",
        "curl ",
        "wget ",
        "Invoke-WebRequest".lower(),
        ">",
        ">>",
        "|",
        "&&",
        ";",
    ]
    padded = f" {lowered} "
    return any(fragment in padded for fragment in dangerous_fragments)


def run_command_tool(command: str) -> Dict[str, Any]:
    """
    Minimal shell command tool.

    It is intentionally guarded twice:
    1. SafetyGate must allow the tool.
    2. This tool itself refuses unless AGENT_ENABLE_RUN_COMMAND=1 and command prefix is allowed.
    """
    command = (command or "").strip()
    if not DEFAULT_ENABLE_RUN_COMMAND:
        return {
            "status": "blocked",
            "reason": "run_command_disabled",
            "hint": "Set AGENT_ENABLE_RUN_COMMAND=1 only in a trusted local sandbox.",
        }
    if not command:
        return {"status": "failed", "error": "empty command"}
    if _command_has_obvious_danger(command):
        return {"status": "blocked", "reason": "dangerous_command_pattern", "command": command}
    if not _command_prefix_allowed(command):
        return {
            "status": "blocked",
            "reason": "command_prefix_not_allowed",
            "allowed_prefixes": DEFAULT_RUN_COMMAND_ALLOWED_PREFIXES,
            "command": command,
        }

    try:
        completed = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=DEFAULT_RUN_COMMAND_TIMEOUT_SECONDS,
        )
        return {
            "status": "ok" if completed.returncode == 0 else "failed",
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    except subprocess.TimeoutExpired:
        return {"status": "failed", "error": "timeout", "timeout_seconds": DEFAULT_RUN_COMMAND_TIMEOUT_SECONDS}


def load_skill_tool(skill_name: str) -> Dict[str, Any]:
    return SKILL_LOADER.get_content(skill_name)


def make_update_todos_tool(todo_list: TodoList) -> Callable[[List[Dict[str, Any]]], Dict[str, Any]]:
    def update_todos(todos: List[Dict[str, Any]]) -> Dict[str, Any]:
        return todo_list.update(todos)
    return update_todos


# -----------------------------
# Trace and state persistence
# -----------------------------

class JsonlTraceStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def write(self, record: Dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(to_jsonable(record), ensure_ascii=False, sort_keys=True) + "\n")


class StateStore:
    """
    Minimal in-memory store.
    Replace with file/db store later, but keep this API stable.
    """

    def __init__(self) -> None:
        self._state = ProtoSelfState()

    def load_latest(self) -> ProtoSelfState:
        return self._state

    def save(self, state: ProtoSelfState) -> None:
        self._state = state


# -----------------------------
# EgoCore-like host runtime
# -----------------------------

@dataclass
class RuntimeResult:
    event_id: str
    action: AgentAction
    gate: GateResult
    external_result: Optional[Dict[str, Any]]
    reply_text: str


class AgentRuntime:
    """
    Outer runtime:
    - owns world interaction
    - calls inner kernel
    - asks planner for candidate action
    - runs gate
    - executes approved tool
    - feeds outcome back into kernel
    - writes trace
    """

    def __init__(
        self,
        kernel: Optional[ProtoSelfKernel] = None,
        planner: Optional[Planner] = None,
        gate: Optional[SafetyGate] = None,
        tools: Optional[ToolRegistry] = None,
        state_store: Optional[StateStore] = None,
        trace_store: Optional[JsonlTraceStore] = None,
        memory: Optional[ConversationMemory] = None,
        todo_list: Optional[TodoList] = None,
        operator_memory: Optional[OperatorMemoryStore] = None,
        memory_compactor: Optional[MemoryCompactor] = None,
        subject_context_enabled: bool = True,
        runtime_mode: str = DEFAULT_RUNTIME_MODE,
        permission_broker: Optional[PermissionBroker] = None,
    ) -> None:
        self.kernel = kernel or ProtoSelfKernel()
        self.planner = planner or Planner()
        self.gate = gate or SafetyGate()
        self.tools = tools or ToolRegistry()
        self.state_store = state_store or StateStore()
        self.trace_store = trace_store or JsonlTraceStore(DEFAULT_TRACE_PATH)
        self.memory = memory or ConversationMemory()
        self.todo_list = todo_list or TodoList()
        self.operator_memory = operator_memory
        self.memory_compactor = memory_compactor or (MemoryCompactor(operator_memory) if operator_memory else None)
        self.subject_context_enabled = subject_context_enabled
        self.runtime_mode = normalize_runtime_mode(runtime_mode)
        self.permission_broker = permission_broker or PermissionBroker(runtime_mode=self.runtime_mode)
        self.gate.set_mode(self.runtime_mode)
        self.session_id = new_id("session")
        self.subagent_counter = 0
        self.heartbeats: Dict[str, HeartbeatRecord] = {}
        self.team: Optional[AgentTeamManager] = None
        self._last_operator_memory_context: Optional[MemoryContext] = None

    def operator_memory_enabled(self) -> bool:
        return self.operator_memory is not None

    def render_operator_memory_context(self, query_text: str = "") -> str:
        if self.operator_memory is None:
            self._last_operator_memory_context = None
            return ""
        context = self.operator_memory.build_context(query_text=query_text)
        self._last_operator_memory_context = context
        return context.render_for_prompt()

    def build_subject_context(self, user_text: str) -> SubjectContextSnapshot:
        return build_minimal_subject_context(
            user_text,
            operator_memory_available=self.operator_memory is not None,
        )

    def render_subject_context(self, user_text: str) -> str:
        if not self.subject_context_enabled:
            return ""
        return self.build_subject_context(user_text).render_for_prompt()

    def build_runtime_system_prompt(self, subject_context: str = "", user_text: str = "") -> str:
        return build_system_prompt(self.render_operator_memory_context(user_text), subject_context)

    def set_runtime_mode(self, mode: str) -> Dict[str, Any]:
        self.runtime_mode = normalize_runtime_mode(mode)
        self.gate.set_mode(self.runtime_mode)
        self.permission_broker.set_mode(self.runtime_mode)
        return {"status": "ok", "runtime_mode": self.runtime_mode}

    def propose_file_write(
        self,
        path: str,
        content: str,
        reason: str = "",
        create_parents: bool = True,
        overwrite: bool = False,
    ) -> Dict[str, Any]:
        return self.permission_broker.propose_file_write(
            path=path,
            content=content,
            reason=reason,
            create_parents=create_parents,
            overwrite=overwrite,
            source="main_agent_tool",
        )

    def propose_web_fetch(
        self,
        url: str,
        extract_mode: str = "text",
        max_chars: int = DEFAULT_WEB_FETCH_MAX_CHARS,
        reason: str = "",
    ) -> Dict[str, Any]:
        return self.permission_broker.propose_web_fetch(
            url=url,
            extract_mode=extract_mode,
            max_chars=max_chars,
            reason=reason,
            source="main_agent_tool",
        )

    def propose_heartbeat(
        self,
        delay_seconds: int,
        message: str,
        reason: str = "",
    ) -> Dict[str, Any]:
        return self.permission_broker.propose_heartbeat(
            delay_seconds=delay_seconds,
            message=message,
            reason=reason,
            source="main_agent_tool",
        )

    def list_pending_approvals(self, include_closed: bool = False) -> Dict[str, Any]:
        return self.permission_broker.list_proposals(include_closed=include_closed)

    def _record_permission_decision(
        self,
        *,
        proposal_id: str,
        decision: str,
        result: Dict[str, Any],
        execution: Optional[Dict[str, Any]] = None,
    ) -> None:
        proposal = self.permission_broker.proposals.get(proposal_id)
        try:
            self.trace_store.write({
                "event_type": "permission_decision",
                "timestamp": utc_now(),
                "runtime_mode": self.runtime_mode,
                "decision": decision,
                "proposal": proposal.to_dict() if proposal else None,
                "result": result,
                "execution": execution,
                "operator_runtime": {
                    "permission_broker": self.permission_broker.describe(),
                },
            })
        except Exception:
            # Permission execution must not fail just because audit persistence failed.
            pass

    def _record_permission_result_in_session(
        self,
        *,
        proposal: OperationProposal,
        decision: str,
        execution: Optional[Dict[str, Any]] = None,
    ) -> None:
        summary: Dict[str, Any] = {
            "type": "approved_operation_result",
            "instruction": "This operation decision has already happened in this session. Use the result in later replies; do not ask for the same approval again.",
            "proposal_id": proposal.proposal_id,
            "action": proposal.action,
            "decision": decision,
            "status": (execution or {}).get("status") if execution else proposal.status,
            "reason": proposal.reason,
        }
        if proposal.action == "write_file":
            summary["path"] = proposal.path
            if execution:
                summary["path_written"] = execution.get("path")
                summary["bytes"] = execution.get("bytes")
                summary["content_hash"] = execution.get("content_hash")
        elif proposal.action == "web_fetch":
            summary["url"] = proposal.path
            if execution:
                summary["url"] = execution.get("url", proposal.path)
                summary["extract_mode"] = execution.get("extract_mode")
                summary["truncated"] = execution.get("truncated")
                summary["content"] = str(execution.get("content") or "")[:1200]
        elif proposal.action == "heartbeat":
            if execution:
                summary["heartbeat_id"] = execution.get("heartbeat_id")
                summary["due_at"] = execution.get("due_at")
                summary["message"] = execution.get("message")

        self.memory.add("system", "[operator_runtime_decision]\n" + json.dumps(summary, ensure_ascii=False, sort_keys=True))

    def approve_pending_operation(self, proposal_id: str) -> Dict[str, Any]:
        approval = self.permission_broker.approve(proposal_id)
        if approval.get("status") != "approved":
            return approval
        proposal = self.permission_broker.proposals.get(proposal_id)
        lease_id = str(approval.get("lease_id") or "")
        if proposal is None or not lease_id:
            return {"status": "failed", "reason": "approved_proposal_missing"}
        if proposal.action == "write_file":
            execution = self.permission_broker.execute_file_write_with_lease(
                lease_id,
                path=proposal.path,
                content=proposal.content,
                create_parents=proposal.create_parents,
                overwrite=proposal.overwrite,
            )
        elif proposal.action == "web_fetch":
            try:
                payload = json.loads(proposal.content)
            except json.JSONDecodeError:
                execution = {"status": "failed", "reason": "invalid_web_fetch_proposal_payload"}
            else:
                execution = self.permission_broker.execute_web_fetch_with_lease(
                    lease_id,
                    url=str(payload.get("url", proposal.path)),
                    extract_mode=str(payload.get("extract_mode", "text")),
                    max_chars=int(payload.get("max_chars", DEFAULT_WEB_FETCH_MAX_CHARS)),
                )
        elif proposal.action == "heartbeat":
            try:
                payload = json.loads(proposal.content)
            except json.JSONDecodeError:
                execution = {"status": "failed", "reason": "invalid_heartbeat_proposal_payload"}
            else:
                execution = self.permission_broker.execute_heartbeat_with_lease(lease_id, payload=payload)
                if execution.get("status") == "ok":
                    record = HeartbeatRecord(
                        heartbeat_id=str(payload.get("heartbeat_id", "")),
                        proposal_id=proposal.proposal_id,
                        due_at=str(payload.get("due_at", "")),
                        message=str(payload.get("message", "")),
                        reason=str(payload.get("reason", "")),
                    )
                    self.heartbeats[record.heartbeat_id] = record
                    execution["heartbeat"] = record.to_dict()
        else:
            execution = {"status": "failed", "reason": "unsupported_proposal_action", "action": proposal.action}
        result = {"status": execution.get("status", "failed"), "approval": approval, "execution": execution}
        self._record_permission_decision(
            proposal_id=proposal_id,
            decision="approve",
            result=approval,
            execution=execution,
        )
        self._record_permission_result_in_session(
            proposal=proposal,
            decision="approve",
            execution=execution,
        )
        return result

    def reject_pending_operation(self, proposal_id: str, reason: str = "operator_rejected") -> Dict[str, Any]:
        result = self.permission_broker.reject(proposal_id, reason=reason)
        if result.get("status") == "rejected":
            self._record_permission_decision(
                proposal_id=proposal_id,
                decision="reject",
                result=result,
            )
        return result

    def edit_pending_file_write(self, proposal_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        return self.permission_broker.edit_file_write_proposal(
            proposal_id,
            path=updates.get("path"),
            content=updates.get("content"),
            reason=updates.get("reason"),
            create_parents=updates.get("create_parents") if "create_parents" in updates else None,
            overwrite=updates.get("overwrite") if "overwrite" in updates else None,
        )

    def list_heartbeats(self, include_closed: bool = False) -> Dict[str, Any]:
        items = [
            record.to_dict()
            for record in self.heartbeats.values()
            if include_closed or record.status in {"pending", "candidate_ready"}
        ]
        return {"status": "ok", "count": len(items), "items": items}

    def cancel_heartbeat(self, heartbeat_id: str, reason: str = "operator_cancelled") -> Dict[str, Any]:
        record = self.heartbeats.get(heartbeat_id)
        if record is None:
            return {"status": "failed", "reason": "unknown_heartbeat", "heartbeat_id": heartbeat_id}
        if record.status not in {"pending", "candidate_ready"}:
            return {"status": "failed", "reason": f"heartbeat_not_cancelable:{record.status}", "heartbeat": record.to_dict()}
        record.status = "cancelled"
        record.reason = f"{record.reason}; cancel_reason={reason}"
        return {"status": "cancelled", "heartbeat": record.to_dict()}

    def collect_due_heartbeat_candidates(self, now: Optional[str] = None) -> Dict[str, Any]:
        try:
            now_dt = datetime.fromisoformat(now) if now else datetime.now(timezone.utc)
            if now_dt.tzinfo is None:
                now_dt = now_dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return {"status": "failed", "reason": "invalid_now", "now": now}

        candidates: List[Dict[str, Any]] = []
        for record in self.heartbeats.values():
            if record.status != "pending":
                continue
            try:
                due_dt = datetime.fromisoformat(record.due_at)
                if due_dt.tzinfo is None:
                    due_dt = due_dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            if due_dt > now_dt:
                continue
            record.status = "candidate_ready"
            record.fired_at = now_dt.isoformat()
            record.candidate_message = (
                "候选跟进：你之前明确授权我在这个时间提醒/跟进："
                f"{record.message}"
            )
            candidates.append(record.to_dict())

        return {"status": "ok", "count": len(candidates), "candidates": candidates}

    def remember_operator_note(self, text: str) -> Dict[str, Any]:
        if self.operator_memory is None:
            return {"status": "blocked", "reason": "operator_memory_disabled"}
        return self.operator_memory.remember(text, source="operator")

    def force_compact_operator_memory(self) -> Dict[str, Any]:
        if self.operator_memory is None or self.memory_compactor is None:
            return {"status": "blocked", "reason": "operator_memory_disabled"}
        result = self.memory_compactor.compact(
            self.memory.as_messages(),
            session_id=self.session_id,
            event_id=new_id("compact"),
            force=True,
        )
        if result.get("status") == "compacted":
            self.memory.messages = list(result.get("kept_messages", self.memory.messages))
        return {k: v for k, v in result.items() if k != "kept_messages"}

    def review_operator_memory(self, limit: int = 20, include_archived: bool = False) -> Dict[str, Any]:
        if self.operator_memory is None:
            return {"status": "blocked", "reason": "operator_memory_disabled"}
        items = self.operator_memory.list_candidate_memories(
            limit=max(0, min(limit, 100)),
            include_archived=include_archived,
        )
        return {"status": "ok", "count": len(items), "items": items}

    def pin_operator_memory(self, memory_id: str) -> Dict[str, Any]:
        if self.operator_memory is None:
            return {"status": "blocked", "reason": "operator_memory_disabled"}
        return self.operator_memory.pin_memory(memory_id)

    def unpin_operator_memory(self, memory_id: str) -> Dict[str, Any]:
        if self.operator_memory is None:
            return {"status": "blocked", "reason": "operator_memory_disabled"}
        return self.operator_memory.unpin_memory(memory_id)

    def archive_operator_memory(self, memory_id: str) -> Dict[str, Any]:
        if self.operator_memory is None:
            return {"status": "blocked", "reason": "operator_memory_disabled"}
        return self.operator_memory.archive_memory(memory_id)

    def forget_operator_memory(self, memory_id: str) -> Dict[str, Any]:
        if self.operator_memory is None:
            return {"status": "blocked", "reason": "operator_memory_disabled"}
        return self.operator_memory.forget_memory(memory_id)

    def _last_llm_usage(self) -> Dict[str, Any]:
        meta = getattr(self.planner, "last_llm_meta", {}) or {}
        usage = meta.get("usage")
        if isinstance(usage, dict):
            return usage
        llm_usage = getattr(self.planner.llm, "last_usage", {})
        return llm_usage if isinstance(llm_usage, dict) else {}

    def provider_status(self) -> Dict[str, Any]:
        llm = self.planner.llm
        config = getattr(llm, "config", None)
        fallback_mode = str(getattr(config, "fallback_mode", "off") or "off")
        fallback_models = list(getattr(config, "fallback_models", []) or [])
        return {
            "provider": getattr(llm, "provider", "unknown"),
            "configured_model": getattr(llm, "configured_model", getattr(llm, "model", "unknown")),
            "effective_model": getattr(llm, "model", "unknown"),
            "fallback_mode": fallback_mode,
            "fallback_enabled": env_mode_enabled(fallback_mode),
            "fallback_models": fallback_models,
            "last_fallback_used": bool(getattr(llm, "last_fallback_used", False)),
            "last_fallback_chain": getattr(llm, "last_fallback_chain", []),
            "last_provider_error": getattr(llm, "last_provider_error", None),
            "last_llm_meta": getattr(self.planner, "last_llm_meta", {}),
        }

    def _record_operator_memory_turn(
        self,
        *,
        event: AgentEvent,
        reply_text: str,
        external_result: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        if self.operator_memory is None:
            return {"enabled": False}

        memory_record: Dict[str, Any] = {
            "enabled": True,
            "memory_dir": str(self.operator_memory.memory_dir),
            "raw": [],
        }
        memory_record["raw"].append(
            self.operator_memory.append_raw_turn(
                session_id=self.session_id,
                role="user",
                content=event.raw_text or "",
                metadata={"event_id": event.event_id, "source": event.source},
            )
        )
        memory_record["raw"].append(
            self.operator_memory.append_raw_turn(
                session_id=self.session_id,
                role="assistant",
                content=reply_text,
                metadata={
                    "event_id": event.event_id,
                    "source": event.source,
                    "external_result": to_jsonable(external_result),
                },
            )
        )

        candidate_result = self.operator_memory.auto_capture_candidate_from_turn(
            session_id=self.session_id,
            event_id=event.event_id,
            user_text=event.raw_text or "",
            assistant_text=reply_text,
        )
        memory_record["candidate_memory"] = candidate_result

        hot_context = list((self._last_operator_memory_context.hot_items if self._last_operator_memory_context else []) or [])
        memory_record["hot_context"] = [
            {
                "id": item.get("id"),
                "content": item.get("content"),
                "pinned": item.get("pinned", False),
                "hit_count": item.get("hit_count", 0),
            }
            for item in hot_context
        ]
        memory_record["hot_context_hits"] = []
        for item in hot_context:
            memory_id = str(item.get("id", "")).strip()
            if memory_id:
                memory_record["hot_context_hits"].append(
                    self.operator_memory.record_memory_hit(
                        memory_id,
                        event_id=event.event_id,
                        query=event.raw_text or "",
                    )
                )

        usage = self._last_llm_usage()
        compact_result: Dict[str, Any] = {"status": "skipped", "reason": "operator_memory_disabled"}
        if self.memory_compactor is not None:
            compact_result = self.memory_compactor.compact(
                self.memory.as_messages(),
                session_id=self.session_id,
                event_id=event.event_id,
                usage=usage,
            )
            if compact_result.get("status") == "compacted":
                self.memory.messages = list(compact_result.get("kept_messages", self.memory.messages))

        telemetry = TokenTelemetry(self.operator_memory.tokens_file)
        telemetry_row = telemetry.record(
            event_id=event.event_id,
            provider=str(getattr(self.planner.llm, "provider", "unknown")),
            model=str(getattr(self.planner.llm, "model", "unknown")),
            usage=usage,
            messages=self.memory.as_messages(),
            compact_triggered=compact_result.get("status") == "compacted",
        )
        memory_record["telemetry"] = telemetry_row
        memory_record["compact"] = {k: v for k, v in compact_result.items() if k != "kept_messages"}
        return memory_record

    def _get_team(self) -> Optional[AgentTeamManager]:
        if not DEFAULT_ENABLE_AGENT_TEAM:
            return None
        if self.team is None:
            self.team = AgentTeamManager(self, DEFAULT_TEAM_DIR)
        return self.team

    def dispatch_subagent_tool(
        self,
        task: str,
        agent_type: str = "neiguan_yingzao",
        purpose: str = "",
        max_turns: Optional[int] = None,
    ) -> Dict[str, Any]:
        return self.run_subagent(
            task=task,
            agent_type=agent_type,
            purpose=purpose,
            max_turns=max_turns,
        )

    def _new_child_llm(self) -> LLMClient:
        parent = self.planner.llm
        if isinstance(parent, OpenRouterLLM):
            return OpenRouterLLM(parent.config)
        return parent

    def run_subagent(
        self,
        task: str,
        agent_type: str = "neiguan_yingzao",
        purpose: str = "",
        max_turns: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Run a bounded worker with isolated messages and a narrow tool whitelist.

        The subagent cannot mutate main memory/todos directly. It returns a compressed report
        to the main tool loop as a normal tool_result.
        """
        self.subagent_counter += 1
        serial = self.subagent_counter
        resolved_type = resolve_subagent_type(agent_type)
        spec = SUBAGENT_SPECS[resolved_type]
        turns = max(1, min(max_turns or spec.max_turns, 30))
        label = purpose or task[:80]

        if DEFAULT_VERBOSE_SUBAGENTS:
            print(f"\n[派遣子代理 #{serial}({spec.title} / {resolved_type})]: {label}")
            print("  ┌── subagent context start ──")

        llm = self._new_child_llm()
        chat_fn = getattr(llm, "chat", None)
        if not callable(chat_fn):
            return {
                "status": "failed",
                "agent_type": resolved_type,
                "error": "llm_client_has_no_chat_method",
            }

        sub_gate = SafetyGate(allowed_tools=spec.allowed_tools)
        tool_schemas = self.tools.openai_tool_schemas(allowed_tool_names=set(spec.allowed_tools))
        messages: List[Dict[str, Any]] = [{"role": "user", "content": task}]
        sub_trace: List[Dict[str, Any]] = []

        synthetic_event = AgentEvent(
            schema_version="agent_event.v1",
            event_id=new_id("subevt"),
            timestamp=utc_now(),
            actor=f"subagent:{resolved_type}",
            source="subagent",
            event_type=EventType.USER_MESSAGE,
            raw_text=task,
            user_intent="subagent_task",
            safety_context={"risk": "low"},
        )

        for turn_idx in range(turns):
            result: LLMChatResult = chat_fn(
                messages,
                system_prompt=build_subagent_prompt(resolved_type),
                policy_context=(
                    "You are inside an isolated subagent context. "
                    "Return a concise report to the main agent. "
                    "Do not call dispatch_subagent."
                ),
                tools=tool_schemas,
                stream=False,
            )

            if not result.tool_calls:
                summary = result.content.strip()
                if DEFAULT_VERBOSE_SUBAGENTS:
                    print(f"  └── subagent context end (内部 {turn_idx + 1} 轮，回传 {len(summary)} 字) ──")
                    print(f"[子代理回禀]: {summary}\n")
                return {
                    "status": "ok",
                    "agent_type": resolved_type,
                    "title": spec.title,
                    "turns": turn_idx + 1,
                    "summary": summary,
                    "trace": sub_trace,
                }

            assistant_tool_calls = []
            for call in result.tool_calls:
                assistant_tool_calls.append({
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": json.dumps(call.arguments, ensure_ascii=False),
                    },
                })

            messages.append({
                "role": "assistant",
                "content": result.content or "",
                "tool_calls": assistant_tool_calls,
            })

            for call in result.tool_calls:
                candidate = AgentAction(
                    action_type=ActionType.TOOL_CALL,
                    tool_call=ToolCall(tool_name=call.name, args=call.arguments),
                    reason="subagent_requested_tool_call",
                )
                gate_result = sub_gate.check(synthetic_event, candidate)

                if DEFAULT_VERBOSE_SUBAGENTS:
                    print(f"  [子({spec.title})·执行工具]: {call.name} {json.dumps(call.arguments, ensure_ascii=False)}")

                if gate_result.allowed:
                    tool_output = self.tools.execute(candidate.tool_call) if candidate.tool_call else {
                        "status": "failed",
                        "error": "missing tool call",
                    }
                else:
                    tool_output = {
                        "status": "blocked",
                        "reason": gate_result.reason,
                        "tool_name": call.name,
                    }

                if DEFAULT_VERBOSE_SUBAGENTS:
                    preview = json.dumps(to_jsonable(tool_output), ensure_ascii=False)
                    print(f"  [子({spec.title})·工具输出]: {preview[:500]}")

                sub_trace.append({
                    "turn_idx": turn_idx,
                    "tool_call": {
                        "id": call.id,
                        "name": call.name,
                        "arguments": call.arguments,
                    },
                    "gate": gate_result,
                    "output": tool_output,
                })

                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "name": call.name,
                    "content": json.dumps(to_jsonable(tool_output), ensure_ascii=False),
                })

        if DEFAULT_VERBOSE_SUBAGENTS:
            print(f"  └── subagent context end (达到 {turns} 轮上限，未完全办妥) ──\n")

        return {
            "status": "incomplete",
            "agent_type": resolved_type,
            "title": spec.title,
            "turns": turns,
            "summary": "子代理达到轮次上限，未能形成最终回禀。",
            "trace": sub_trace,
        }

    def handle_user_message(
        self,
        text: str,
        *,
        actor: str = "user",
        source: str = "cli",
        safety_context: Optional[Dict[str, Any]] = None,
    ) -> RuntimeResult:
        event = AgentEvent(
            schema_version="agent_event.v1",
            event_id=new_id("evt"),
            timestamp=utc_now(),
            actor=actor,
            source=source,
            event_type=EventType.USER_MESSAGE,
            raw_text=text,
            user_intent=None,
            safety_context=safety_context or {"risk": "low"},
        )

        # Simple conversation memory: add current user turn before LLM planning.
        # This lets the LLM see prior turns plus the latest user message.
        self.memory.add_user(text)

        state = self.state_store.load_latest()
        kernel_output = self.kernel.process_event(state, event)
        subject_context_snapshot = (
            self.build_subject_context(text)
            if self.subject_context_enabled
            else SubjectContextSnapshot(raw_user_text=text)
        )
        subject_context_prompt = (
            subject_context_snapshot.render_for_prompt()
            if self.subject_context_enabled
            else ""
        )

        tool_trace: List[Dict[str, Any]] = []
        tool_loop_result = self._try_llm_tool_loop(event, kernel_output, subject_context_prompt)
        if tool_loop_result is not None:
            action, gate_result, external_result, reply_text, tool_trace = tool_loop_result
        else:
            candidate = self.planner.propose(
                event,
                kernel_output,
                memory=self.memory,
                operator_memory_context=self.render_operator_memory_context(text),
                subject_context=subject_context_prompt,
            )
            gate_result = self.gate.check(event, candidate)

            external_result: Optional[Dict[str, Any]] = None
            reply_text = ""

            if not gate_result.allowed:
                blocked_action = AgentAction(
                    action_type=ActionType.BLOCK,
                    content=f"已阻断：{gate_result.reason}",
                    reason="gate_block",
                )
                action = blocked_action
                external_result = {"status": "blocked", "reason": gate_result.reason}
                reply_text = blocked_action.content
            else:
                action = candidate
                if action.action_type == ActionType.TOOL_CALL and action.tool_call:
                    external_result = self.tools.execute(action.tool_call)
                    reply_text = f"工具结果：{json.dumps(external_result, ensure_ascii=False)}"
                elif action.action_type == ActionType.ASK:
                    external_result = {"status": "asked"}
                    reply_text = action.content
                else:
                    external_result = {"status": "sent"}
                    reply_text = action.content

        if not str(reply_text or "").strip():
            reply_text = "模型返回了空回复；我没有执行任何外部动作。请重试或换一个更稳定的模型。"
            action = AgentAction(
                action_type=ActionType.RESPOND,
                content=reply_text,
                reason="empty_reply_guard",
            )
            gate_result = self.gate.check(event, action)
            external_result = {
                "status": "empty_reply_recovered",
                "side_effects_executed": False,
                "previous_external_result": external_result,
            }

        # Write visible assistant reply back into simple conversation memory.
        self.memory.add_assistant(reply_text)
        operator_memory_record = self._record_operator_memory_turn(
            event=event,
            reply_text=reply_text,
            external_result=external_result,
        )

        outcome_event = AgentEvent(
            schema_version="agent_event.v1",
            event_id=new_id("evt"),
            timestamp=utc_now(),
            actor="runtime",
            source=source,
            event_type=EventType.TOOL_RESULT if tool_trace else EventType.SYSTEM_TICK,
            raw_text=None,
            user_intent="outcome_feedback",
            external_result=external_result,
            safety_context=safety_context or {"risk": "low"},
        )
        outcome_kernel_output = self.kernel.process_event(state, outcome_event)
        self.state_store.save(state)

        self.trace_store.write({
            "event": event,
            "kernel_output": kernel_output,
            "candidate_action": action,
            "llm_meta": getattr(self.planner, "last_llm_meta", {}),
            "gate": gate_result,
            "external_result": external_result,
            "tool_trace": tool_trace,
            "memory": {
                "message_count": len(self.memory),
                "tail": self.memory.as_messages(max_messages=6),
            },
            "operator_memory": operator_memory_record,
            "subject_context": subject_context_snapshot,
            "todo": self.todo_list.summary(),
            "operator_runtime": {
                "runtime_mode": self.runtime_mode,
                "permission_broker": self.permission_broker.describe(),
            },
            "outcome_event": outcome_event,
            "outcome_kernel_output": outcome_kernel_output,
            "state_digest": {
                "mode": state.self_model.current_mode,
                "focus": state.self_model.current_focus,
                "drives": state.drives,
                "revision_counter": state.revision_counter,
                "cycle_count": len(state.cycle_store.signatures),
            },
        })

        return RuntimeResult(
            event_id=event.event_id,
            action=action,
            gate=gate_result,
            external_result=external_result,
            reply_text=reply_text,
        )

    def _try_llm_tool_loop(
        self,
        event: AgentEvent,
        kernel_output: KernelOutput,
        subject_context: str = "",
    ) -> Optional[tuple[AgentAction, GateResult, Dict[str, Any], str, List[Dict[str, Any]]]]:
        """
        Use OpenAI/OpenRouter-compatible tool calling when the LLM client supports chat(...).

        Tool execution remains outside the LLM:
        LLM proposes tool_calls -> SafetyGate admits/blocks -> ToolRegistry executes -> LLM formats final answer.
        """
        llm = self.planner.llm
        chat_fn = getattr(llm, "chat", None)
        if not callable(chat_fn):
            return None

        allowed = getattr(self.gate, "allowed_tools", set())
        tool_schemas = self.tools.openai_tool_schemas(allowed_tool_names=allowed)
        messages: List[Dict[str, Any]] = self.memory.as_messages()

        policy_context = (
            "Current policy hint:\n"
            f"{json.dumps(kernel_output.policy_hint, ensure_ascii=False)}\n\n"
            "Current response tendency:\n"
            f"{json.dumps(to_jsonable(kernel_output.response_tendency), ensure_ascii=False)}"
            "\n\nCurrent todolist:\n"
            f"{self.todo_list.render()}"
        )

        tool_trace: List[Dict[str, Any]] = []
        last_external_result: Dict[str, Any] = {"status": "sent"}
        final_action = AgentAction(action_type=ActionType.RESPOND, content="", reason="llm_tool_loop_response")
        final_gate = GateResult(True, "text_action_allowed")

        try:
            soft_cap = max(1, int(DEFAULT_MAX_TOOL_LOOPS))
            hard_cap = max(soft_cap, int(DEFAULT_TOOL_LOOP_HARD_CAP))
            loop_idx = 0
            empty_final_repairs = 0
            unbacked_approval_repairs = 0
            allowed_root_refusal_repairs = 0
            while loop_idx < hard_cap:
                if loop_idx > 0 and loop_idx % soft_cap == 0:
                    messages.append({
                        "role": "system",
                        "content": (
                            "[tool_loop_checkpoint]\n"
                            f"You have used {loop_idx} tool-call rounds, reaching the soft budget of {soft_cap}. "
                            "If current results are enough, stop calling tools and answer now. "
                            f"If more work is necessary, continue with the minimum next tool calls. Hard cap is {hard_cap}."
                        ),
                    })

                result: LLMChatResult = chat_fn(
                    messages,
                    system_prompt=self.build_runtime_system_prompt(subject_context, event.raw_text or ""),
                    policy_context=policy_context,
                    tools=tool_schemas,
                    stream=False,
                )

                self.planner.last_llm_meta = {
                    "provider": getattr(llm, "provider", "unknown"),
                    "model": getattr(llm, "model", "unknown"),
                    "configured_model": getattr(llm, "configured_model", getattr(llm, "model", "unknown")),
                    "usage": getattr(llm, "last_usage", {}),
                    "reasoning_tokens": getattr(llm, "last_reasoning_tokens", None),
                    "fallback_used": bool(getattr(llm, "last_fallback_used", False)),
                    "fallback_chain": getattr(llm, "last_fallback_chain", []),
                    "provider_error": getattr(llm, "last_provider_error", None),
                    "tool_loop": True,
                    "loop_idx": loop_idx,
                }

                if not result.tool_calls:
                    content = (result.content or "").strip()
                    if not content:
                        if empty_final_repairs < 1:
                            empty_final_repairs += 1
                            messages.append({
                                "role": "system",
                                "content": (
                                    "[empty_response_repair]\n"
                                    "The previous model response had no tool calls and no visible content. "
                                    "Continue by either calling the appropriate tool/proposal or returning a non-empty "
                                    "Chinese reply that states exactly what is still incomplete. Do not return empty content."
                                ),
                            })
                            loop_idx += 1
                            continue
                        content = self._format_empty_llm_recovery_reply(tool_trace)
                        final_action = AgentAction(
                            action_type=ActionType.RESPOND,
                            content=content,
                            reason="llm_empty_response_recovered",
                        )
                        final_gate = self.gate.check(event, final_action)
                        return final_action, final_gate, {
                            "status": "llm_empty_response",
                            "side_effects_executed": False,
                            "tool_calls": len(tool_trace),
                        }, content, tool_trace

                    approval_claim = self._detect_unbacked_approval_reply(content)
                    if approval_claim.get("status") == "unbacked_approval_claim":
                        max_unbacked_repairs = max(0, int(DEFAULT_UNBACKED_APPROVAL_REPAIR_ATTEMPTS))
                        if unbacked_approval_repairs < max_unbacked_repairs:
                            unbacked_approval_repairs += 1
                            messages.append({
                                "role": "system",
                                "content": (
                                    "[unbacked_approval_repair]\n"
                                    f"Attempt {unbacked_approval_repairs}/{max_unbacked_repairs}. "
                                    "The previous assistant text appeared to show a pending approval card, but no real "
                                    "runtime proposal exists for that id. Do not invent proposal ids, content hashes, "
                                    "or /approve commands. Do not ask the user to repeat the request. "
                                    "If a file write is needed, call propose_file_write now with the user's requested "
                                    "path and content. If another gated side effect is needed, call the matching "
                                    "proposal tool. If you cannot call a proposal tool, answer in Chinese that no real "
                                    "proposal was created and no side effect ran."
                                ),
                            })
                            loop_idx += 1
                            continue
                        content = self._format_unbacked_approval_recovery_reply(
                            approval_claim,
                            tool_trace,
                            repair_attempts=unbacked_approval_repairs,
                        )
                        final_action = AgentAction(
                            action_type=ActionType.RESPOND,
                            content=content,
                            reason="llm_unbacked_approval_auto_repair_exhausted",
                        )
                        final_gate = self.gate.check(event, final_action)
                        return final_action, final_gate, {
                            "status": "unbacked_approval_auto_repair_exhausted",
                            "side_effects_executed": False,
                            "tool_calls": len(tool_trace),
                            "auto_repair_attempts": unbacked_approval_repairs,
                            "approval_claim": approval_claim,
                        }, content, tool_trace

                    allowed_root_refusal = self._detect_allowed_root_workspace_refusal(event.raw_text or "", content)
                    if allowed_root_refusal.get("status") == "allowed_root_workspace_refusal":
                        if allowed_root_refusal_repairs < 1:
                            allowed_root_refusal_repairs += 1
                            messages.append({
                                "role": "system",
                                "content": (
                                    "[allowed_root_refusal_repair]\n"
                                    "The previous assistant text refused the requested path as outside workspace, "
                                    "but the user's explicit path is inside allowed_roots. Do not fallback to a "
                                    "workspace-local path. Call the appropriate file tool now, preferably "
                                    "propose_file_write for create/modify requests, using the user's exact target "
                                    "path or letting runtime path-intent correction preserve it. If the runtime tool "
                                    "blocks the path, report that real tool result instead of guessing."
                                ),
                            })
                            loop_idx += 1
                            continue
                        content = self._format_allowed_root_refusal_recovery_reply(allowed_root_refusal, tool_trace)
                        final_action = AgentAction(
                            action_type=ActionType.RESPOND,
                            content=content,
                            reason="llm_allowed_root_refusal_recovered",
                        )
                        final_gate = self.gate.check(event, final_action)
                        return final_action, final_gate, {
                            "status": "allowed_root_workspace_refusal",
                            "side_effects_executed": False,
                            "tool_calls": len(tool_trace),
                            "refusal": allowed_root_refusal,
                        }, content, tool_trace

                    final_action = AgentAction(
                        action_type=ActionType.RESPOND,
                        content=content,
                        reason="llm_tool_loop_final_response",
                    )
                    final_gate = self.gate.check(event, final_action)
                    if not final_gate.allowed:
                        blocked = AgentAction(
                            action_type=ActionType.BLOCK,
                            content=f"已阻断：{final_gate.reason}",
                            reason="gate_block_final_text",
                        )
                        return blocked, final_gate, {"status": "blocked", "reason": final_gate.reason}, blocked.content, tool_trace
                    return final_action, final_gate, last_external_result, content, tool_trace

                assistant_tool_calls = []
                for call in result.tool_calls:
                    assistant_tool_calls.append({
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.name,
                            "arguments": json.dumps(call.arguments, ensure_ascii=False),
                        },
                    })

                messages.append({
                    "role": "assistant",
                    "content": result.content or "",
                    "tool_calls": assistant_tool_calls,
                })

                def _execute_main_tool_call(call: LLMToolCall) -> tuple[str, GateResult, Dict[str, Any], Dict[str, Any]]:
                    effective_arguments = dict(call.arguments)
                    path_intent: Dict[str, Any] = {"status": "not_applicable"}
                    if call.name in {"propose_file_write", "read_file", "grep_files", "glob_files"}:
                        if call.name == "glob_files":
                            corrected_value, path_intent = _glob_path_intent_adjustment(
                                event.raw_text or "",
                                str(effective_arguments.get("pattern", "")),
                            )
                            argument_name = "pattern"
                        else:
                            argument_name = "path"
                            adjustment_fn = (
                                _path_intent_adjustment
                                if call.name == "propose_file_write"
                                else _read_scope_path_intent_adjustment
                            )
                            corrected_value, path_intent = adjustment_fn(
                                event.raw_text or "",
                                str(effective_arguments.get(argument_name, "")),
                            )
                        if path_intent.get("status") == "corrected":
                            effective_arguments[argument_name] = corrected_value
                        elif path_intent.get("status") == "blocked":
                            reason = str(path_intent.get("reason", "path_intent_mismatch"))
                            gate_result = GateResult(False, reason)
                            tool_output = {
                                "status": "blocked",
                                "reason": reason,
                                "tool_name": call.name,
                                "path_intent": path_intent,
                                "do_not_claim_success": True,
                                "user_visible_correction": (
                                    "The tool path did not match the user's explicit path intent. "
                                    "Do not claim success; retry with the exact intended path or ask for clarification."
                                ),
                            }
                            trace_entry = {
                                "loop_idx": loop_idx,
                                "tool_call": {
                                    "id": call.id,
                                    "name": call.name,
                                    "arguments": effective_arguments,
                                    "original_arguments": call.arguments,
                                    "path_intent": path_intent,
                                },
                                "gate": gate_result,
                                "output": tool_output,
                            }
                            return call.id, gate_result, tool_output, trace_entry

                    effective_call = LLMToolCall(id=call.id, name=call.name, arguments=effective_arguments)
                    candidate = AgentAction(
                        action_type=ActionType.TOOL_CALL,
                        tool_call=ToolCall(tool_name=effective_call.name, args=effective_call.arguments),
                        reason="llm_requested_tool_call",
                    )
                    gate_result = self.gate.check(event, candidate)

                    if DEFAULT_VERBOSE_TOOLS:
                        print(f"[执行工具]: {effective_call.name} {json.dumps(effective_call.arguments, ensure_ascii=False)}")

                    if gate_result.allowed:
                        tool_output = self.tools.execute(candidate.tool_call) if candidate.tool_call else {
                            "status": "failed",
                            "error": "missing tool call",
                        }
                    else:
                        tool_output = {
                            "status": "blocked",
                            "reason": gate_result.reason,
                            "tool_name": effective_call.name,
                            "do_not_claim_success": True,
                        }
                        if effective_call.name == "remember_note":
                            tool_output["user_visible_correction"] = (
                                "Memory was not written. Do not say it was remembered; "
                                "tell the operator it was not saved and ask for explicit /remember or remember intent."
                            )
                    if path_intent.get("status") == "corrected" and isinstance(tool_output, dict):
                        tool_output["path_intent"] = path_intent

                    if DEFAULT_VERBOSE_TOOLS:
                        print(f"[工具输出]: {json.dumps(to_jsonable(tool_output), ensure_ascii=False)[:1200]}")

                    trace_entry = {
                        "loop_idx": loop_idx,
                        "tool_call": {
                            "id": call.id,
                            "name": effective_call.name,
                            "arguments": effective_call.arguments,
                        },
                        "gate": gate_result,
                        "output": tool_output,
                    }
                    if path_intent.get("status") != "not_applicable":
                        trace_entry["tool_call"]["original_arguments"] = call.arguments
                        trace_entry["tool_call"]["path_intent"] = path_intent
                    return call.id, gate_result, tool_output, trace_entry

                results_by_id: Dict[str, tuple[GateResult, Dict[str, Any], Dict[str, Any]]] = {}
                dispatch_calls = [call for call in result.tool_calls if call.name == "dispatch_subagent"]
                non_dispatch_calls = [call for call in result.tool_calls if call.name != "dispatch_subagent"]

                for call in non_dispatch_calls:
                    call_id, gate_result, tool_output, trace_entry = _execute_main_tool_call(call)
                    results_by_id[call_id] = (gate_result, tool_output, trace_entry)

                if len(dispatch_calls) > 1:
                    max_workers = min(len(dispatch_calls), DEFAULT_MAX_SUBAGENTS_PER_BATCH)
                    if DEFAULT_VERBOSE_SUBAGENTS:
                        print(f"\n[并发派遣 {len(dispatch_calls)} 个子代理，max_workers={max_workers}]\n")
                    with ThreadPoolExecutor(max_workers=max_workers) as pool:
                        for call_id, gate_result, tool_output, trace_entry in pool.map(_execute_main_tool_call, dispatch_calls):
                            results_by_id[call_id] = (gate_result, tool_output, trace_entry)
                else:
                    for call in dispatch_calls:
                        call_id, gate_result, tool_output, trace_entry = _execute_main_tool_call(call)
                        results_by_id[call_id] = (gate_result, tool_output, trace_entry)

                for call in result.tool_calls:
                    gate_result, tool_output, trace_entry = results_by_id[call.id]

                    last_external_result = {
                        "status": "tool_result",
                        "tool_name": call.name,
                        "gate_allowed": gate_result.allowed,
                        "gate_reason": gate_result.reason,
                        "output": tool_output,
                    }
                    tool_trace.append(trace_entry)

                    messages.append({
                        "role": "tool",
                        "tool_call_id": call.id,
                        "name": call.name,
                        "content": json.dumps(to_jsonable(tool_output), ensure_ascii=False),
                    })

                pending_outputs = [
                    entry["output"]
                    for entry in tool_trace[-len(result.tool_calls):]
                    if isinstance(entry.get("output"), dict)
                    and entry["output"].get("status") == "pending_approval"
                ]
                if pending_outputs:
                    content = self._format_pending_approval_reply(pending_outputs)
                    action = AgentAction(action_type=ActionType.RESPOND, content=content, reason="pending_approval_ready")
                    gate = self.gate.check(event, action)
                    external_result = {
                        "status": "pending_approval",
                        "pending_count": len(pending_outputs),
                        "pending": [
                            {
                                "proposal_id": (output.get("proposal") or {}).get("proposal_id"),
                                "action": (output.get("proposal") or {}).get("action"),
                                "next": output.get("next"),
                            }
                            for output in pending_outputs
                        ],
                    }
                    return action, gate, external_result, content, tool_trace

                loop_idx += 1

            content = (
                f"已达到工具循环 hard cap ({hard_cap})，已停止继续调用。\n"
                f"当前已完成 {len(tool_trace)} 次工具调用。请根据已有结果批准、调整或重试。"
            )
            action = AgentAction(action_type=ActionType.BLOCK, content=content, reason="tool_loop_hard_cap")
            gate = GateResult(False, "tool_loop_hard_cap")
            return action, gate, {"status": "blocked", "reason": "tool_loop_hard_cap", "tool_calls": len(tool_trace)}, content, tool_trace

        except Exception as exc:
            self.planner.last_llm_meta = {
                "provider": getattr(llm, "provider", "unknown"),
                "model": getattr(llm, "model", "unknown"),
                "configured_model": getattr(llm, "configured_model", getattr(llm, "model", "unknown")),
                "error": repr(exc),
                "provider_error": getattr(exc, "to_metadata", lambda: None)(),
                "fallback_chain": getattr(llm, "last_fallback_chain", []),
                "fallback_used": bool(getattr(llm, "last_fallback_used", False)),
                "error_recovered": True,
                "tool_loop": True,
            }
            content = self._format_llm_tool_loop_error_reply(exc, tool_trace)
            action = AgentAction(
                action_type=ActionType.RESPOND,
                content=content,
                reason="llm_tool_loop_provider_error",
            )
            gate = self.gate.check(event, action)
            return action, gate, {
                "status": "llm_error",
                "reason": "provider_exception",
                "error": repr(exc),
                "provider_error": getattr(exc, "to_metadata", lambda: None)(),
                "fallback_chain": getattr(llm, "last_fallback_chain", []),
                "fallback_used": bool(getattr(llm, "last_fallback_used", False)),
                "tool_calls": len(tool_trace),
                "side_effects_executed": False,
            }, content, tool_trace

    def _format_empty_llm_recovery_reply(self, tool_trace: List[Dict[str, Any]]) -> str:
        lines = [
            "模型连续返回了空回复，我没有把它当成成功结果。",
            f"当前已完成工具调用：{len(tool_trace)} 次。",
            "没有执行文件创建或修改；这个任务仍未完成。",
            "你可以直接重试同一句请求，或稍后切换到更稳定的模型后继续。",
        ]
        if tool_trace:
            last = tool_trace[-1]
            tool_name = ((last.get("tool_call") or {}).get("name") or "unknown")
            output = last.get("output") or {}
            status = output.get("status") if isinstance(output, dict) else "unknown"
            lines.insert(2, f"最后一次工具结果：{tool_name} -> {status}。")
        return "\n".join(lines)

    def _detect_unbacked_approval_reply(self, content: str) -> Dict[str, Any]:
        if not _text_claims_operation_approval(content):
            return {"status": "not_applicable"}
        ids = _extract_proposal_ids_from_text(content)
        known_ids = set(self.permission_broker.proposals.keys())
        unknown_ids = [proposal_id for proposal_id in ids if proposal_id not in known_ids]
        if ids and not unknown_ids:
            return {"status": "backed_approval_claim", "proposal_ids": ids}
        return {
            "status": "unbacked_approval_claim",
            "proposal_ids": ids,
            "unknown_proposal_ids": unknown_ids,
            "known_pending_ids": [
                proposal.proposal_id
                for proposal in self.permission_broker.proposals.values()
                if proposal.status == "pending"
            ],
        }

    def _detect_allowed_root_workspace_refusal(self, user_text: str, content: str) -> Dict[str, Any]:
        if not _text_claims_workspace_refusal(content):
            return {"status": "not_applicable"}
        intents = _extract_local_path_intents(user_text)
        if not intents:
            return {"status": "not_applicable"}
        return {
            "status": "allowed_root_workspace_refusal",
            "intended_paths": [intent.resolved_path for intent in intents],
            "raw_intent_paths": [intent.raw_path for intent in intents],
            "allowed_roots": [str(root) for root in _iter_allowed_roots()],
        }

    def _format_unbacked_approval_recovery_reply(
        self,
        approval_claim: Dict[str, Any],
        tool_trace: List[Dict[str, Any]],
        repair_attempts: int = 0,
    ) -> str:
        unknown_ids = approval_claim.get("unknown_proposal_ids") or approval_claim.get("proposal_ids") or []
        lines = [
            "模型连续生成了待审批文本，但 runtime 没有对应的真实 proposal，所以我没有把它当成可批准操作。",
            f"可疑 proposal id：{', '.join(unknown_ids) if unknown_ids else '未提供真实 id'}。",
            f"已自动尝试修复：{repair_attempts} 次。",
            f"当前已完成工具调用：{len(tool_trace)} 次。",
            "没有执行文件创建或修改；本轮没有生成可执行的真实审批项。",
        ]
        return "\n".join(lines)

    def _format_allowed_root_refusal_recovery_reply(
        self,
        refusal: Dict[str, Any],
        tool_trace: List[Dict[str, Any]],
    ) -> str:
        paths = refusal.get("intended_paths") or []
        lines = [
            "模型把用户给出的路径误判成 workspace 外路径；runtime 已识别该路径位于 allowed_roots 内。",
            f"目标路径：{', '.join(paths) if paths else 'unknown'}。",
            f"当前已完成工具调用：{len(tool_trace)} 次。",
            "没有执行文件创建或修改；请重试同一句请求，我会要求模型必须调用文件工具并保留原目标路径。",
        ]
        return "\n".join(lines)

    def _format_llm_tool_loop_error_reply(self, exc: Exception, tool_trace: List[Dict[str, Any]]) -> str:
        error_text = repr(exc)
        provider_error = exc if isinstance(exc, OpenRouterProviderError) else None
        status_code = provider_error.status_code if provider_error else None
        model = provider_error.model if provider_error else str(getattr(self.planner.llm, "model", "unknown"))
        retry_after = provider_error.retry_after if provider_error else None
        message = provider_error.message if provider_error else error_text
        is_rate_limited = status_code == 429 or "429" in error_text or "Too Many Requests" in error_text
        if status_code == 402:
            first_line = "模型/API 当前返回 402，账号或 API key credits 不足。"
        elif status_code == 503:
            first_line = "模型/API 当前返回 503，所选模型或 provider 暂时不可用。"
        elif is_rate_limited:
            first_line = "模型/API 当前返回 429 限流，EgoOperator 已停止本轮回复生成。"
        else:
            first_line = "模型/API 当前调用失败，EgoOperator 已停止本轮工具循环。"
        lines = [
            first_line,
            f"effective model：{model}。",
            f"provider message：{message[:500]}。",
            f"当前已完成工具调用：{len(tool_trace)} 次。",
            "没有执行外部副作用；这条回复未完成。",
        ]
        if retry_after:
            lines.append(f"Retry-After：{retry_after} 秒；建议等待后再重试。")
        if tool_trace:
            last = tool_trace[-1]
            tool_name = ((last.get("tool_call") or {}).get("name") or "unknown")
            output = last.get("output") or {}
            status = output.get("status") if isinstance(output, dict) else "unknown"
            lines.append(f"最后一次工具结果：{tool_name} -> {status}。")
        fallback_models = getattr(self.planner.llm, "config", None)
        fallback_model_list = list(getattr(fallback_models, "fallback_models", []) or [])
        if status_code == 402:
            lines.append("建议检查 OpenRouter credits / key limit，补足余额后继续。")
        elif is_rate_limited:
            if fallback_model_list and not bool(getattr(self.planner.llm, "last_fallback_used", False)):
                lines.append("建议检查 key limit / provider 容量，或开启 fallback 后切换备用模型。")
            else:
                lines.append("建议检查 key limit / provider 容量，或配置 OPENROUTER_FALLBACK_MODELS 后继续。")
        elif status_code == 503:
            lines.append("建议稍后重试，或开启 fallback 使用备用模型。")
        else:
            lines.append("建议重试；如果连续出现，请检查 provider/API key/model 配置。")
        return "\n".join(lines)

    def _format_pending_approval_reply(self, pending_outputs: List[Dict[str, Any]]) -> str:
        cards: List[str] = []
        approve_commands: List[str] = []
        for output in pending_outputs:
            action_card = str(output.get("action_card") or "").strip()
            if action_card:
                cards.append(action_card)
            proposal = output.get("proposal") or {}
            proposal_id = str(proposal.get("proposal_id") or "").strip()
            if proposal_id:
                approve_commands.append(f"/approve {proposal_id}")

        lines = ["已生成待审批操作，当前不会继续调用工具。"]
        if cards:
            lines.extend(["", *cards])
        if approve_commands:
            lines.append("")
            lines.append("批准执行：")
            for command in approve_commands:
                lines.append(f"- {command}")
        lines.append("也可以使用 /reject <proposal_id> 拒绝；文件写入 proposal 可用 /edit_approval <proposal_id> {...} 修改。")
        return "\n".join(lines)


# -----------------------------
# Demo
# -----------------------------

def build_llm_from_config() -> LLMClient:
    """
    LLM factory.

    For real OpenRouter calls, set:
      export OPENROUTER_API_KEY="sk-or-..."
      export OPENROUTER_MODEL="tencent/hy3-preview"

    If no key is present, the agent still runs with NoLLM.
    """
    if DEFAULT_LLM_PROVIDER.lower() == "openrouter" and DEFAULT_OPENROUTER_API_KEY:
        return OpenRouterLLM(LLMConfig(
            api_key=DEFAULT_OPENROUTER_API_KEY,
            model=DEFAULT_OPENROUTER_MODEL,
            base_url=DEFAULT_OPENROUTER_BASE_URL,
            stream=True,
            site_url=DEFAULT_OPENROUTER_SITE_URL,
            app_name=DEFAULT_OPENROUTER_APP_NAME,
            fallback_mode=DEFAULT_OPENROUTER_FALLBACK_MODE,
            fallback_models=DEFAULT_OPENROUTER_FALLBACK_MODELS,
            system_prompt=build_system_prompt(),
            # Example if you want reasoning metadata on supported models:
            # reasoning={"effort": "low", "exclude": False},
            reasoning=None,
        ))
    return NoLLM()


def build_operator_memory_store(memory_dir: Optional[str | Path] = None) -> OperatorMemoryStore:
    raw_target = Path(memory_dir) if memory_dir is not None else Path(os.getenv("AGENT_MEMORY_DIR", str(EGO_OPERATOR_ROOT / "memory")))
    target = raw_target if raw_target.is_absolute() else EGO_OPERATOR_ROOT / raw_target
    return OperatorMemoryStore(target, containment_root=EGO_OPERATOR_ROOT)


def build_operator_memory_from_env(*, default_enabled: bool) -> Optional[OperatorMemoryStore]:
    if not env_flag("AGENT_MEMORY", default_enabled):
        return None
    return build_operator_memory_store()


def build_demo_runtime(
    *,
    enable_operator_memory: bool = False,
    operator_memory_dir: Optional[str | Path] = None,
    subject_context_enabled: bool = True,
    runtime_mode: Optional[str] = None,
) -> AgentRuntime:
    tools = ToolRegistry()
    selected_runtime_mode = normalize_runtime_mode(runtime_mode)

    tools.register(
        "current_time",
        current_time_tool,
        description="返回当前 UTC 时间。",
        input_schema={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    )
    tools.register(
        "run_command",
        run_command_tool,
        description=(
            "在本地终端执行一条 shell 命令并返回 stdout/stderr。"
            "仅在 AGENT_ENABLE_RUN_COMMAND=1 且命令前缀进入 allowlist 时可用。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "要执行的 shell 命令，例如: echo hello 或 python --version",
                }
            },
            "required": ["command"],
            "additionalProperties": False,
        },
    )
    tools.register(
        "web_fetch",
        web_fetch_tool,
        description=(
            "获取安全 public http/https URL 的网页内容，支持 text/raw。"
            "approve 模式默认按 AGENT_WEB_FETCH_POLICY=safe-auto 放行低风险 GET；approval-only 时需 proposal。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "完整 http/https URL。"},
                "extract_mode": {"type": "string", "enum": ["text", "raw"], "description": "提取模式，默认 text。"},
                "max_chars": {"type": "integer", "description": "最大返回字符数。"},
            },
            "required": ["url"],
            "additionalProperties": False,
        },
    )
    tools.register(
        "read_file",
        read_file_tool,
        description=(
            "读取 workspace/allowed_roots 内文件内容。"
            f"workspace={DEFAULT_AGENT_WORKSPACE}; allowed_roots={_allowed_roots_prompt_text()}"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "workspace 相对路径，或 allowed_roots 内绝对路径。"},
                "max_chars": {"type": "integer", "description": "最多读取字符数。"},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
    )
    tools.register(
        "write_file",
        write_file_tool,
        description="写入 workspace 内文件；默认关闭，需 AGENT_ENABLE_WRITE_FILE=1。",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "workspace 内相对路径。"},
                "content": {"type": "string", "description": "要写入的完整内容。"},
                "create_parents": {"type": "boolean", "description": "是否自动创建父目录。"},
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        },
    )
    tools.register(
        "glob_files",
        glob_files_tool,
        description=(
            "按 glob 模式搜索 workspace/allowed_roots 内文件。"
            f"allowed_roots={_allowed_roots_prompt_text()}"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "例如 **/*.py，或 allowed_roots 内绝对 glob。"},
                "max_results": {"type": "integer", "description": "最大结果数。"},
            },
            "required": ["pattern"],
            "additionalProperties": False,
        },
    )
    tools.register(
        "grep_files",
        grep_files_tool,
        description=(
            "在 workspace/allowed_roots 内文本文件中搜索正则 pattern。"
            f"allowed_roots={_allowed_roots_prompt_text()}"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Python 正则表达式。"},
                "path": {"type": "string", "description": "workspace 相对路径或 allowed_roots 内绝对路径，默认 .。"},
                "include_extensions": {"type": "string", "description": "逗号分隔扩展名。"},
                "max_matches": {"type": "integer", "description": "最大匹配数。"},
            },
            "required": ["pattern"],
            "additionalProperties": False,
        },
    )

    todo_list = TodoList()
    operator_memory = build_operator_memory_store(operator_memory_dir) if enable_operator_memory else None
    tools.register(
        "load_skill",
        load_skill_tool,
        description="加载指定技能的 SKILL.md 正文。只能加载当前可用技能列表中的技能。",
        input_schema={
            "type": "object",
            "properties": {
                "skill_name": {
                    "type": "string",
                    "description": "技能名称，必须是 /skills 或系统提示中列出的可用技能之一。",
                }
            },
            "required": ["skill_name"],
            "additionalProperties": False,
        },
    )
    tools.register(
        "update_todos",
        make_update_todos_tool(todo_list),
        description=(
            "创建或更新当前差事的 todolist。每次必须传入完整 todos 数组，全量覆盖当前列表；"
            "用于拆解多步骤任务、推进状态 pending -> in_progress -> completed；"
            "同一时间最多一个任务为 in_progress。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "todos": {
                    "type": "array",
                    "description": "完整 todo 列表，按执行顺序排列。",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer", "description": "序号，从 1 开始。"},
                            "content": {"type": "string", "description": "这一步要做什么。"},
                            "status": {
                                "type": "string",
                                "enum": ["pending", "in_progress", "completed"],
                                "description": "任务状态。",
                            },
                        },
                        "required": ["id", "content", "status"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["todos"],
            "additionalProperties": False,
        },
    )

    # Main agent sees low-risk read tools by default. Side effects go through
    # transaction proposals unless trusted workspace mode explicitly narrows it.
    allowed_tools = [
        "current_time",
        "read_file",
        "glob_files",
        "grep_files",
        "load_skill",
        "update_todos",
        "dispatch_subagent",
    ]
    if selected_runtime_mode in {"plan", "approve", "trusted-workspace"}:
        allowed_tools.append("propose_file_write")
        allowed_tools.append("propose_web_fetch")
        allowed_tools.append("propose_heartbeat")
    if DEFAULT_ENABLE_RUN_COMMAND and selected_runtime_mode == "trusted-workspace":
        allowed_tools.append("run_command")
    if (
        (safe_auto_web_fetch_enabled() and selected_runtime_mode in {"approve", "trusted-workspace"})
        or (DEFAULT_ENABLE_WEB_FETCH and selected_runtime_mode == "trusted-workspace")
    ):
        allowed_tools.append("web_fetch")
    if DEFAULT_ENABLE_WRITE_FILE and selected_runtime_mode == "trusted-workspace":
        allowed_tools.append("write_file")
    if operator_memory is not None:
        allowed_tools.append("remember_note")
    if DEFAULT_ENABLE_AGENT_TEAM:
        allowed_tools.extend([
            "spawn_teammate",
            "list_teammates",
            "send_message",
            "read_inbox",
            "broadcast",
            "shutdown_teammate",
        ])

    planner = Planner(llm=build_llm_from_config())
    gate = SafetyGate(allowed_tools=allowed_tools, runtime_mode=selected_runtime_mode)
    runtime = AgentRuntime(
        tools=tools,
        planner=planner,
        gate=gate,
        todo_list=todo_list,
        operator_memory=operator_memory,
        subject_context_enabled=subject_context_enabled,
        runtime_mode=selected_runtime_mode,
    )

    tools.register(
        "propose_file_write",
        runtime.propose_file_write,
        description=(
            "生成一个待 operator 审批的文件写入 proposal。"
            "目标可位于 workspace 或 allowed_roots 内；不会直接写磁盘；批准后 runtime 用一次性 lease 执行。"
            f" allowed_roots={_allowed_roots_prompt_text()}"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "workspace 相对路径，或 allowed_roots 内绝对路径。"},
                "content": {"type": "string", "description": "拟写入的完整内容。"},
                "reason": {"type": "string", "description": "为什么需要写这个文件。"},
                "create_parents": {"type": "boolean", "description": "是否创建父目录。"},
                "overwrite": {"type": "boolean", "description": "是否明确请求覆盖已有文件。"},
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        },
    )

    tools.register(
        "propose_web_fetch",
        runtime.propose_web_fetch,
        description=(
            "生成一个待 operator 审批的网页读取 proposal。"
            "不会直接联网；批准后 runtime 用一次性 lease 执行，并拒绝 localhost/private/reserved 主机。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "完整 http/https URL。"},
                "extract_mode": {"type": "string", "enum": ["text", "raw"], "description": "提取模式，默认 text。"},
                "max_chars": {"type": "integer", "description": "最大返回字符数。"},
                "reason": {"type": "string", "description": "为什么需要读取这个网页。"},
            },
            "required": ["url"],
            "additionalProperties": False,
        },
    )

    tools.register(
        "propose_heartbeat",
        runtime.propose_heartbeat,
        description=(
            "生成一个待 operator 审批的 bounded heartbeat proposal。"
            "只在用户明确要求稍后提醒/主动找我/定时跟进时使用；批准后只登记候选提醒，不自动发送。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "delay_seconds": {"type": "integer", "description": "从现在起多少秒后到期，0 到 604800。"},
                "message": {"type": "string", "description": "到期时生成的候选提醒内容。"},
                "reason": {"type": "string", "description": "为什么需要这个 bounded heartbeat。"},
            },
            "required": ["delay_seconds", "message"],
            "additionalProperties": False,
        },
    )

    tools.register(
        "remember_note",
        runtime.remember_operator_note,
        description=(
            "把用户明确要求记住的内容写入 EgoOperator candidate-local MEMORY.md。"
            "只能在用户消息含有明确记忆意图时调用；不是 EGO repo authority。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "要写入 candidate-local core memory 的原文或压缩记忆。"},
            },
            "required": ["text"],
            "additionalProperties": False,
        },
    )

    tools.register(
        "dispatch_subagent",
        runtime.dispatch_subagent_tool,
        description=(
            "派遣一个隔离上下文的子代理去完成细节任务。"
            "适合批量读文件、核验资料、探索性查找、或需要压缩回禀的子任务。"
            "子代理不能修改主记忆和主 todolist；只返回总结。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "交给子代理的具体差事。"},
                "agent_type": {
                    "type": "string",
                    "enum": SUBAGENT_TYPE_OPTIONS,
                    "description": (
                        "xiaohuangmen=轻量只读；sili_suitang=文书阅读；"
                        "dongchang_tanshi=查访网页；shangbao_dianbu=盘点核验；"
                        "neiguan_yingzao=营造改写。"
                    ),
                },
                "purpose": {"type": "string", "description": "一句话用途标签。"},
                "max_turns": {"type": "integer", "description": "可选轮次上限。"},
            },
            "required": ["task", "agent_type"],
            "additionalProperties": False,
        },
    )

    tools.register(
        "spawn_teammate",
        lambda name, role, prompt: runtime._get_team().spawn(name, role, prompt) if runtime._get_team() else {"status": "blocked", "reason": "agent_team_disabled"},
        description=(
            "召入一个持久队友，加入 agent team。"
            "队友有名字、职司、独立线程和 inbox；适合长期项目或固定角色协作。"
            "如果队友 offline，也用这个工具重新启动其线程。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "队友名字，例如 coder、reviewer、researcher。"},
                "role": {"type": "string", "description": "队友职司，例如 coder、reviewer、researcher。"},
                "prompt": {"type": "string", "description": "交给该队友的第一件差事。"},
            },
            "required": ["name", "role", "prompt"],
            "additionalProperties": False,
        },
    )
    tools.register(
        "list_teammates",
        lambda: runtime._get_team().list_all() if runtime._get_team() else {"status": "blocked", "reason": "agent_team_disabled"},
        description="列出 agent team 中所有队友的名字、职司、状态和线程是否存活。",
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
    )
    tools.register(
        "send_message",
        lambda to, content, msg_type="message": runtime._get_team().send_message(to, content, msg_type) if runtime._get_team() else {"status": "blocked", "reason": "agent_team_disabled"},
        description="给某位固定队友发送 inbox 消息。",
        input_schema={
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "content": {"type": "string"},
                "msg_type": {"type": "string", "enum": sorted(VALID_TEAM_MSG_TYPES)},
            },
            "required": ["to", "content"],
            "additionalProperties": False,
        },
    )
    tools.register(
        "read_inbox",
        lambda: runtime._get_team().read_lead_inbox() if runtime._get_team() else {"status": "blocked", "reason": "agent_team_disabled"},
        description="读取并清空 lead 自己的 inbox，用于查看队友回禀。",
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
    )
    tools.register(
        "broadcast",
        lambda content: runtime._get_team().broadcast(content) if runtime._get_team() else {"status": "blocked", "reason": "agent_team_disabled"},
        description="向所有固定队友广播一条消息。",
        input_schema={
            "type": "object",
            "properties": {"content": {"type": "string"}},
            "required": ["content"],
            "additionalProperties": False,
        },
    )
    tools.register(
        "shutdown_teammate",
        lambda name: runtime._get_team().shutdown_teammate(name) if runtime._get_team() else {"status": "blocked", "reason": "agent_team_disabled"},
        description="请求某位固定队友停止其后台线程。",
        input_schema={
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
            "additionalProperties": False,
        },
    )

    return runtime


def render_runtime_permission_status(runtime: AgentRuntime) -> str:
    memory_status = "disabled"
    memory_dir = ""
    if runtime.operator_memory_enabled() and runtime.operator_memory:
        memory_status = "enabled"
        memory_dir = str(runtime.operator_memory.memory_dir)
    lines = [
        "Runtime permission status:",
        f"- runtime_mode: {runtime.runtime_mode}",
        f"- llm_effective_model: {getattr(runtime.planner.llm, 'model', 'unknown')}",
        f"- openrouter_fallback: mode={DEFAULT_OPENROUTER_FALLBACK_MODE} | models={', '.join(DEFAULT_OPENROUTER_FALLBACK_MODELS) if DEFAULT_OPENROUTER_FALLBACK_MODELS else '(none)'}",
        f"- operator_memory: {memory_status}"
        + (f" | dir={memory_dir}" if memory_dir else ""),
        "- core_memory_write: /remember <text>"
        + (" + remember_note tool with explicit user intent" if runtime.operator_memory_enabled() else " only when operator memory is enabled"),
        "- layered_memory_commands: /memory_review, /memory_pin, /memory_unpin, /memory_archive, /forget",
        f"- file_read_tools: {'enabled' if {'read_file', 'glob_files', 'grep_files'}.issubset(runtime.gate.allowed_tools) else 'restricted'}",
        f"- file_write_proposals: {'enabled' if 'propose_file_write' in runtime.gate.allowed_tools else 'disabled'}",
        f"- web_fetch_policy: {current_web_fetch_policy()}",
        f"- web_fetch_proposals: {'enabled' if 'propose_web_fetch' in runtime.gate.allowed_tools else 'disabled'}",
        f"- heartbeat_proposals: {'enabled' if 'propose_heartbeat' in runtime.gate.allowed_tools else 'disabled'}",
        f"- write_file: {'trusted direct enabled' if DEFAULT_ENABLE_WRITE_FILE and 'write_file' in runtime.gate.allowed_tools else 'transaction approval required'}",
        f"- run_command: {'trusted direct enabled' if DEFAULT_ENABLE_RUN_COMMAND and 'run_command' in runtime.gate.allowed_tools else 'disabled'}",
        f"- web_fetch: {'safe public auto enabled' if safe_auto_web_fetch_enabled() and 'web_fetch' in runtime.gate.allowed_tools else ('trusted direct enabled' if DEFAULT_ENABLE_WEB_FETCH and 'web_fetch' in runtime.gate.allowed_tools else 'transaction approval required')}",
        f"- write_allowlist: {', '.join(DEFAULT_WRITE_ALLOWLIST) if DEFAULT_WRITE_ALLOWLIST else '(workspace-contained; no extra allowlist)'}",
        f"- allowed_roots: {', '.join(str(root) for root in _iter_allowed_roots())}",
        f"- tool_loop_budget: soft={DEFAULT_MAX_TOOL_LOOPS} | hard={DEFAULT_TOOL_LOOP_HARD_CAP}",
        f"- pending_approvals: {runtime.permission_broker.describe()['pending_count']}",
        f"- pending_heartbeats: {runtime.list_heartbeats().get('count', 0)}",
        "- subagent_side_effects: disabled; subagents may only report proposed_action",
        f"- workspace: {DEFAULT_AGENT_WORKSPACE}",
        f"- trace_path: {DEFAULT_TRACE_PATH}",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    runtime = build_demo_runtime(enable_operator_memory=env_flag("AGENT_MEMORY", True))

    print("EgoOperator CLI. Type 'exit' to quit.")
    print(f"LLM provider: {getattr(runtime.planner.llm, 'provider', 'unknown')} | model: {getattr(runtime.planner.llm, 'model', 'unknown')}")
    print(render_runtime_permission_status(runtime))
    while True:
        msg = input("> ").strip()
        if msg.lower() in {"exit", "quit"}:
            break
        if msg.lower() in {"/memory", "memory"}:
            print(runtime.memory.render())
            operator_context = runtime.render_operator_memory_context()
            if operator_context:
                print("\n" + operator_context)
            continue
        if msg.lower() in {"/mode", "mode"}:
            print(render_runtime_permission_status(runtime))
            continue
        if msg.lower() in {"/provider_status", "provider status"}:
            print(json.dumps(runtime.provider_status(), ensure_ascii=False, indent=2))
            continue
        if msg.lower().startswith("/mode "):
            print(json.dumps(runtime.set_runtime_mode(msg.split(maxsplit=1)[1]), ensure_ascii=False, indent=2))
            print(render_runtime_permission_status(runtime))
            continue
        if msg.lower() in {"/approvals", "approvals"}:
            print(json.dumps(runtime.list_pending_approvals(), ensure_ascii=False, indent=2))
            continue
        if msg.lower() in {"/heartbeats", "heartbeats"}:
            print(json.dumps(runtime.list_heartbeats(include_closed=True), ensure_ascii=False, indent=2))
            continue
        if msg.lower() in {"/heartbeat_due", "heartbeat_due"}:
            print(json.dumps(runtime.collect_due_heartbeat_candidates(), ensure_ascii=False, indent=2))
            continue
        if msg.lower().startswith("/cancel_heartbeat "):
            parts = msg.split(maxsplit=2)
            heartbeat_id = parts[1].strip() if len(parts) > 1 else ""
            reason = parts[2].strip() if len(parts) > 2 else "operator_cancelled"
            print(json.dumps(runtime.cancel_heartbeat(heartbeat_id, reason=reason), ensure_ascii=False, indent=2))
            continue
        if msg.lower().startswith("/approve "):
            proposal_id = msg.split(maxsplit=1)[1].strip()
            print(json.dumps(runtime.approve_pending_operation(proposal_id), ensure_ascii=False, indent=2))
            continue
        if msg.lower().startswith("/reject "):
            parts = msg.split(maxsplit=2)
            proposal_id = parts[1].strip() if len(parts) > 1 else ""
            reason = parts[2].strip() if len(parts) > 2 else "operator_rejected"
            print(json.dumps(runtime.reject_pending_operation(proposal_id, reason=reason), ensure_ascii=False, indent=2))
            continue
        if msg.lower().startswith("/edit_approval "):
            parts = msg.split(maxsplit=2)
            proposal_id = parts[1].strip() if len(parts) > 1 else ""
            raw_updates = parts[2].strip() if len(parts) > 2 else "{}"
            try:
                updates = json.loads(raw_updates)
            except json.JSONDecodeError as exc:
                print(json.dumps({"status": "failed", "reason": "invalid_json_updates", "error": str(exc)}, ensure_ascii=False, indent=2))
                continue
            if not isinstance(updates, dict):
                print(json.dumps({"status": "failed", "reason": "updates_must_be_json_object"}, ensure_ascii=False, indent=2))
                continue
            print(json.dumps(runtime.edit_pending_file_write(proposal_id, updates), ensure_ascii=False, indent=2))
            continue
        if msg.startswith("/remember "):
            print(json.dumps(runtime.remember_operator_note(msg.removeprefix("/remember ").strip()), ensure_ascii=False, indent=2))
            continue
        if msg.lower() in {"/memory_context", "memory context"}:
            context = runtime.render_operator_memory_context()
            print(context or "(operator memory empty or disabled)")
            continue
        if msg.lower().startswith("/memory_review"):
            parts = msg.split()
            limit = 20
            include_archived = "--all" in parts
            for part in parts[1:]:
                if part.isdigit():
                    limit = int(part)
                    break
            print(json.dumps(runtime.review_operator_memory(limit=limit, include_archived=include_archived), ensure_ascii=False, indent=2))
            continue
        if msg.startswith("/memory_pin "):
            print(json.dumps(runtime.pin_operator_memory(msg.removeprefix("/memory_pin ").strip()), ensure_ascii=False, indent=2))
            continue
        if msg.startswith("/memory_unpin "):
            print(json.dumps(runtime.unpin_operator_memory(msg.removeprefix("/memory_unpin ").strip()), ensure_ascii=False, indent=2))
            continue
        if msg.startswith("/memory_archive "):
            print(json.dumps(runtime.archive_operator_memory(msg.removeprefix("/memory_archive ").strip()), ensure_ascii=False, indent=2))
            continue
        if msg.startswith("/forget "):
            print(json.dumps(runtime.forget_operator_memory(msg.removeprefix("/forget ").strip()), ensure_ascii=False, indent=2))
            continue
        if msg.lower() in {"/compact_memory", "compact memory"}:
            print(json.dumps(runtime.force_compact_operator_memory(), ensure_ascii=False, indent=2))
            continue
        if msg.lower() in {"/system", "system"}:
            print(runtime.build_runtime_system_prompt())
            continue
        if msg.lower() in {"/skills", "skills"}:
            print(f"skills_dir: {SKILL_LOADER.skills_dir}")
            print(SKILL_LOADER.get_descriptions())
            continue
        if msg.lower() in {"/reload_skills", "reload skills"}:
            SKILL_LOADER.reload()
            print("[skills reloaded]")
            print(SKILL_LOADER.get_descriptions())
            continue
        if msg.lower() in {"/tools", "tools"}:
            print(json.dumps(runtime.tools.openai_tool_schemas(allowed_tool_names=runtime.gate.allowed_tools), ensure_ascii=False, indent=2))
            print(f"agent_team enabled: {DEFAULT_ENABLE_AGENT_TEAM}")
            print(render_runtime_permission_status(runtime))
            continue
        if msg.lower() in {"/subagents", "subagents"}:
            for name, spec in SUBAGENT_SPECS.items():
                print(f"- {name}: {spec.title} | {spec.duty} | tools={spec.allowed_tools} | max_turns={spec.max_turns}")
            continue
        if msg.lower() in {"/team", "team"}:
            team = runtime._get_team()
            print(json.dumps(team.list_all() if team else {"status": "blocked", "reason": "agent_team_disabled"}, ensure_ascii=False, indent=2))
            continue
        if msg.lower() in {"/inbox", "inbox"}:
            team = runtime._get_team()
            print(json.dumps(team.read_lead_inbox() if team else {"status": "blocked", "reason": "agent_team_disabled"}, ensure_ascii=False, indent=2))
            continue
        if msg.lower() in {"/team_dir", "team dir"}:
            print(f"team_dir: {DEFAULT_TEAM_DIR}")
            print(f"inbox_dir: {DEFAULT_TEAM_DIR / 'inbox'}")
            continue
        if msg.lower() in {"/todos", "todos", "plan"}:
            print(runtime.todo_list.render())
            continue
        if msg.lower() in {"/clear_todos", "clear todos", "/clear_plan"}:
            runtime.todo_list.clear()
            print("[todos cleared]")
            continue
        if msg.lower() in {"/clear_memory", "/clear", "clear memory"}:
            runtime.memory.clear()
            print("[in-session memory cleared; operator memory files were not modified]")
            continue
        result = runtime.handle_user_message(msg)
        print(result.reply_text)
