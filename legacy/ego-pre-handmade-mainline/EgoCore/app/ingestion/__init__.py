"""
EgoCore Long Input Ingestion Layer

统一处理 Telegram 文本附件与超长普通消息。
全文外置存储，首轮只注入摘要与引用，按需回读。

V1 支持格式：
- .txt, .md, .log
- .json, .yaml, .yml
- .csv
"""

from .contracts import (
    IngestedInput,
    ArtifactMetadata,
    ChunkRef,
    IngestionPolicy,
    IngestionResult,
)
from .artifact_store import ArtifactStore, get_artifact_store
from .text_processor import TextProcessor, get_text_processor
from .manager import IngestionManager, TelegramDocumentInfo, get_ingestion_manager

__all__ = [
    "IngestedInput",
    "ArtifactMetadata",
    "ChunkRef",
    "IngestionPolicy",
    "IngestionResult",
    "ArtifactStore",
    "TextProcessor",
    "IngestionManager",
    "TelegramDocumentInfo",
    "get_artifact_store",
    "get_text_processor",
    "get_ingestion_manager",
]
