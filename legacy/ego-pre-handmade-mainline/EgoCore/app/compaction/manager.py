"""
Compaction Manager

统一入口，所有长内容先入 compactor。
"""

from __future__ import annotations
import logging
import hashlib
from typing import Optional, Dict, Any, List
from pathlib import Path

from .contracts import (
    CompactedArtifact,
    Capsule,
    ProseCapsule,
    CodeCapsule,
    LogCapsule,
    ToolResultCapsule,
    ChunkRef,
    SymbolRef,
    ContentType,
    CompactionPolicy,
    ReadRequest,
    ReadResult,
)

logger = logging.getLogger(__name__)

# 默认 artifact 根目录
DEFAULT_ARTIFACT_ROOT = "artifacts/compacted"


class CompactionManager:
    """
    压缩管理器
    
    统一处理所有长内容的语义压缩。
    Raw 保真保存，Capsule 入 prompt，Ref 进 history。
    """
    
    def __init__(self, root_dir: Optional[str] = None, policy: Optional[CompactionPolicy] = None):
        self.root = Path(root_dir or DEFAULT_ARTIFACT_ROOT)
        self.root.mkdir(parents=True, exist_ok=True)
        self.policy = policy or CompactionPolicy.default()
        self._cache: Dict[str, CompactedArtifact] = {}
    
    def compact(
        self,
        content: str,
        content_type: ContentType,
        session_key: str,
        original_filename: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CompactedArtifact:
        """
        压缩内容
        
        Args:
            content: 原始内容
            content_type: 内容类型
            session_key: 会话标识
            original_filename: 原始文件名
            metadata: 额外元数据
        
        Returns:
            CompactedArtifact 压缩后的 artifact
        """
        # 生成 artifact_id
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        artifact_id = f"artifact://compacted/{content_hash}"
        
        # 检查缓存
        if artifact_id in self._cache:
            return self._cache[artifact_id]
        
        # 落盘 raw
        raw_path = self._store_raw(content, session_key, content_hash)
        
        # 根据类型生成 Capsule
        capsule = self._generate_capsule(content, content_type, metadata)
        
        # 生成 chunk refs
        chunk_refs = self._generate_chunks(content, content_type)
        
        # 构建 artifact
        artifact = CompactedArtifact(
            artifact_id=artifact_id,
            content_type=content_type,
            raw_ref=f"artifact://raw/{content_hash}",
            original_filename=original_filename,
            size_bytes=len(content),
            line_count=len(content.splitlines()),
            chunk_refs=chunk_refs,
            capsule=capsule,
        )
        
        # 存储 capsule
        self._store_capsule(artifact, session_key, content_hash)
        
        # 缓存
        self._cache[artifact_id] = artifact
        
        logger.info(
            f"Compacted: {artifact_id} type={content_type.value} "
            f"size={len(content)} chunks={len(chunk_refs)}"
        )
        
        return artifact
    
    def compact_tool_result(
        self,
        tool_result: Dict[str, Any],
        session_key: str,
    ) -> CompactedArtifact:
        """
        压缩工具执行结果
        
        Args:
            tool_result: 工具执行结果
            session_key: 会话标识
        
        Returns:
            CompactedArtifact
        """
        # 提取关键信息
        stdout = tool_result.get("stdout", "")
        stderr = tool_result.get("stderr", "")
        
        # 生成 capsule
        capsule = LogCapsule(
            tool=tool_result.get("tool"),
            success=tool_result.get("success", True),
            exit_code=tool_result.get("exit_code"),
            cwd=tool_result.get("cwd"),
            timed_out=tool_result.get("timed_out", False),
            errors=self._extract_errors(stderr) if stderr else [],
            side_effects=tool_result.get("side_effects", []),
            output_files=tool_result.get("output_files", []),
            stdout_preview=stdout[:500] if stdout else None,
            stderr_preview=stderr[:200] if stderr else None,
        )
        
        # 生成 artifact
        content = f"STDOUT:\n{stdout}\n\nSTDERR:\n{stderr}"
        return self.compact(
            content=content,
            content_type=ContentType.TOOL_RESULT,
            session_key=session_key,
            metadata={"capsule": capsule},
        )
    
    def read(self, request: ReadRequest) -> ReadResult:
        """
        读取 artifact 内容
        
        Args:
            request: 读取请求
        
        Returns:
            ReadResult
        """
        artifact = self._cache.get(request.artifact_id)
        if not artifact:
            # 尝试从磁盘加载
            artifact = self._load_artifact(request.artifact_id)
        
        if not artifact:
            return ReadResult(
                success=False,
                error=f"Artifact not found: {request.artifact_id}",
            )
        
        if request.mode == "capsule":
            return ReadResult(
                success=True,
                content=artifact.to_prompt_text() if artifact.capsule else None,
                source_ref=artifact.capsule_ref,
            )
        
        if request.mode == "raw":
            content = self._read_raw(artifact)
            return ReadResult(
                success=content is not None,
                content=content,
                source_ref=artifact.raw_ref,
            )
        
        if request.mode == "chunk" and request.chunk_id:
            content = self._read_chunk(artifact, request.chunk_id)
            return ReadResult(
                success=content is not None,
                content=content,
                source_ref=f"{artifact.raw_ref}#chunk:{request.chunk_id}",
            )
        
        if request.mode == "lines" and request.line_start and request.line_end:
            content = self._read_lines(artifact, request.line_start, request.line_end)
            return ReadResult(
                success=content is not None,
                content=content,
                source_ref=f"{artifact.raw_ref}#lines:{request.line_start}-{request.line_end}",
            )
        
        if request.mode == "symbol" and request.symbol_name:
            content = self._read_symbol(artifact, request.symbol_name)
            return ReadResult(
                success=content is not None,
                content=content,
                source_ref=f"{artifact.raw_ref}#symbol:{request.symbol_name}",
            )
        
        return ReadResult(
            success=False,
            error=f"Invalid read mode: {request.mode}",
        )
    
    def _generate_capsule(
        self,
        content: str,
        content_type: ContentType,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Capsule:
        """根据内容类型生成 Capsule"""
        if metadata and "capsule" in metadata:
            return metadata["capsule"]
        
        if content_type == ContentType.PROSE:
            return self._generate_prose_capsule(content)
        elif content_type == ContentType.CODE:
            return self._generate_code_capsule(content)
        elif content_type == ContentType.LOG:
            return self._generate_log_capsule(content)
        elif content_type == ContentType.TOOL_RESULT:
            return self._generate_tool_result_capsule(content)
        else:
            return ProseCapsule(kind="unknown")
    
    def _generate_prose_capsule(self, content: str) -> ProseCapsule:
        """
        生成普通文本 Capsule
        
        简单规则提取：
        - 标题作为 goal
        - 包含"必须/不得/禁止"的行作为 hard_constraints
        - 包含"决定/确认"的行作为 decisions
        - 包含"风险/注意"的行作为 risks
        - 包含"待办/下一步"的行作为 action_items
        """
        lines = content.splitlines()
        
        goal = None
        hard_constraints = []
        decisions = []
        risks = []
        action_items = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 标题（第一行或 # 开头）
            if line.startswith("#") and not goal:
                goal = line.lstrip("#").strip()
                continue
            
            # 硬约束关键词
            if any(kw in line for kw in ["必须", "不得", "禁止", "不允许", "严禁", "hard"]):
                hard_constraints.append(line[:200])
                if len(hard_constraints) >= self.policy.max_constraints:
                    continue
            
            # 决定关键词
            if any(kw in line for kw in ["决定", "确认", "已确定", "decision"]):
                decisions.append(line[:200])
                if len(decisions) >= self.policy.max_decisions:
                    continue
            
            # 风险关键词
            if any(kw in line for kw in ["风险", "注意", "警告", "可能失败", "risk"]):
                risks.append(line[:200])
                if len(risks) >= self.policy.max_risks:
                    continue
            
            # 待办关键词
            if any(kw in line for kw in ["待办", "下一步", "TODO", "action"]):
                action_items.append(line[:200])
                if len(action_items) >= self.policy.max_action_items:
                    continue
        
        return ProseCapsule(
            goal=goal,
            hard_constraints=hard_constraints,
            decisions=decisions,
            risks=risks,
            action_items=action_items,
        )
    
    def _generate_code_capsule(self, content: str) -> CodeCapsule:
        """
        生成代码 Capsule
        
        提取 symbol 索引。
        """
        lines = content.splitlines()
        symbols = []
        
        for i, line in enumerate(lines):
            # Python function/class
            if line.strip().startswith(("def ", "class ", "async def ")):
                parts = line.strip().split("(")
                if len(parts) >= 1:
                    name = parts[0].replace("def ", "").replace("class ", "").replace("async ", "").strip()
                    symbol_type = "class" if "class " in line else "function"
                    symbols.append(SymbolRef(
                        name=name,
                        type=symbol_type,
                        line_start=i + 1,
                        line_end=i + 1,  # 需要更精确的结束行
                    ))
            
            # JavaScript/TypeScript function
            if "function " in line or "const " in line and "=>" in line:
                symbols.append(SymbolRef(
                    name=line.strip()[:50],
                    type="function",
                    line_start=i + 1,
                    line_end=i + 1,
                ))
        
        # 限制数量
        symbols = symbols[:self.policy.max_symbols]
        
        return CodeCapsule(
            language=self._detect_language(content),
            symbols=symbols,
        )
    
    def _generate_log_capsule(self, content: str) -> LogCapsule:
        """
        生成日志 Capsule
        
        提取错误和关键事件。
        """
        lines = content.splitlines()
        errors = []
        warnings = []
        key_events = []
        
        for line in lines:
            line_lower = line.lower()
            if "error" in line_lower or "failed" in line_lower or "exception" in line_lower:
                errors.append(line[:500])
                if len(errors) >= self.policy.max_errors:
                    continue
            elif "warning" in line_lower or "warn" in line_lower:
                warnings.append(line[:300])
            elif "success" in line_lower or "completed" in line_lower or "done" in line_lower:
                key_events.append({"type": "success", "line": line[:200]})
        
        return LogCapsule(
            errors=errors[:self.policy.max_errors],
            warnings=warnings[:self.policy.max_errors],
            key_events=key_events[:self.policy.max_events],
        )
    
    def _generate_tool_result_capsule(self, content: str) -> ToolResultCapsule:
        """生成工具结果 Capsule"""
        return ToolResultCapsule(
            stdout_preview=content[:500],
        )
    
    def _generate_chunks(self, content: str, content_type: ContentType) -> List[ChunkRef]:
        """生成 chunk refs"""
        if content_type == ContentType.CODE:
            # 代码按函数/类切
            return self._chunk_code(content)
        else:
            # 其他按段落切
            return self._chunk_prose(content)
    
    def _chunk_prose(self, content: str) -> List[ChunkRef]:
        """按段落切分"""
        lines = content.splitlines()
        chunks = []
        current_start = 0
        current_chars = 0
        
        for i, line in enumerate(lines):
            current_chars += len(line)
            
            # 段落结束
            if line.strip() == "" or current_chars >= self.policy.max_chunk_size:
                if i > current_start:
                    chunks.append(ChunkRef(
                        chunk_id=f"chunk_{len(chunks)}",
                        index=len(chunks),
                        line_start=current_start + 1,
                        line_end=i + 1,
                        char_count=current_chars,
                        preview="\n".join(lines[current_start:i+1])[:100],
                    ))
                current_start = i + 1
                current_chars = 0
        
        # 剩余内容
        if current_start < len(lines):
            chunks.append(ChunkRef(
                chunk_id=f"chunk_{len(chunks)}",
                index=len(chunks),
                line_start=current_start + 1,
                line_end=len(lines),
                char_count=current_chars,
                preview="\n".join(lines[current_start:])[:100],
            ))
        
        return chunks
    
    def _chunk_code(self, content: str) -> List[ChunkRef]:
        """代码按函数/类切分"""
        # 简化：按空行切
        return self._chunk_prose(content)
    
    def _extract_errors(self, stderr: str) -> List[str]:
        """提取错误信息"""
        errors = []
        for line in stderr.splitlines():
            if any(kw in line.lower() for kw in ["error", "failed", "exception", "traceback"]):
                errors.append(line[:500])
        return errors[:self.policy.max_errors]
    
    def _detect_language(self, content: str) -> Optional[str]:
        """检测语言"""
        first_line = content.splitlines()[0] if content else ""
        if first_line.startswith("#!") or "import " in content:
            return "python"
        if "function " in content or "const " in content:
            return "javascript"
        return None
    
    def _store_raw(self, content: str, session_key: str, content_hash: str) -> str:
        """
        存储 raw 文件（扁平化）
        
        全局最优方案：
        - 文件存储到 raw/{hash}.txt（不含 session_key）
        - 相同内容只存储一次（content-addressable）
        - 读取时 O(1) 直接定位
        """
        raw_dir = self.root / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        raw_path = raw_dir / f"{content_hash}.txt"
        
        # 去重：如果文件已存在，直接返回路径
        if not raw_path.exists():
            raw_path.write_text(content, encoding="utf-8")
            logger.debug(f"Stored raw: {raw_path}")
        else:
            logger.debug(f"Raw already exists (dedup): {raw_path}")
        
        return str(raw_path)
    
    def _store_capsule(self, artifact: CompactedArtifact, session_key: str, content_hash: str) -> str:
        """存储 capsule 文件"""
        import json
        safe_session = session_key.replace(":", "_").replace("/", "_")
        capsule_dir = self.root / "capsule" / safe_session
        capsule_dir.mkdir(parents=True, exist_ok=True)
        capsule_path = capsule_dir / f"{content_hash}.json"
        capsule_path.write_text(json.dumps(artifact.to_dict(), indent=2, ensure_ascii=False))
        return str(capsule_path)
    
    def _load_artifact(self, artifact_id: str) -> Optional[CompactedArtifact]:
        """从磁盘加载 artifact"""
        # 从缓存或 capsule 文件加载
        if artifact_id in self._cache:
            return self._cache[artifact_id]
        
        # 尝试从 capsule 文件加载
        content_hash = artifact_id.split("/")[-1]
        capsule_dir = self.root / "capsule"
        if capsule_dir.exists():
            for session_dir in capsule_dir.iterdir():
                if session_dir.is_dir():
                    capsule_path = session_dir / f"{content_hash}.json"
                    if capsule_path.exists():
                        try:
                            import json
                            data = json.loads(capsule_path.read_text())
                            artifact = CompactedArtifact.from_dict(data)
                            self._cache[artifact_id] = artifact
                            return artifact
                        except Exception:
                            pass
        return None
    
    def _read_raw(self, artifact: CompactedArtifact) -> Optional[str]:
        """
        读取 raw 内容（扁平化）
        
        全局最优方案：
        - 直接读取 raw/{hash}.txt
        - O(1) 复杂度，无需遍历
        """
        if artifact.raw_ref:
            # raw_ref 格式: artifact://raw/{content_hash}
            content_hash = artifact.raw_ref.split("/")[-1]
            raw_path = self.root / "raw" / f"{content_hash}.txt"
            
            if raw_path.exists():
                try:
                    return raw_path.read_text(encoding="utf-8")
                except Exception as e:
                    logger.warning(f"Failed to read raw {raw_path}: {e}")
        
        return None
    
    def _read_chunk(self, artifact: CompactedArtifact, chunk_id: str) -> Optional[str]:
        """读取指定 chunk"""
        for chunk in artifact.chunk_refs:
            if chunk.chunk_id == chunk_id:
                raw = self._read_raw(artifact)
                if raw:
                    lines = raw.splitlines()
                    return "\n".join(lines[chunk.line_start - 1:chunk.line_end])
        return None
    
    def _read_lines(self, artifact: CompactedArtifact, start: int, end: int) -> Optional[str]:
        """读取指定行"""
        raw = self._read_raw(artifact)
        if raw:
            lines = raw.splitlines()
            return "\n".join(lines[start - 1:end])
        return None
    
    def _read_symbol(self, artifact: CompactedArtifact, symbol_name: str) -> Optional[str]:
        """读取指定 symbol"""
        for symbol in artifact.symbol_refs:
            if symbol.name == symbol_name:
                return self._read_lines(artifact, symbol.line_start, symbol.line_end)
        return None


# 单例
_manager: Optional[CompactionManager] = None


def get_compaction_manager() -> CompactionManager:
    """获取全局 CompactionManager 实例"""
    global _manager
    if _manager is None:
        _manager = CompactionManager()
    return _manager
