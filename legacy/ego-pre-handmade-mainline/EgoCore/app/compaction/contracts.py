"""
Semantic Compaction Contracts v1.0.0

三层表示模型：
- Raw Layer: 完整原文，保真保存
- Index Layer: 结构索引（标题树、chunk、symbol）
- Capsule Layer: 压缩表示，进 prompt

原则：
- Raw 保真，Capsule 入 prompt，Ref 进 history
- 代码保 span，普通文字保语义
- 细节按需回读
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Literal
from enum import Enum
import time
import hashlib


# ============================================================================
# Content Types
# ============================================================================

class ContentType(Enum):
    """内容类型"""
    PROSE = "prose"           # 普通文字（md, txt）
    CODE = "code"             # 代码文件
    LOG = "log"               # 日志/shell 输出
    TOOL_RESULT = "tool_result"  # 工具执行结果
    STRUCTURED = "structured" # 结构化数据（json, yaml）


# ============================================================================
# Reference Types
# ============================================================================

@dataclass
class ChunkRef:
    """Chunk 引用"""
    chunk_id: str
    index: int
    line_start: int
    line_end: int
    char_count: int
    heading: Optional[str] = None
    preview: Optional[str] = None  # 前 100 字符
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "index": self.index,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "char_count": self.char_count,
            "heading": self.heading,
            "preview": self.preview,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChunkRef":
        return cls(**data)


@dataclass
class SymbolRef:
    """Symbol 引用（代码专用）"""
    name: str
    type: str  # function, class, variable, route, etc.
    line_start: int
    line_end: int
    language: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "language": self.language,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SymbolRef":
        return cls(**data)


@dataclass
class SpanRef:
    """Span 引用（代码关键段）"""
    span_id: str
    line_start: int
    line_end: int
    reason: Optional[str] = None  # 为什么这个 span 重要
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "span_id": self.span_id,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "reason": self.reason,
        }


# ============================================================================
# Capsule Types
# ============================================================================

@dataclass
class Capsule:
    """
    Capsule 基类
    
    给 Runtime 的压缩表示。只包含任务相关关键信息。
    """
    kind: str
    created_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {"kind": self.kind, "created_at": self.created_at}
    
    def to_prompt_text(self) -> str:
        """生成注入到 prompt 的文本"""
        raise NotImplementedError


@dataclass
class ProseCapsule(Capsule):
    """
    普通文字 Capsule
    
    只包含：
    - 目标
    - 硬约束
    - 决定
    - 风险
    - 待办
    - 相关 chunk ref
    """
    kind: str = "prose"
    goal: Optional[str] = None
    success_criteria: Optional[str] = None
    hard_constraints: List[str] = field(default_factory=list)
    decisions: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    open_questions: List[str] = field(default_factory=list)
    action_items: List[str] = field(default_factory=list)
    relevant_chunks: List[str] = field(default_factory=list)  # chunk_ids
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **super().to_dict(),
            "goal": self.goal,
            "success_criteria": self.success_criteria,
            "hard_constraints": self.hard_constraints,
            "decisions": self.decisions,
            "risks": self.risks,
            "open_questions": self.open_questions,
            "action_items": self.action_items,
            "relevant_chunks": self.relevant_chunks,
        }
    
    def to_prompt_text(self) -> str:
        lines = []
        if self.goal:
            lines.append(f"[目标] {self.goal}")
        if self.success_criteria:
            lines.append(f"[成功判据] {self.success_criteria}")
        if self.hard_constraints:
            lines.append("[硬约束]")
            for c in self.hard_constraints[:5]:
                lines.append(f"  - {c}")
        if self.decisions:
            lines.append("[决定]")
            for d in self.decisions[:5]:
                lines.append(f"  - {d}")
        if self.risks:
            lines.append("[风险]")
            for r in self.risks[:3]:
                lines.append(f"  - {r}")
        if self.action_items:
            lines.append("[待办]")
            for a in self.action_items[:5]:
                lines.append(f"  - {a}")
        return "\n".join(lines)


@dataclass
class CodeCapsule(Capsule):
    """
    代码 Capsule
    
    结构保真：保留 symbol 索引和相关 span。
    """
    kind: str = "code"
    language: Optional[str] = None
    file_path: Optional[str] = None
    symbols: List[SymbolRef] = field(default_factory=list)
    relevant_spans: List[SpanRef] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    entry_points: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **super().to_dict(),
            "language": self.language,
            "file_path": self.file_path,
            "symbols": [s.to_dict() for s in self.symbols],
            "relevant_spans": [s.to_dict() for s in self.relevant_spans],
            "dependencies": self.dependencies,
            "entry_points": self.entry_points,
        }
    
    def to_prompt_text(self) -> str:
        lines = []
        if self.file_path:
            lines.append(f"[代码文件] {self.file_path}")
        if self.language:
            lines.append(f"[语言] {self.language}")
        if self.symbols:
            lines.append(f"[Symbols] {len(self.symbols)} 个")
            for s in self.symbols[:10]:
                lines.append(f"  - {s.type} {s.name} (L{s.line_start}-{s.line_end})")
        if self.relevant_spans:
            lines.append(f"[关键段] {len(self.relevant_spans)} 个")
        return "\n".join(lines)


@dataclass
class LogCapsule(Capsule):
    """
    日志/shell 输出 Capsule
    
    事件化压缩：错误保真，正常日志压缩。
    """
    kind: str = "log"
    exit_code: Optional[int] = None
    success: bool = True
    timed_out: bool = False
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    side_effects: List[str] = field(default_factory=list)
    key_events: List[Dict[str, Any]] = field(default_factory=list)
    output_files: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **super().to_dict(),
            "exit_code": self.exit_code,
            "success": self.success,
            "timed_out": self.timed_out,
            "errors": self.errors,
            "warnings": self.warnings,
            "side_effects": self.side_effects,
            "key_events": self.key_events,
            "output_files": self.output_files,
        }
    
    def to_prompt_text(self) -> str:
        lines = []
        status = "成功" if self.success else f"失败(exit={self.exit_code})"
        lines.append(f"[执行结果] {status}")
        if self.timed_out:
            lines.append("[超时]")
        if self.errors:
            lines.append(f"[错误] {len(self.errors)} 个")
            for e in self.errors[:3]:
                lines.append(f"  - {e[:200]}")
        if self.output_files:
            lines.append(f"[输出文件] {', '.join(self.output_files[:5])}")
        return "\n".join(lines)


@dataclass
class ToolResultCapsule(Capsule):
    """
    工具执行结果 Capsule
    
    只保留摘要和关键信息，不保留完整 stdout。
    """
    kind: str = "tool_result"
    tool: Optional[str] = None
    success: bool = True
    exit_code: Optional[int] = None
    cwd: Optional[str] = None
    timed_out: bool = False
    truncated: bool = False
    stdout_preview: Optional[str] = None  # 前 500 字符
    stderr_preview: Optional[str] = None  # 前 200 字符
    key_findings: List[str] = field(default_factory=list)
    artifact_refs: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **super().to_dict(),
            "tool": self.tool,
            "success": self.success,
            "exit_code": self.exit_code,
            "cwd": self.cwd,
            "timed_out": self.timed_out,
            "truncated": self.truncated,
            "stdout_preview": self.stdout_preview,
            "stderr_preview": self.stderr_preview,
            "key_findings": self.key_findings,
            "artifact_refs": self.artifact_refs,
        }
    
    def to_prompt_text(self) -> str:
        lines = []
        status = "成功" if self.success else f"失败(exit={self.exit_code})"
        lines.append(f"[{self.tool or 'tool'}] {status}")
        if self.cwd:
            lines.append(f"[工作目录] {self.cwd}")
        if self.key_findings:
            lines.append("[关键发现]")
            for f in self.key_findings[:3]:
                lines.append(f"  - {f}")
        if self.artifact_refs:
            lines.append(f"[可回读] {', '.join(self.artifact_refs[:3])}")
        return "\n".join(lines)


# ============================================================================
# Compacted Artifact
# ============================================================================

@dataclass
class CompactedArtifact:
    """
    压缩后的 Artifact
    
    三层表示：
    - raw_ref: 完整原文引用
    - index_ref: 结构索引引用
    - capsule_ref: 压缩表示引用
    """
    artifact_id: str
    content_type: ContentType
    raw_ref: str  # artifact://raw/...
    index_ref: Optional[str] = None  # artifact://index/...
    capsule_ref: Optional[str] = None  # artifact://capsule/...
    
    # 元数据
    original_filename: Optional[str] = None
    size_bytes: int = 0
    line_count: int = 0
    created_at: float = field(default_factory=time.time)
    
    # 引用
    chunk_refs: List[ChunkRef] = field(default_factory=list)
    symbol_refs: List[SymbolRef] = field(default_factory=list)
    
    # Capsule（运行时直接访问）
    capsule: Optional[Capsule] = None
    
    # 策略
    raw_in_prompt: bool = False
    capsule_in_prompt: bool = True
    lazy_read: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "content_type": self.content_type.value,
            "raw_ref": self.raw_ref,
            "index_ref": self.index_ref,
            "capsule_ref": self.capsule_ref,
            "original_filename": self.original_filename,
            "size_bytes": self.size_bytes,
            "line_count": self.line_count,
            "created_at": self.created_at,
            "chunk_refs": [c.to_dict() for c in self.chunk_refs],
            "symbol_refs": [s.to_dict() for s in self.symbol_refs],
            "capsule": self.capsule.to_dict() if self.capsule else None,
            "raw_in_prompt": self.raw_in_prompt,
            "capsule_in_prompt": self.capsule_in_prompt,
            "lazy_read": self.lazy_read,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CompactedArtifact":
        capsule_data = data.get("capsule")
        capsule = None
        if capsule_data:
            kind = capsule_data.get("kind", "prose")
            if kind == "prose":
                capsule = ProseCapsule(**capsule_data)
            elif kind == "code":
                capsule = CodeCapsule(**capsule_data)
            elif kind == "log":
                capsule = LogCapsule(**capsule_data)
            elif kind == "tool_result":
                capsule = ToolResultCapsule(**capsule_data)
        
        return cls(
            artifact_id=data["artifact_id"],
            content_type=ContentType(data["content_type"]),
            raw_ref=data["raw_ref"],
            index_ref=data.get("index_ref"),
            capsule_ref=data.get("capsule_ref"),
            original_filename=data.get("original_filename"),
            size_bytes=data.get("size_bytes", 0),
            line_count=data.get("line_count", 0),
            created_at=data.get("created_at", time.time()),
            chunk_refs=[ChunkRef.from_dict(c) for c in data.get("chunk_refs", [])],
            symbol_refs=[SymbolRef.from_dict(s) for s in data.get("symbol_refs", [])],
            capsule=capsule,
            raw_in_prompt=data.get("raw_in_prompt", False),
            capsule_in_prompt=data.get("capsule_in_prompt", True),
            lazy_read=data.get("lazy_read", True),
        )
    
    def to_prompt_text(self) -> str:
        """生成注入到 prompt 的文本（只用 Capsule）"""
        lines = []
        
        # 基本信息
        lines.append(f"[Artifact] {self.artifact_id}")
        if self.original_filename:
            lines.append(f"  文件: {self.original_filename}")
        lines.append(f"  类型: {self.content_type.value}")
        lines.append(f"  大小: {self.size_bytes} bytes")
        
        # Capsule 内容
        if self.capsule:
            lines.append("")
            lines.append(self.capsule.to_prompt_text())
        
        # 可回读
        if self.lazy_read:
            lines.append("")
            lines.append(f"[可回读] read_artifact(\"{self.artifact_id}\")")
        
        return "\n".join(lines)


# ============================================================================
# Read API
# ============================================================================

@dataclass
class ReadRequest:
    """读取请求"""
    artifact_id: str
    mode: Literal["raw", "chunk", "lines", "symbol", "capsule"] = "capsule"
    chunk_id: Optional[str] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    symbol_name: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "mode": self.mode,
            "chunk_id": self.chunk_id,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "symbol_name": self.symbol_name,
        }


@dataclass
class ReadResult:
    """读取结果"""
    success: bool
    content: Optional[str] = None
    error: Optional[str] = None
    truncated: bool = False
    source_ref: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "content": self.content,
            "error": self.error,
            "truncated": self.truncated,
            "source_ref": self.source_ref,
        }


# ============================================================================
# Compaction Policy
# ============================================================================

@dataclass
class CompactionPolicy:
    """压缩策略"""
    # 大小阈值
    min_size_for_compaction: int = 1000  # 小于此值不压缩
    max_chunk_size: int = 4000
    max_preview_size: int = 100
    
    # Capsule 限制
    max_constraints: int = 5
    max_decisions: int = 5
    max_risks: int = 3
    max_action_items: int = 5
    
    # 代码特定
    max_symbols: int = 50
    max_spans: int = 10
    
    # 日志特定
    max_errors: int = 10
    max_events: int = 20
    
    @classmethod
    def default(cls) -> "CompactionPolicy":
        return cls()
