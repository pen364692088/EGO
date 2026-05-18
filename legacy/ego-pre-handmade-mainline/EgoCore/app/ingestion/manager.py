"""
Ingestion Manager

统一长输入摄入入口。
使用 Semantic Compaction 层处理长内容。
"""

from __future__ import annotations
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from .contracts import (
    IngestedInput,
    ArtifactMetadata,
    ChunkRef,
    IngestionPolicy,
    IngestionResult,
    InputKind,
    IngestionStatus,
)
from .artifact_store import ArtifactStore, get_artifact_store
from .text_processor import TextProcessor, get_text_processor

# 使用 Compaction 层
from app.compaction import (
    CompactionManager,
    get_compaction_manager,
    ContentType,
)

logger = logging.getLogger(__name__)


@dataclass
class TelegramDocumentInfo:
    """Telegram 文档信息"""
    file_id: str
    file_unique_id: str
    filename: Optional[str]
    mime_type: str
    file_size: int
    message_id: int
    caption: Optional[str] = None


class IngestionManager:
    """
    摄入管理器
    
    统一处理：
    - Telegram 文本附件
    - 超长普通消息
    
    流程：
    1. 接收输入
    2. 落盘为 artifact
    3. 规范化 + 切分
    4. 生成摘要
    5. 返回 IngestedInput
    """
    
    # 支持的 MIME 类型
    SUPPORTED_MIME_TYPES = {
        "text/plain",
        "text/markdown",
        "text/x-markdown",
        "application/json",
        "text/yaml",
        "text/x-yaml",
        "text/csv",
    }
    
    # 支持的扩展名
    SUPPORTED_EXTENSIONS = {
        ".txt", ".md", ".log",
        ".json", ".yaml", ".yml",
        ".csv",
    }
    
    # 超长消息阈值
    LONG_MESSAGE_THRESHOLD = 8000  # 8KB
    
    def __init__(
        self,
        artifact_store: Optional[ArtifactStore] = None,
        text_processor: Optional[TextProcessor] = None,
        policy: Optional[IngestionPolicy] = None,
        compaction_manager: Optional[CompactionManager] = None,
    ):
        self.store = artifact_store or get_artifact_store()
        self.processor = text_processor or get_text_processor()
        self.policy = policy or IngestionPolicy.default()
        self.compactor = compaction_manager or get_compaction_manager()
    
    def is_supported_document(
        self,
        mime_type: Optional[str],
        filename: Optional[str],
    ) -> bool:
        """检查是否是支持的文档类型"""
        if mime_type and mime_type in self.SUPPORTED_MIME_TYPES:
            return True
        
        if filename:
            import pathlib
            ext = pathlib.Path(filename).suffix.lower()
            if ext in self.SUPPORTED_EXTENSIONS:
                return True
        
        return False
    
    def is_long_message(self, text: str) -> bool:
        """检查是否是超长消息"""
        return len(text) > self.LONG_MESSAGE_THRESHOLD
    
    async def ingest_telegram_document(
        self,
        document_info: TelegramDocumentInfo,
        content: bytes,
        session_key: str,
    ) -> IngestionResult:
        """
        摄入 Telegram 文档
        
        使用 Semantic Compaction 层处理长内容。
        
        Args:
            document_info: Telegram 文档信息
            content: 文件内容
            session_key: 会话标识
        
        Returns:
            IngestionResult 摄入结果
        """
        try:
            # 1. 检查是否支持
            if not self.is_supported_document(
                document_info.mime_type,
                document_info.filename,
            ):
                return IngestionResult(
                    success=False,
                    error=f"不支持的文件类型: {document_info.mime_type or document_info.filename}",
                )
            
            # 2. 解码文本
            text = content.decode("utf-8")
            
            # 3. 判断内容类型
            content_type = self._infer_content_type(document_info.filename, document_info.mime_type)
            
            # 4. 使用 Compaction 层处理
            artifact = self.compactor.compact(
                content=text,
                content_type=content_type,
                session_key=session_key,
                original_filename=document_info.filename,
            )
            
            logger.info(
                f"Telegram document compacted: {artifact.artifact_id} "
                f"type={content_type.value} chunks={len(artifact.chunk_refs)}"
            )
            
            # 5. 构建 IngestedInput（只保留最小信息）
            ingested = IngestedInput(
                session_key=session_key,
                message_id=str(document_info.message_id),
                user_text=document_info.caption,
                # 不再保存完整的 attachments/metadata
                attachments=[],
                # 不再保存 summary/outline，用 capsule 代替
                summary=None,
                outline=None,
                key_chunks=[],
                # 只保留 artifact_ref
                artifact_refs=[artifact.artifact_id],
                policy=self.policy,
                status=IngestionStatus.PROCESSED,
                # 保存 CompactedArtifact 引用
                _compacted_artifact=artifact,
            )
            
            return IngestionResult(
                success=True,
                ingested_input=ingested,
            )
            
        except Exception as e:
            logger.exception(f"Failed to ingest telegram document: {e}")
            return IngestionResult(
                success=False,
                error=str(e),
            )
    
    def _infer_content_type(self, filename: Optional[str], mime_type: Optional[str]) -> ContentType:
        """推断内容类型"""
        if filename:
            ext = filename.lower().split(".")[-1] if "." in filename else ""
            if ext in ("py", "js", "ts", "java", "go", "rs", "cpp", "c", "h"):
                return ContentType.CODE
            if ext in ("md", "txt", "rst", "adoc"):
                return ContentType.PROSE
            if ext in ("json", "yaml", "yml", "toml"):
                return ContentType.STRUCTURED
            if ext in ("log",):
                return ContentType.LOG
        
        if mime_type:
            if "markdown" in mime_type:
                return ContentType.PROSE
            if "json" in mime_type or "yaml" in mime_type:
                return ContentType.STRUCTURED
        
        return ContentType.PROSE
    
    async def ingest_long_message(
        self,
        text: str,
        session_key: str,
        message_id: str,
    ) -> IngestionResult:
        """
        摄入超长普通消息
        
        使用 Semantic Compaction 层统一处理，与 ingest_telegram_document 行为一致。
        
        Args:
            text: 消息文本
            session_key: 会话标识
            message_id: 消息 ID
        
        Returns:
            IngestionResult 摄入结果
        """
        try:
            # 使用 Compaction 层统一处理（与 ingest_telegram_document 一致）
            artifact = self.compactor.compact(
                content=text,
                content_type=ContentType.PROSE,
                session_key=session_key,
                original_filename=f"message_{message_id}.txt",
                metadata={"source": "long_message", "message_id": message_id},
            )
            
            logger.info(
                f"Long message compacted: {artifact.artifact_id} "
                f"type=prose size={len(text)} chunks={len(artifact.chunk_refs)}"
            )
            
            # 构建 IngestedInput（只保留最小信息，与文档行为一致）
            ingested = IngestedInput(
                session_key=session_key,
                message_id=message_id,
                user_text=text[:self.policy.max_inline_size] if len(text) <= self.policy.max_inline_size else None,
                # 统一使用 artifact_refs，不再保存完整 attachments/metadata
                attachments=[],
                summary=None,
                outline=None,
                key_chunks=[],
                artifact_refs=[artifact.artifact_id],
                policy=self.policy,
                status=IngestionStatus.PROCESSED,
                _compacted_artifact=artifact,
            )
            
            return IngestionResult(
                success=True,
                ingested_input=ingested,
            )
            
        except Exception as e:
            logger.exception(f"Failed to ingest long message: {e}")
            return IngestionResult(
                success=False,
                error=str(e),
            )
    
    def read_chunk(
        self,
        artifact_id: str,
        chunk_id: str,
    ) -> Optional[str]:
        """读取指定 chunk"""
        return self.store.read_chunk(artifact_id, chunk_id)
    
    def read_lines(
        self,
        artifact_id: str,
        line_start: int,
        line_end: int,
    ) -> Optional[str]:
        """读取指定行区间"""
        return self.store.read_lines(artifact_id, line_start, line_end)
    
    def read_section(
        self,
        artifact_id: str,
        section_heading: str,
    ) -> Optional[str]:
        """读取指定 section"""
        return self.store.read_section(artifact_id, section_heading)


# 单例
_manager: Optional[IngestionManager] = None


def get_ingestion_manager() -> IngestionManager:
    """获取全局 IngestionManager 实例"""
    global _manager
    if _manager is None:
        _manager = IngestionManager()
    return _manager
