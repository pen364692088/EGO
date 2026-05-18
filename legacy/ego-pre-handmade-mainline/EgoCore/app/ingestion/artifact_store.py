"""
Artifact Store

管理已摄入文件的落盘、索引和读取。
"""

from __future__ import annotations
import os
import hashlib
import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from .contracts import (
    ArtifactMetadata,
    InputKind,
    ChunkRef,
    IngestionStatus,
)

logger = logging.getLogger(__name__)

# 默认 artifact 根目录
DEFAULT_ARTIFACT_ROOT = "artifacts/ingested_inputs"


class ArtifactStore:
    """
    Artifact 存储管理器
    
    职责：
    - 文件落盘
    - 元数据写入
    - 按需读取
    - 索引维护
    """
    
    def __init__(self, root_dir: Optional[str] = None):
        self.root = Path(root_dir or DEFAULT_ARTIFACT_ROOT)
        self._ensure_root()
    
    def _ensure_root(self) -> None:
        """确保根目录存在"""
        self.root.mkdir(parents=True, exist_ok=True)
    
    def _compute_sha256(self, content: bytes) -> str:
        """计算 SHA256"""
        return hashlib.sha256(content).hexdigest()
    
    def _get_artifact_dir(self, session_key: str, sha256: str) -> Path:
        """
        获取 artifact 目录路径
        
        格式: artifacts/ingested_inputs/<date>/<session_key>/<sha256>/
        """
        date_str = datetime.now().strftime("%Y-%m-%d")
        # 清理 session_key 中的特殊字符
        safe_session = session_key.replace(":", "_").replace("/", "_")
        return self.root / date_str / safe_session / sha256[:16]
    
    def store(
        self,
        content: bytes,
        session_key: str,
        original_filename: Optional[str] = None,
        mime: str = "text/plain",
        source: str = "telegram",
        telegram_message_id: Optional[str] = None,
        telegram_file_id: Optional[str] = None,
    ) -> ArtifactMetadata:
        """
        存储文件并返回元数据
        
        Args:
            content: 文件内容（字节）
            session_key: 会话标识
            original_filename: 原始文件名
            mime: MIME 类型
            source: 来源渠道
            telegram_message_id: Telegram 消息 ID
            telegram_file_id: Telegram 文件 ID
        
        Returns:
            ArtifactMetadata 元数据对象
        """
        sha256 = self._compute_sha256(content)
        artifact_dir = self._get_artifact_dir(session_key, sha256)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        
        # 确定文件扩展名
        ext = self._get_extension(original_filename, mime)
        
        # 落盘原始文件
        raw_filename = f"raw{ext}"
        raw_path = artifact_dir / raw_filename
        raw_path.write_bytes(content)
        
        # 生成 artifact_id
        artifact_id = f"artifact://ingested/{sha256[:16]}"
        
        # 推断输入类型
        kind = self._infer_kind(ext, mime)
        
        # 尝试解码文本以获取行数
        encoding = self._detect_encoding(content)
        line_count = 0
        try:
            text = content.decode(encoding)
            line_count = len(text.splitlines())
        except Exception:
            pass
        
        # 构建元数据
        metadata = ArtifactMetadata(
            artifact_id=artifact_id,
            sha256=sha256,
            kind=kind,
            mime=mime,
            original_filename=original_filename,
            size_bytes=len(content),
            encoding=encoding,
            line_count=line_count,
            source=source,
            telegram_message_id=telegram_message_id,
            telegram_file_id=telegram_file_id,
            session_key=session_key,
            raw_path=str(raw_path),
        )
        
        # 写入元数据文件
        meta_path = artifact_dir / "metadata.json"
        meta_path.write_text(json.dumps(metadata.to_dict(), indent=2, ensure_ascii=False))
        
        logger.info(
            f"Artifact stored: {artifact_id} "
            f"filename={original_filename} size={len(content)} "
            f"lines={line_count}"
        )
        
        return metadata
    
    def store_summary(
        self,
        artifact: ArtifactMetadata,
        summary: str,
        outline: Optional[str] = None,
    ) -> str:
        """
        存储摘要文件
        
        Returns:
            摘要文件路径
        """
        artifact_dir = Path(artifact.raw_path).parent
        summary_path = artifact_dir / "summary.txt"
        
        content = f"# 摘要\n\n{summary}"
        if outline:
            content += f"\n\n# 结构大纲\n\n{outline}"
        
        summary_path.write_text(content, encoding="utf-8")
        artifact.summary_path = str(summary_path)
        
        # 更新元数据
        meta_path = artifact_dir / "metadata.json"
        meta_path.write_text(json.dumps(artifact.to_dict(), indent=2, ensure_ascii=False))
        
        return str(summary_path)
    
    def store_chunks(
        self,
        artifact: ArtifactMetadata,
        chunks: List[ChunkRef],
        chunk_contents: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        存储 chunk 索引和内容
        
        Args:
            artifact: Artifact 元数据
            chunks: Chunk 引用列表
            chunk_contents: 可选的 chunk 内容映射
        
        Returns:
            chunks 目录路径
        """
        artifact_dir = Path(artifact.raw_path).parent
        chunks_dir = artifact_dir / "chunks"
        chunks_dir.mkdir(exist_ok=True)
        
        # 写入索引
        index_path = chunks_dir / "index.json"
        index_data = {
            "artifact_id": artifact.artifact_id,
            "chunk_count": len(chunks),
            "chunks": [c.to_dict() for c in chunks],
        }
        index_path.write_text(json.dumps(index_data, indent=2, ensure_ascii=False))
        
        # 写入各 chunk 内容
        if chunk_contents:
            for chunk_id, content in chunk_contents.items():
                chunk_file = chunks_dir / f"{chunk_id}.txt"
                chunk_file.write_text(content, encoding="utf-8")
        
        artifact.chunks_path = str(chunks_dir)
        artifact.chunk_count = len(chunks)
        
        # 更新元数据
        meta_path = artifact_dir / "metadata.json"
        meta_path.write_text(json.dumps(artifact.to_dict(), indent=2, ensure_ascii=False))
        
        return str(chunks_dir)
    
    def read_raw(self, artifact_id: str) -> Optional[str]:
        """
        读取原始文件内容
        
        Args:
            artifact_id: artifact URI
        
        Returns:
            文件内容字符串，失败返回 None
        """
        path = self._resolve_path(artifact_id, "raw")
        if path is None:
            return None
        
        # 尝试找具体文件
        for f in path.parent.glob("raw.*"):
            try:
                return f.read_text(encoding="utf-8")
            except Exception:
                continue
        
        return None
    
    def read_chunk(
        self,
        artifact_id: str,
        chunk_id: str,
    ) -> Optional[str]:
        """
        读取指定 chunk 内容
        
        Args:
            artifact_id: artifact URI
            chunk_id: chunk ID
        
        Returns:
            chunk 内容字符串
        """
        path = self._resolve_path(artifact_id, f"chunks/{chunk_id}.txt")
        if path is None:
            return None
        
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            return None
    
    def read_lines(
        self,
        artifact_id: str,
        line_start: int,
        line_end: int,
    ) -> Optional[str]:
        """
        读取指定行区间
        
        Args:
            artifact_id: artifact URI
            line_start: 起始行号（1-indexed）
            line_end: 结束行号（inclusive）
        
        Returns:
            指定行区间的文本
        """
        content = self.read_raw(artifact_id)
        if content is None:
            return None
        
        lines = content.splitlines()
        # 转换为 0-indexed
        start = max(0, line_start - 1)
        end = min(len(lines), line_end)
        
        return "\n".join(lines[start:end])
    
    def read_section(
        self,
        artifact_id: str,
        section_heading: str,
    ) -> Optional[str]:
        """
        读取指定 section（按 heading）
        
        仅适用于 markdown 文件。
        
        Args:
            artifact_id: artifact URI
            section_heading: section 标题（不含 #）
        
        Returns:
            section 内容
        """
        content = self.read_raw(artifact_id)
        if content is None:
            return None
        
        lines = content.splitlines()
        section_lines = []
        in_section = False
        section_level = 0
        
        for line in lines:
            # 检测 heading
            if line.startswith("#"):
                current_level = len(line) - len(line.lstrip("#"))
                current_heading = line.lstrip("#").strip()
                
                if not in_section and current_heading == section_heading:
                    in_section = True
                    section_level = current_level
                    section_lines.append(line)
                    continue
                elif in_section and current_level <= section_level:
                    # 遇到同级或更高级 heading，section 结束
                    break
            
            if in_section:
                section_lines.append(line)
        
        return "\n".join(section_lines) if section_lines else None
    
    def load_metadata(self, artifact_id: str) -> Optional[ArtifactMetadata]:
        """
        加载元数据
        
        Args:
            artifact_id: artifact URI
        
        Returns:
            ArtifactMetadata 对象
        """
        # 解析 artifact_id
        # artifact://ingested/<sha256_prefix>
        if not artifact_id.startswith("artifact://ingested/"):
            return None
        
        sha_prefix = artifact_id.split("/")[-1]
        
        # 搜索匹配的目录
        for date_dir in self.root.iterdir():
            if not date_dir.is_dir():
                continue
            for session_dir in date_dir.iterdir():
                if not session_dir.is_dir():
                    continue
                for artifact_dir in session_dir.iterdir():
                    if artifact_dir.name == sha_prefix:
                        meta_path = artifact_dir / "metadata.json"
                        if meta_path.exists():
                            try:
                                data = json.loads(meta_path.read_text())
                                return ArtifactMetadata.from_dict(data)
                            except Exception:
                                continue
        
        return None
    
    def _resolve_path(self, artifact_id: str, relative: str) -> Optional[Path]:
        """解析 artifact 内部路径"""
        if not artifact_id.startswith("artifact://ingested/"):
            return None
        
        sha_prefix = artifact_id.split("/")[-1]
        
        for date_dir in self.root.iterdir():
            if not date_dir.is_dir():
                continue
            for session_dir in date_dir.iterdir():
                if not session_dir.is_dir():
                    continue
                for artifact_dir in session_dir.iterdir():
                    if artifact_dir.name == sha_prefix:
                        return artifact_dir / relative
        
        return None
    
    def _get_extension(self, filename: Optional[str], mime: str) -> str:
        """推断文件扩展名"""
        if filename:
            ext = Path(filename).suffix.lower()
            if ext:
                return ext
        
        # 从 MIME 推断
        mime_to_ext = {
            "text/plain": ".txt",
            "text/markdown": ".md",
            "text/x-markdown": ".md",
            "application/json": ".json",
            "text/yaml": ".yaml",
            "text/x-yaml": ".yaml",
            "text/csv": ".csv",
        }
        return mime_to_ext.get(mime, ".txt")
    
    def _infer_kind(self, ext: str, mime: str) -> InputKind:
        """推断输入类型"""
        structured_exts = {".json", ".yaml", ".yml", ".csv"}
        if ext.lower() in structured_exts:
            return InputKind.STRUCTURED_DATA
        return InputKind.TEXT_DOCUMENT
    
    def _detect_encoding(self, content: bytes) -> str:
        """检测编码"""
        # BOM 检测
        if content.startswith(b'\xef\xbb\xbf'):
            return "utf-8-sig"
        if content.startswith(b'\xff\xfe'):
            return "utf-16-le"
        if content.startswith(b'\xfe\xff'):
            return "utf-16-be"
        
        # 默认 UTF-8
        try:
            content.decode("utf-8")
            return "utf-8"
        except UnicodeDecodeError:
            pass
        
        # 尝试其他编码
        for encoding in ["gbk", "gb2312", "latin-1"]:
            try:
                content.decode(encoding)
                return encoding
            except UnicodeDecodeError:
                continue
        
        return "utf-8"  # fallback


# 单例
_store: Optional[ArtifactStore] = None


def get_artifact_store() -> ArtifactStore:
    """获取全局 ArtifactStore 实例"""
    global _store
    if _store is None:
        _store = ArtifactStore()
    return _store
