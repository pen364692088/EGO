"""
Ingestion Contracts

定义长输入摄入层的核心数据结构。
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum
import time


class InputKind(Enum):
    """输入类型"""
    TEXT_DOCUMENT = "text_document"      # .txt, .md, .log
    STRUCTURED_DATA = "structured_data"  # .json, .yaml, .csv
    LONG_MESSAGE = "long_message"        # 超长普通消息


class IngestionStatus(Enum):
    """摄入状态"""
    PENDING = "pending"
    DOWNLOADED = "downloaded"
    PROCESSED = "processed"
    FAILED = "failed"


@dataclass
class ChunkRef:
    """Chunk 引用"""
    chunk_id: str                    # chunk 唯一标识
    index: int                       # 在文件中的顺序索引
    line_start: int                  # 起始行号
    line_end: int                    # 结束行号
    char_count: int                  # 字符数
    heading: Optional[str] = None    # 如果是 md，记录所属 heading
    preview: Optional[str] = None    # 前 100 字符预览

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
        return cls(
            chunk_id=data["chunk_id"],
            index=data["index"],
            line_start=data["line_start"],
            line_end=data["line_end"],
            char_count=data["char_count"],
            heading=data.get("heading"),
            preview=data.get("preview"),
        )


@dataclass
class ArtifactMetadata:
    """Artifact 元数据"""
    artifact_id: str                  # artifact://ingested/...
    sha256: str                       # 文件 hash
    kind: InputKind                   # 输入类型
    mime: str                         # MIME 类型
    original_filename: Optional[str]  # 原始文件名
    size_bytes: int                   # 文件大小
    encoding: str = "utf-8"           # 编码
    line_count: int = 0               # 行数
    chunk_count: int = 0              # chunk 数量

    # 来源信息
    source: str = "telegram"          # 来源渠道
    telegram_message_id: Optional[str] = None
    telegram_file_id: Optional[str] = None
    session_key: Optional[str] = None

    # 时间戳
    created_at: float = field(default_factory=time.time)

    # 引用路径
    raw_path: Optional[str] = None    # 原始文件路径
    summary_path: Optional[str] = None  # 摘要文件路径
    chunks_path: Optional[str] = None   # chunks 索引路径

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "sha256": self.sha256,
            "kind": self.kind.value,
            "mime": self.mime,
            "original_filename": self.original_filename,
            "size_bytes": self.size_bytes,
            "encoding": self.encoding,
            "line_count": self.line_count,
            "chunk_count": self.chunk_count,
            "source": self.source,
            "telegram_message_id": self.telegram_message_id,
            "telegram_file_id": self.telegram_file_id,
            "session_key": self.session_key,
            "created_at": self.created_at,
            "raw_path": self.raw_path,
            "summary_path": self.summary_path,
            "chunks_path": self.chunks_path,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ArtifactMetadata":
        return cls(
            artifact_id=data["artifact_id"],
            sha256=data["sha256"],
            kind=InputKind(data["kind"]),
            mime=data["mime"],
            original_filename=data.get("original_filename"),
            size_bytes=data["size_bytes"],
            encoding=data.get("encoding", "utf-8"),
            line_count=data.get("line_count", 0),
            chunk_count=data.get("chunk_count", 0),
            source=data.get("source", "telegram"),
            telegram_message_id=data.get("telegram_message_id"),
            telegram_file_id=data.get("telegram_file_id"),
            session_key=data.get("session_key"),
            created_at=data.get("created_at", time.time()),
            raw_path=data.get("raw_path"),
            summary_path=data.get("summary_path"),
            chunks_path=data.get("chunks_path"),
        )

    @property
    def artifact_ref(self) -> str:
        """返回可引用的 artifact URI"""
        return self.artifact_id


@dataclass
class IngestionPolicy:
    """摄入策略"""
    fulltext_in_context: bool = False      # 是否内联全文
    summary_in_context: bool = True        # 是否注入摘要
    max_inline_size: int = 8 * 1024        # 小于此值允许内联 (8KB)
    chunk_size: int = 4000                 # 每个 chunk 最大字符数
    summary_lines: int = 15                # 摘要行数
    top_k_chunks: int = 3                  # 首轮注入的关键 chunk 数

    @classmethod
    def default(cls) -> "IngestionPolicy":
        return cls()

    @classmethod
    def for_large_file(cls) -> "IngestionPolicy":
        """大文件策略：严格外置"""
        return cls(
            fulltext_in_context=False,
            summary_in_context=True,
            max_inline_size=0,  # 禁止内联
            chunk_size=4000,
            summary_lines=20,
            top_k_chunks=5,
        )


@dataclass
class IngestedInput:
    """
    已摄入的输入
    
    这是进入 Runtime 的正式输入对象。
    使用 Semantic Compaction 层处理长内容。
    """
    # 基本信息
    session_key: str
    message_id: str

    # 用户文本（caption 或长消息）
    user_text: Optional[str] = None

    # 附件（已废弃，保留兼容）
    attachments: List[ArtifactMetadata] = field(default_factory=list)

    # 摘要（已废弃，使用 capsule）
    summary: Optional[str] = None

    # 结构大纲（已废弃）
    outline: Optional[str] = None

    # 关键 chunks（已废弃）
    key_chunks: List[ChunkRef] = field(default_factory=list)

    # 引用句柄
    artifact_refs: List[str] = field(default_factory=list)

    # 摄入策略
    policy: IngestionPolicy = field(default_factory=IngestionPolicy.default)

    # 状态
    status: IngestionStatus = IngestionStatus.PENDING
    error: Optional[str] = None
    
    # CompactedArtifact 引用（新）
    _compacted_artifact: Any = None  # 避免循环导入，用 Any

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_key": self.session_key,
            "message_id": self.message_id,
            "user_text": self.user_text,
            "attachments": [a.to_dict() for a in self.attachments] if self.attachments else [],
            "summary": self.summary,
            "outline": self.outline,
            "key_chunks": [c.to_dict() for c in self.key_chunks] if self.key_chunks else [],
            "artifact_refs": self.artifact_refs,
            "policy": {
                "fulltext_in_context": self.policy.fulltext_in_context,
                "summary_in_context": self.policy.summary_in_context,
                "max_inline_size": self.policy.max_inline_size,
            },
            "status": self.status.value,
            "error": self.error,
        }

    def to_prompt_context(self) -> str:
        """
        生成注入到 LLM prompt 的上下文
        
        使用 Semantic Compaction：
        - 只注入 Capsule（goal/constraints/decisions/risks/actions）
        - 只注入 artifact_refs（用于按需回读）
        - 不注入完整摘要/大纲
        """
        lines = []

        # 用户文本（caption）
        if self.user_text:
            lines.append(f"[用户消息]\n{self.user_text}")

        # 使用 CompactedArtifact 的 capsule
        if self._compacted_artifact is not None:
            artifact = self._compacted_artifact
            lines.append("")
            lines.append(artifact.to_prompt_text())
        elif self.artifact_refs:
            # 没有 CompactedArtifact 时，只显示引用
            lines.append(f"\n[已摄入文件]")
            for ref in self.artifact_refs:
                lines.append(f"- 引用: {ref}")
            lines.append(f"- 可用 read_artifact() 读取详情")

        return "\n".join(lines)
    
    def get_full_summary(self) -> str:
        """
        获取完整摘要（用于调试或特定需求）
        
        不进入 prompt context。
        """
        lines = []

        if self.summary:
            lines.append(f"[内容摘要]\n{self.summary}")

        if self.outline:
            lines.append(f"\n[文档结构]\n{self.outline}")

        if self.key_chunks:
            lines.append("\n[关键片段]")
            for chunk in self.key_chunks:
                heading = f" ({chunk.heading})" if chunk.heading else ""
                lines.append(f"- Chunk {chunk.index}{heading}: lines {chunk.line_start}-{chunk.line_end}")
                if chunk.preview:
                    lines.append(f"  预览: {chunk.preview[:100]}...")

        return "\n".join(lines)


@dataclass
class IngestionResult:
    """摄入操作结果"""
    success: bool
    ingested_input: Optional[IngestedInput] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "ingested_input": self.ingested_input.to_dict() if self.ingested_input else None,
            "error": self.error,
        }
