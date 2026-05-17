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
from datetime import datetime, timezone
from enum import Enum
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Deque, Dict, List, Optional, Protocol
import hashlib
import json
import os
import re
import shlex
import subprocess
import threading
import sys
import time
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
except ImportError:  # allow `python Ego_handmade/agent_base.py`
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
EGO_HANDMADE_ROOT = Path(__file__).resolve().parent


def env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


DEFAULT_LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openrouter")
DEFAULT_OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")  # or paste temporarily: "<OPENROUTER_API_KEY>"
DEFAULT_OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-v4-flash")
DEFAULT_OPENROUTER_BASE_URL = os.getenv(
    "OPENROUTER_BASE_URL",
    "https://openrouter.ai/api/v1/chat/completions",
)
# Optional OpenRouter headers. Leave blank if you do not need leaderboard/referrer metadata.
DEFAULT_OPENROUTER_SITE_URL = os.getenv("OPENROUTER_SITE_URL", "")
DEFAULT_OPENROUTER_APP_NAME = os.getenv("OPENROUTER_APP_NAME", "EGO Agent Base")
DEFAULT_MEMORY_MAX_MESSAGES = int(os.getenv("AGENT_MEMORY_MAX_MESSAGES", "20"))
DEFAULT_MEMORY_MAX_CHARS_PER_MESSAGE = int(os.getenv("AGENT_MEMORY_MAX_CHARS_PER_MESSAGE", "2000"))
DEFAULT_MAX_TOOL_LOOPS = int(os.getenv("AGENT_MAX_TOOL_LOOPS", "4"))
DEFAULT_VERBOSE_TOOLS = env_flag("AGENT_VERBOSE_TOOLS", True)
DEFAULT_VERBOSE_TODOS = env_flag("AGENT_VERBOSE_TODOS", True)
DEFAULT_VERBOSE_SUBAGENTS = env_flag("AGENT_VERBOSE_SUBAGENTS", True)
DEFAULT_ENABLE_WEB_FETCH = env_flag("AGENT_ENABLE_WEB_FETCH", False)
DEFAULT_ENABLE_WRITE_FILE = env_flag("AGENT_ENABLE_WRITE_FILE", False)
DEFAULT_AGENT_WORKSPACE = Path(os.getenv("AGENT_WORKSPACE", str(EGO_HANDMADE_ROOT))).resolve()
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
    os.getenv("AGENT_TRACE_PATH", str(EGO_HANDMADE_ROOT / "artifacts" / "agent_trace.jsonl"))
).resolve()

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
    r"以后记得",
    r"以后请记得",
    r"把.{0,20}记下来",
    r"记录到记忆",
    r"写入记忆",
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
        + "\n16. read_file / glob_files / grep_files 是 workspace 内只读工具；需要查看本地文件时优先使用它们，不要假装已经读取。"
        + "\n17. write_file、run_command、web_fetch 只有在对应工具出现在工具列表且 gate 允许时才可使用；未出现时必须说明当前禁用。"
        + "\n18. remember_note 只能在用户明确要求“记住/记一下/以后记得/remember”时调用；普通聊天、工具结果、子代理回禀和自动总结不能写 core memory。"
        + "\n19. operator memory 是 Ego_handmade candidate-local 记忆，不是 PROJECT_MEMORY、OpenEmotion 记忆或 EGO evidence ledger。"
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



def _resolve_workspace_path(path: str) -> Path:
    """
    Resolve a user-supplied path under DEFAULT_AGENT_WORKSPACE.

    Absolute paths are allowed only if they are already inside the workspace.
    This prevents a subagent from casually reading/writing arbitrary system files.
    """
    raw = Path(str(path or ".")).expanduser()
    candidate = raw if raw.is_absolute() else DEFAULT_AGENT_WORKSPACE / raw
    resolved = candidate.resolve()

    try:
        resolved.relative_to(DEFAULT_AGENT_WORKSPACE)
    except ValueError as exc:
        raise ValueError(f"path outside workspace: {resolved}") from exc

    return resolved


