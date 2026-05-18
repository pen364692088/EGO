"""
EgoCore Semantic Compaction Layer

统一处理所有长内容的语义压缩。
Raw 保真保存，Capsule 入 prompt，Ref 进 history。

Content Types:
- prose: 普通文字（md, txt）
- code: 代码文件
- log: 日志/shell 输出
- tool_result: 工具执行结果
"""

from .contracts import (
    CompactedArtifact,
    Capsule,
    ProseCapsule,
    CodeCapsule,
    LogCapsule,
    ToolResultCapsule,
    ChunkRef,
    SymbolRef,
    ReadRequest,
    ReadResult,
    CompactionPolicy,
    ContentType,
)
from .manager import CompactionManager, get_compaction_manager

__all__ = [
    "CompactedArtifact",
    "Capsule",
    "ProseCapsule",
    "CodeCapsule",
    "LogCapsule",
    "ToolResultCapsule",
    "ChunkRef",
    "SymbolRef",
    "ReadRequest",
    "ReadResult",
    "CompactionPolicy",
    "ContentType",
    "CompactionManager",
    "get_compaction_manager",
]
