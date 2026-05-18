"""
Runtime v2 Tool Broker

负责工具执行，包括：
- shell: 执行 shell 命令（带 artifact:// 禁止规则）
- file: 文件操作
- read_artifact: 读取 artifact 原文
- read_chunk: 读取 artifact chunk
- read_lines: 读取 artifact 行区间

Fail-fast 规则：
- shell 不能读取 artifact:// URI
- read_artifact 失败后立即返回短错，不进入循环
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict

from app.config import get_config, load_config
from app.tools import execute_tool, setup_tools
from app.ingestion.artifact_store import get_artifact_store
from app.compaction import get_compaction_manager, ReadRequest

from .contracts import ToolExecutionResult

logger = logging.getLogger(__name__)

# Fail-fast 错误消息模板
ARTIFACT_SHELL_BLOCKED = (
    "artifact:// URI 不能通过 shell 直接读取。"
    "请使用 read_artifact(artifact_id) 工具。"
)

ARTIFACT_NOT_FOUND = (
    "artifact_ref 已存在，但读取失败。"
    "可能原因：artifact 未正确存储或 resolver 未配置。"
)

ARTIFACT_READ_FAIL_FAST = (
    "artifact 读取失败，已终止尝试。"
    "请检查 artifact_id 是否正确，或提供明确可读路径。"
)


class RuntimeV2ToolBroker:
    """
    Runtime v2 工具代理

    支持：
    - shell: 执行 shell 命令（带 artifact:// 禁止规则）
    - file: 文件操作
    - read_artifact: 读取 artifact 原文
    - read_chunk: 读取 artifact chunk
    - read_lines: 读取 artifact 行区间
    """

    def __init__(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        try:
            cfg = get_config()
        except Exception:
            cfg = load_config(
                config_dir=str(repo_root / "config"),
                env_file=str(repo_root / ".env"),
                validate=False,
            )
        setup_tools(cfg.get("tools", {}) if hasattr(cfg, "get") else {})
        # 两个 artifact 系统
        self.artifact_store = get_artifact_store()
        self.compaction_manager = get_compaction_manager()

    async def execute(self, tool: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        result = await self.execute_typed(tool, tool_input)
        return result.to_dict()

    async def execute_typed(self, tool: str, tool_input: Dict[str, Any]) -> ToolExecutionResult:
        """
        执行工具调用

        Fail-fast 规则：
        - shell 读取 artifact:// → 立即拒绝
        - read_artifact 失败 → 返回短错，不继续尝试
        """
        if tool == "shell":
            return await self._execute_shell(tool_input)
        elif tool == "file":
            return await self._execute_file(tool_input)
        elif tool == "read_artifact":
            return await self._execute_read_artifact(tool_input)
        elif tool == "read_chunk":
            return await self._execute_read_chunk(tool_input)
        elif tool == "read_lines":
            return await self._execute_read_lines(tool_input)
        else:
            return ToolExecutionResult(
                success=False,
                tool=tool,
                stdout="",
                stderr=f"unsupported tool: {tool}",
                exit_code=-1,
                cwd=tool_input.get("cwd") if isinstance(tool_input, dict) else None,
                timed_out=False,
                truncated=False,
                metadata={},
                raw={},
            )

    async def _execute_shell(self, tool_input: Dict[str, Any]) -> ToolExecutionResult:
        """
        执行 shell 命令

        Fail-fast: 禁止 shell 直接读取 artifact:// URI
        """
        command = tool_input.get("command", "")

        # Fail-fast 规则：禁止 shell 读取 artifact://
        if "artifact://" in command:
            logger.warning(f"Shell blocked: attempted to read artifact:// URI")
            return ToolExecutionResult(
                success=False,
                tool="shell",
                stdout="",
                stderr=ARTIFACT_SHELL_BLOCKED,
                exit_code=-2,  # 特殊 exit code 表示被禁止
                cwd=tool_input.get("cwd"),
                timed_out=False,
                truncated=False,
                metadata={"blocked": True, "reason": "artifact_uri_in_shell"},
                raw={},
            )

        params = {
            "command": command,
            "working_dir": tool_input.get("cwd"),
            "timeout_seconds": tool_input.get("timeout_sec", 20),
        }
        result = await asyncio.to_thread(execute_tool, "shell", params, None, "runtime_v2_shell")
        data = result.to_dict()
        metadata = dict(data.get("metadata") or {})
        return ToolExecutionResult(
            success=bool(data.get("success")),
            tool="shell",
            stdout=str(data.get("output") or ""),
            stderr=str(data.get("error") or ""),
            exit_code=int(metadata.get("exit_code", 0 if data.get("success") else 1)),
            cwd=params.get("working_dir"),
            timed_out=bool(metadata.get("timed_out") or metadata.get("timeout") or False),
            truncated=bool(metadata.get("truncated") or metadata.get("truncated_output") or False),
            metadata=metadata,
            raw=data,
        )

    async def _execute_file(self, tool_input: Dict[str, Any]) -> ToolExecutionResult:
        """执行文件操作"""
        result = await asyncio.to_thread(execute_tool, "file", tool_input, None, "runtime_v2_file")
        data = result.to_dict()
        metadata = dict(data.get("metadata") or {})
        return ToolExecutionResult(
            success=bool(data.get("success")),
            tool="file",
            stdout=str(data.get("output") or ""),
            stderr=str(data.get("error") or ""),
            exit_code=int(metadata.get("exit_code", 0 if data.get("success") else 1)),
            cwd=tool_input.get("cwd") or tool_input.get("path"),
            timed_out=bool(metadata.get("timed_out") or metadata.get("timeout") or False),
            truncated=bool(metadata.get("truncated") or metadata.get("truncated_output") or False),
            metadata=metadata,
            raw=data,
        )

    async def _execute_read_artifact(self, tool_input: Dict[str, Any]) -> ToolExecutionResult:
        """
        读取 artifact 原文

        支持：
        - artifact://compacted/... → CompactionManager
        - artifact://ingested/... → ArtifactStore

        Fail-fast: 读取失败立即返回短错，不继续尝试
        """
        artifact_id = tool_input.get("artifact_id") or tool_input.get("artifact_ref")

        if not artifact_id:
            return ToolExecutionResult(
                success=False,
                tool="read_artifact",
                stdout="",
                stderr="缺少 artifact_id 参数",
                exit_code=-1,
                timed_out=False,
                truncated=False,
                metadata={},
                raw={},
            )

        # 验证 artifact_id 格式
        if not artifact_id.startswith("artifact://"):
            return ToolExecutionResult(
                success=False,
                tool="read_artifact",
                stdout="",
                stderr=f"无效的 artifact_id 格式: {artifact_id}。应为 artifact://...",
                exit_code=-1,
                timed_out=False,
                truncated=False,
                metadata={},
                raw={},
            )

        # 尝试读取
        try:
            content = None

            # 根据 prefix 判断使用哪个系统
            if artifact_id.startswith("artifact://compacted/"):
                # 使用 CompactionManager
                request = ReadRequest(artifact_id=artifact_id, mode="raw")
                result = self.compaction_manager.read(request)
                if result.success:
                    content = result.content

            elif artifact_id.startswith("artifact://ingested/"):
                # 使用 ArtifactStore
                content = self.artifact_store.read_raw(artifact_id)

            if content is None:
                # Fail-fast: 读不到就返回短错
                logger.warning(f"Artifact read failed: {artifact_id}")
                return ToolExecutionResult(
                    success=False,
                    tool="read_artifact",
                    stdout="",
                    stderr=ARTIFACT_READ_FAIL_FAST,
                    exit_code=-1,
                    timed_out=False,
                    truncated=False,
                    metadata={"artifact_id": artifact_id, "reason": "not_found"},
                    raw={},
                )

            # 成功读取
            # 截断超长内容（保留 50KB）
            max_len = 50 * 1024
            truncated = len(content) > max_len
            if truncated:
                content = content[:max_len] + "\n... [截断]"

            return ToolExecutionResult(
                success=True,
                tool="read_artifact",
                stdout=content,
                stderr="",
                exit_code=0,
                timed_out=False,
                truncated=truncated,
                metadata={"artifact_id": artifact_id, "chars": len(content)},
                raw={"artifact_id": artifact_id},
            )

        except Exception as e:
            logger.exception(f"Artifact read error: {artifact_id} - {e}")
            return ToolExecutionResult(
                success=False,
                tool="read_artifact",
                stdout="",
                stderr=f"artifact 读取失败: {str(e)[:100]}",
                exit_code=-1,
                timed_out=False,
                truncated=False,
                metadata={"artifact_id": artifact_id, "error": str(e)},
                raw={},
            )

    async def _execute_read_chunk(self, tool_input: Dict[str, Any]) -> ToolExecutionResult:
        """
        读取 artifact chunk

        支持：
        - artifact://compacted/... → CompactionManager
        - artifact://ingested/... → ArtifactStore

        Fail-fast: 读取失败立即返回短错
        """
        artifact_id = tool_input.get("artifact_id") or tool_input.get("artifact_ref")
        chunk_id = tool_input.get("chunk_id") or tool_input.get("chunk")

        if not artifact_id or not chunk_id:
            return ToolExecutionResult(
                success=False,
                tool="read_chunk",
                stdout="",
                stderr="缺少 artifact_id 或 chunk_id 参数",
                exit_code=-1,
                timed_out=False,
                truncated=False,
                metadata={},
                raw={},
            )

        try:
            content = None

            if artifact_id.startswith("artifact://compacted/"):
                request = ReadRequest(artifact_id=artifact_id, mode="chunk", chunk_id=chunk_id)
                result = self.compaction_manager.read(request)
                if result.success:
                    content = result.content

            elif artifact_id.startswith("artifact://ingested/"):
                content = self.artifact_store.read_chunk(artifact_id, chunk_id)

            if content is None:
                logger.warning(f"Chunk read failed: {artifact_id}/{chunk_id}")
                return ToolExecutionResult(
                    success=False,
                    tool="read_chunk",
                    stdout="",
                    stderr=f"chunk {chunk_id} 不存在或不可读",
                    exit_code=-1,
                    timed_out=False,
                    truncated=False,
                    metadata={"artifact_id": artifact_id, "chunk_id": chunk_id},
                    raw={},
                )

            return ToolExecutionResult(
                success=True,
                tool="read_chunk",
                stdout=content,
                stderr="",
                exit_code=0,
                timed_out=False,
                truncated=False,
                metadata={"artifact_id": artifact_id, "chunk_id": chunk_id, "chars": len(content)},
                raw={"artifact_id": artifact_id, "chunk_id": chunk_id},
            )

        except Exception as e:
            logger.exception(f"Chunk read error: {artifact_id}/{chunk_id} - {e}")
            return ToolExecutionResult(
                success=False,
                tool="read_chunk",
                stdout="",
                stderr=f"chunk 读取失败: {str(e)[:100]}",
                exit_code=-1,
                timed_out=False,
                truncated=False,
                metadata={"artifact_id": artifact_id, "chunk_id": chunk_id, "error": str(e)},
                raw={},
            )

    async def _execute_read_lines(self, tool_input: Dict[str, Any]) -> ToolExecutionResult:
        """
        读取 artifact 行区间

        支持：
        - artifact://compacted/... → CompactionManager
        - artifact://ingested/... → ArtifactStore

        Fail-fast: 读取失败立即返回短错
        """
        artifact_id = tool_input.get("artifact_id") or tool_input.get("artifact_ref")
        line_start = tool_input.get("line_start") or tool_input.get("start")
        line_end = tool_input.get("line_end") or tool_input.get("end")

        if not artifact_id:
            return ToolExecutionResult(
                success=False,
                tool="read_lines",
                stdout="",
                stderr="缺少 artifact_id 参数",
                exit_code=-1,
                timed_out=False,
                truncated=False,
                metadata={},
                raw={},
            )

        if line_start is None or line_end is None:
            return ToolExecutionResult(
                success=False,
                tool="read_lines",
                stdout="",
                stderr="缺少 line_start 或 line_end 参数",
                exit_code=-1,
                timed_out=False,
                truncated=False,
                metadata={},
                raw={},
            )

        try:
            content = None

            if artifact_id.startswith("artifact://compacted/"):
                request = ReadRequest(
                    artifact_id=artifact_id,
                    mode="lines",
                    line_start=int(line_start),
                    line_end=int(line_end),
                )
                result = self.compaction_manager.read(request)
                if result.success:
                    content = result.content

            elif artifact_id.startswith("artifact://ingested/"):
                content = self.artifact_store.read_lines(artifact_id, int(line_start), int(line_end))

            if content is None:
                logger.warning(f"Lines read failed: {artifact_id}[{line_start}-{line_end}]")
                return ToolExecutionResult(
                    success=False,
                    tool="read_lines",
                    stdout="",
                    stderr=f"行区间 {line_start}-{line_end} 不存在或不可读",
                    exit_code=-1,
                    timed_out=False,
                    truncated=False,
                    metadata={"artifact_id": artifact_id, "line_start": line_start, "line_end": line_end},
                    raw={},
                )

            return ToolExecutionResult(
                success=True,
                tool="read_lines",
                stdout=content,
                stderr="",
                exit_code=0,
                timed_out=False,
                truncated=False,
                metadata={
                    "artifact_id": artifact_id,
                    "line_start": line_start,
                    "line_end": line_end,
                    "chars": len(content),
                },
                raw={"artifact_id": artifact_id, "line_start": line_start, "line_end": line_end},
            )

        except Exception as e:
            logger.exception(f"Lines read error: {artifact_id}[{line_start}-{line_end}] - {e}")
            return ToolExecutionResult(
                success=False,
                tool="read_lines",
                stdout="",
                stderr=f"行区间读取失败: {str(e)[:100]}",
                exit_code=-1,
                timed_out=False,
                truncated=False,
                metadata={"artifact_id": artifact_id, "error": str(e)},
                raw={},
            )