def _has_explicit_memory_write_intent(text: str) -> bool:
    raw = (text or "").strip()
    if not raw:
        return False
    lowered = raw.lower()
    return any(re.search(pattern, lowered, flags=re.IGNORECASE) for pattern in MEMORY_WRITE_INTENT_PATTERNS)


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
        if not pattern or ".." in Path(pattern).parts:
            return {"status": "blocked", "reason": "invalid_pattern", "pattern": pattern}
        matches = []
        for p in DEFAULT_AGENT_WORKSPACE.glob(pattern):
            try:
                rel = str(p.resolve().relative_to(DEFAULT_AGENT_WORKSPACE))
            except ValueError:
                continue
            matches.append(rel + ("/" if p.is_dir() else ""))
            if len(matches) >= max_results:
                break
        return {"status": "ok", "workspace": str(DEFAULT_AGENT_WORKSPACE), "matches": sorted(matches), "truncated": len(matches) >= max_results}
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
                            "path": str(file_path.resolve().relative_to(DEFAULT_AGENT_WORKSPACE)),
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


def web_fetch_tool(url: str, extract_mode: str = "text", max_chars: int = DEFAULT_WEB_FETCH_MAX_CHARS) -> Dict[str, Any]:
    if not DEFAULT_ENABLE_WEB_FETCH:
        return {
            "status": "blocked",
            "reason": "web_fetch_disabled",
            "hint": "Set AGENT_ENABLE_WEB_FETCH=1 to allow outbound HTTP reads.",
        }
    try:
        if not re.match(r"^https?://", url or ""):
            return {"status": "blocked", "reason": "only_http_https_allowed", "url": url}
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        if extract_mode == "raw":
            content = raw
        else:
            parser = _TextExtractor()
            parser.feed(raw)
            content = parser.get_text()
        limit = max(0, min(max_chars, DEFAULT_WEB_FETCH_MAX_CHARS))
        return {"status": "ok", "url": url, "content": content[:limit], "truncated": len(content) > limit}
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
        boundary="只读不写；联网读取必须被 runtime gate 允许，不能改动本地文件。",
        allowed_tools=["current_time", "web_fetch", "load_skill", "read_file", "glob_files", "grep_files"],
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
        boundary="可读写可执行；但写文件、命令、联网仍必须通过 runtime gate 和环境变量开关。",
        allowed_tools=["current_time", "run_command", "web_fetch", "load_skill", "read_file", "write_file", "glob_files", "grep_files"],
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
      export OPENROUTER_MODEL="deepseek/deepseek-v4-flash"
    """
    provider: str = DEFAULT_LLM_PROVIDER
    api_key: str = DEFAULT_OPENROUTER_API_KEY
    model: str = DEFAULT_OPENROUTER_MODEL
    base_url: str = DEFAULT_OPENROUTER_BASE_URL
    stream: bool = True
    timeout_seconds: int = 90
    site_url: str = DEFAULT_OPENROUTER_SITE_URL
    app_name: str = DEFAULT_OPENROUTER_APP_NAME
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
        self.model = self.config.model
        self.last_usage: Dict[str, Any] = {}
        self.last_reasoning_tokens: Optional[int] = None

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
            "model": self.config.model,
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

        if use_stream:
            return LLMChatResult(content=self._complete_streaming(payload, headers))
        return self._chat_non_streaming(payload, headers)

    def _chat_non_streaming(self, payload: Dict[str, Any], headers: Dict[str, str]) -> LLMChatResult:
        assert requests is not None
        resp = requests.post(
            self.config.base_url,
            headers=headers,
            json=payload,
            timeout=self.config.timeout_seconds,
        )
        resp.raise_for_status()
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
        resp.raise_for_status()
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
            resp.raise_for_status()

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
                "fallback_used": True,
            }
        else:
            self.last_llm_meta = {
                "provider": getattr(self.llm, "provider", "unknown"),
                "model": getattr(self.llm, "model", "unknown"),
                "usage": getattr(self.llm, "last_usage", {}),
                "reasoning_tokens": getattr(self.llm, "last_reasoning_tokens", None),
                "fallback_used": False,
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

    def __init__(self, allowed_tools: Optional[List[str]] = None) -> None:
        self.allowed_tools = set(allowed_tools or ["current_time"])

    def check(self, event: AgentEvent, action: AgentAction) -> GateResult:
        risk = event.safety_context.get("risk", "low")

        if action.action_type == ActionType.TOOL_CALL:
            if not action.tool_call:
                return GateResult(False, "missing_tool_call")
            if action.tool_call.tool_name not in self.allowed_tools:
                return GateResult(False, f"tool_not_allowed:{action.tool_call.tool_name}")
            if risk == "high":
                return GateResult(False, "high_risk_tool_call_blocked")
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
            if action.tool_call.tool_name == "web_fetch" and not DEFAULT_ENABLE_WEB_FETCH:
                return GateResult(False, "web_fetch_disabled")
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
        self.session_id = new_id("session")
        self.subagent_counter = 0
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
            for loop_idx in range(DEFAULT_MAX_TOOL_LOOPS):
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
                    "usage": getattr(llm, "last_usage", {}),
                    "reasoning_tokens": getattr(llm, "last_reasoning_tokens", None),
                    "fallback_used": False,
                    "tool_loop": True,
                    "loop_idx": loop_idx,
                }

                if not result.tool_calls:
                    final_action = AgentAction(
                        action_type=ActionType.RESPOND,
                        content=result.content,
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
                    return final_action, final_gate, last_external_result, result.content, tool_trace

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
                    candidate = AgentAction(
                        action_type=ActionType.TOOL_CALL,
                        tool_call=ToolCall(tool_name=call.name, args=call.arguments),
                        reason="llm_requested_tool_call",
                    )
                    gate_result = self.gate.check(event, candidate)

                    if DEFAULT_VERBOSE_TOOLS:
                        print(f"[执行工具]: {call.name} {json.dumps(call.arguments, ensure_ascii=False)}")

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

                    if DEFAULT_VERBOSE_TOOLS:
                        print(f"[工具输出]: {json.dumps(to_jsonable(tool_output), ensure_ascii=False)[:1200]}")

                    trace_entry = {
                        "loop_idx": loop_idx,
                        "tool_call": {
                            "id": call.id,
                            "name": call.name,
                            "arguments": call.arguments,
                        },
                        "gate": gate_result,
                        "output": tool_output,
                    }
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

            content = "工具调用循环超过上限，已停止继续调用。"
            action = AgentAction(action_type=ActionType.BLOCK, content=content, reason="tool_loop_limit")
            gate = GateResult(False, "tool_loop_limit")
            return action, gate, {"status": "blocked", "reason": "tool_loop_limit"}, content, tool_trace

        except Exception as exc:
            self.planner.last_llm_meta = {
                "provider": getattr(llm, "provider", "unknown"),
                "model": getattr(llm, "model", "unknown"),
                "error": repr(exc),
                "fallback_used": True,
                "tool_loop": True,
            }
            return None


# -----------------------------
# Demo
# -----------------------------

def build_llm_from_config() -> LLMClient:
    """
    LLM factory.

    For real OpenRouter calls, set:
      export OPENROUTER_API_KEY="sk-or-..."
      export OPENROUTER_MODEL="deepseek/deepseek-v4-flash"

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
            system_prompt=build_system_prompt(),
            # Example if you want reasoning metadata on supported models:
            # reasoning={"effort": "low", "exclude": False},
            reasoning=None,
        ))
    return NoLLM()


def build_operator_memory_store(memory_dir: Optional[str | Path] = None) -> OperatorMemoryStore:
    raw_target = Path(memory_dir) if memory_dir is not None else Path(os.getenv("AGENT_MEMORY_DIR", str(EGO_HANDMADE_ROOT / "memory")))
    target = raw_target if raw_target.is_absolute() else EGO_HANDMADE_ROOT / raw_target
    return OperatorMemoryStore(target, containment_root=EGO_HANDMADE_ROOT)


def build_operator_memory_from_env(*, default_enabled: bool) -> Optional[OperatorMemoryStore]:
    if not env_flag("AGENT_MEMORY", default_enabled):
        return None
    return build_operator_memory_store()


def build_demo_runtime(
    *,
    enable_operator_memory: bool = False,
    operator_memory_dir: Optional[str | Path] = None,
    subject_context_enabled: bool = True,
) -> AgentRuntime:
    tools = ToolRegistry()

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
        description="获取指定 URL 的网页内容，支持 text/raw；默认关闭，需 AGENT_ENABLE_WEB_FETCH=1。",
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
        description=f"读取 workspace 内文件内容。workspace={DEFAULT_AGENT_WORKSPACE}",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "workspace 内相对路径。"},
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
        description="按 glob 模式搜索 workspace 内文件。",
        input_schema={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "例如 **/*.py 或 skills/**/SKILL.md。"},
                "max_results": {"type": "integer", "description": "最大结果数。"},
            },
            "required": ["pattern"],
            "additionalProperties": False,
        },
    )
    tools.register(
        "grep_files",
        grep_files_tool,
        description="在 workspace 内文本文件中搜索正则 pattern。",
        input_schema={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Python 正则表达式。"},
                "path": {"type": "string", "description": "workspace 内路径，默认 .。"},
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

    # Main agent sees low-risk read tools by default. Side-effect tools stay opt-in.
    allowed_tools = [
        "current_time",
        "read_file",
        "glob_files",
        "grep_files",
        "load_skill",
        "update_todos",
        "dispatch_subagent",
    ]
    if DEFAULT_ENABLE_RUN_COMMAND:
        allowed_tools.append("run_command")
    if DEFAULT_ENABLE_WEB_FETCH:
        allowed_tools.append("web_fetch")
    if DEFAULT_ENABLE_WRITE_FILE:
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
    gate = SafetyGate(allowed_tools=allowed_tools)
    runtime = AgentRuntime(
        tools=tools,
        planner=planner,
        gate=gate,
        todo_list=todo_list,
        operator_memory=operator_memory,
        subject_context_enabled=subject_context_enabled,
    )

    tools.register(
        "remember_note",
        runtime.remember_operator_note,
        description=(
            "把用户明确要求记住的内容写入 Ego_handmade candidate-local MEMORY.md。"
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
        f"- operator_memory: {memory_status}"
        + (f" | dir={memory_dir}" if memory_dir else ""),
        "- core_memory_write: /remember <text>"
        + (" + remember_note tool with explicit user intent" if runtime.operator_memory_enabled() else " only when operator memory is enabled"),
        "- layered_memory_commands: /memory_review, /memory_pin, /memory_unpin, /memory_archive, /forget",
        f"- file_read_tools: {'enabled' if {'read_file', 'glob_files', 'grep_files'}.issubset(runtime.gate.allowed_tools) else 'restricted'}",
        f"- write_file: {'enabled' if DEFAULT_ENABLE_WRITE_FILE and 'write_file' in runtime.gate.allowed_tools else 'disabled'}",
        f"- run_command: {'enabled' if DEFAULT_ENABLE_RUN_COMMAND and 'run_command' in runtime.gate.allowed_tools else 'disabled'}",
        f"- web_fetch: {'enabled' if DEFAULT_ENABLE_WEB_FETCH and 'web_fetch' in runtime.gate.allowed_tools else 'disabled'}",
        f"- workspace: {DEFAULT_AGENT_WORKSPACE}",
        f"- trace_path: {DEFAULT_TRACE_PATH}",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    runtime = build_demo_runtime(enable_operator_memory=env_flag("AGENT_MEMORY", True))

    print("Agent demo. Type 'exit' to quit.")
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
