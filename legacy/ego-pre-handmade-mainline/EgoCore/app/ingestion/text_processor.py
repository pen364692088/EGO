"""
Text Processor

文本规范化、切分、摘要生成。
"""

from __future__ import annotations
import re
import logging
from typing import Optional, List, Tuple
from dataclasses import dataclass

from .contracts import ChunkRef, InputKind

logger = logging.getLogger(__name__)


@dataclass
class ProcessedText:
    """处理后的文本"""
    normalized: str                    # 规范化后的文本
    line_count: int                    # 行数
    char_count: int                    # 字符数
    chunks: List[ChunkRef]             # 切分结果
    outline: Optional[str] = None      # 大纲（md）
    heading_tree: Optional[List[Tuple[int, str, int]]] = None  # (level, heading, line)


class TextProcessor:
    """
    文本处理器
    
    职责：
    - 编码规范化
    - 文本清洗
    - 智能切分
    - 摘要生成
    - 大纲提取
    """
    
    def __init__(
        self,
        chunk_size: int = 4000,
        max_summary_lines: int = 15,
    ):
        self.chunk_size = chunk_size
        self.max_summary_lines = max_summary_lines
    
    def process(
        self,
        content: str,
        kind: InputKind = InputKind.TEXT_DOCUMENT,
        filename: Optional[str] = None,
    ) -> ProcessedText:
        """
        处理文本
        
        Args:
            content: 原始文本
            kind: 输入类型
            filename: 文件名（用于推断处理策略）
        
        Returns:
            ProcessedText 处理结果
        """
        # 1. 规范化
        normalized = self._normalize(content)
        lines = normalized.splitlines()
        line_count = len(lines)
        char_count = len(normalized)
        
        # 2. 提取大纲（如果是 markdown）
        outline = None
        heading_tree = None
        if kind == InputKind.TEXT_DOCUMENT and filename and filename.endswith(".md"):
            heading_tree = self._extract_headings(lines)
            outline = self._build_outline(heading_tree)
        
        # 3. 切分
        chunks = self._chunk(normalized, lines, kind, heading_tree)
        
        logger.info(
            f"Text processed: {char_count} chars, {line_count} lines, "
            f"{len(chunks)} chunks"
        )
        
        return ProcessedText(
            normalized=normalized,
            line_count=line_count,
            char_count=char_count,
            chunks=chunks,
            outline=outline,
            heading_tree=heading_tree,
        )
    
    def _normalize(self, content: str) -> str:
        """规范化文本"""
        # 统一换行符
        text = content.replace("\r\n", "\n").replace("\r", "\n")
        
        # 移除 BOM（如果还在）
        if text.startswith("\ufeff"):
            text = text[1:]
        
        # 移除尾部空白
        text = text.rstrip()
        
        return text
    
    def _extract_headings(self, lines: List[str]) -> List[Tuple[int, str, int]]:
        """
        提取 markdown heading 结构
        
        Returns:
            List of (level, heading_text, line_number)
        """
        headings = []
        for i, line in enumerate(lines):
            # 匹配 # heading
            match = re.match(r'^(#{1,6})\s+(.+)$', line)
            if match:
                level = len(match.group(1))
                heading = match.group(2).strip()
                headings.append((level, heading, i + 1))  # 1-indexed
        
        return headings
    
    def _build_outline(self, heading_tree: Optional[List[Tuple[int, str, int]]]) -> Optional[str]:
        """构建大纲文本"""
        if not heading_tree:
            return None
        
        lines = []
        for level, heading, line_num in heading_tree:
            indent = "  " * (level - 1)
            lines.append(f"{indent}- {heading} (L{line_num})")
        
        return "\n".join(lines)
    
    def _chunk(
        self,
        normalized: str,
        lines: List[str],
        kind: InputKind,
        heading_tree: Optional[List[Tuple[int, str, int]]],
    ) -> List[ChunkRef]:
        """
        切分文本
        
        策略：
        - Markdown: 按 heading 切
        - 其他: 按段落/空行切，必要时强制按字符数切
        """
        if kind == InputKind.STRUCTURED_DATA:
            # 结构化数据不切分，整体作为一个 chunk
            return [ChunkRef(
                chunk_id="chunk_0",
                index=0,
                line_start=1,
                line_end=len(lines),
                char_count=len(normalized),
                preview=normalized[:100] if normalized else None,
            )]
        
        # Markdown: 按 heading 切
        if heading_tree:
            return self._chunk_by_heading(lines, heading_tree)
        
        # 其他: 按段落切
        return self._chunk_by_paragraph(lines)
    
    def _chunk_by_heading(
        self,
        lines: List[str],
        heading_tree: List[Tuple[int, str, int]],
    ) -> List[ChunkRef]:
        """按 heading 切分"""
        chunks = []
        
        # 添加文件开头的虚拟 heading
        boundaries = [(0, None, 1)]  # (line_index, heading, level)
        boundaries.extend([(h[2] - 1, h[1], h[0]) for h in heading_tree])
        boundaries.append((len(lines), None, 0))
        
        for i in range(len(boundaries) - 1):
            start_idx = boundaries[i][0]
            end_idx = boundaries[i + 1][0]
            heading = boundaries[i][1]
            
            if start_idx >= end_idx:
                continue
            
            section_lines = lines[start_idx:end_idx]
            section_text = "\n".join(section_lines)
            
            # 如果 section 太大，继续细分
            if len(section_text) > self.chunk_size * 1.5:
                sub_chunks = self._chunk_by_paragraph(section_lines, base_index=i)
                chunks.extend(sub_chunks)
            else:
                chunk_id = f"chunk_{len(chunks)}"
                chunks.append(ChunkRef(
                    chunk_id=chunk_id,
                    index=len(chunks),
                    line_start=start_idx + 1,
                    line_end=end_idx,
                    char_count=len(section_text),
                    heading=heading,
                    preview=section_text[:100].replace("\n", " ")[:100],
                ))
        
        return chunks
    
    def _chunk_by_paragraph(
        self,
        lines: List[str],
        base_index: int = 0,
    ) -> List[ChunkRef]:
        """按段落切分"""
        chunks = []
        current_start = 0
        current_lines = []
        
        for i, line in enumerate(lines):
            current_lines.append(line)
            current_text = "\n".join(current_lines)
            
            # 段落结束：空行 或 超过大小限制
            is_paragraph_end = line.strip() == ""
            is_size_limit = len(current_text) >= self.chunk_size
            
            if (is_paragraph_end or is_size_limit) and len(current_text.strip()) > 0:
                chunk_id = f"chunk_{len(chunks)}"
                chunks.append(ChunkRef(
                    chunk_id=chunk_id,
                    index=base_index + len(chunks),
                    line_start=current_start + 1,
                    line_end=i + 1,
                    char_count=len(current_text),
                    preview=current_text[:100].replace("\n", " ")[:100],
                ))
                current_lines = []
                current_start = i + 1
        
        # 处理剩余内容
        if current_lines:
            chunk_id = f"chunk_{len(chunks)}"
            current_text = "\n".join(current_lines)
            chunks.append(ChunkRef(
                chunk_id=chunk_id,
                index=base_index + len(chunks),
                line_start=current_start + 1,
                line_end=len(lines),
                char_count=len(current_text),
                preview=current_text[:100].replace("\n", " ")[:100],
            ))
        
        return chunks
    
    def generate_summary(
        self,
        processed: ProcessedText,
        max_lines: Optional[int] = None,
    ) -> str:
        """
        生成简单摘要
        
        注意：这只是基于规则的简单摘要。
        高质量摘要应调用 LLM 生成。
        
        Args:
            processed: 处理后的文本
            max_lines: 最大行数
        
        Returns:
            摘要文本
        """
        max_lines = max_lines or self.max_summary_lines
        lines = []
        
        # 基本信息
        lines.append(f"文档大小: {processed.char_count} 字符, {processed.line_count} 行")
        lines.append(f"切分数量: {len(processed.chunks)} 个片段")
        
        # 大纲
        if processed.outline:
            outline_lines = processed.outline.split("\n")[:max_lines]
            lines.append("")
            lines.append("文档结构:")
            lines.extend(outline_lines)
        
        # 首 N 行预览
        first_lines = processed.normalized.split("\n")[:5]
        if first_lines:
            lines.append("")
            lines.append("开头预览:")
            for l in first_lines:
                preview = l[:80] + ("..." if len(l) > 80 else "")
                lines.append(f"  {preview}")
        
        return "\n".join(lines)
    
    def extract_key_chunks(
        self,
        processed: ProcessedText,
        top_k: int = 3,
    ) -> List[ChunkRef]:
        """
        提取关键 chunks
        
        简单策略：取最大的 k 个 chunks
        
        Args:
            processed: 处理后的文本
            top_k: 数量
        
        Returns:
            关键 chunk 引用列表
        """
        if len(processed.chunks) <= top_k:
            return processed.chunks
        
        # 按大小排序，取最大的 k 个
        sorted_chunks = sorted(
            processed.chunks,
            key=lambda c: c.char_count,
            reverse=True,
        )
        
        # 保持原始顺序
        key_ids = {c.chunk_id for c in sorted_chunks[:top_k]}
        return [c for c in processed.chunks if c.chunk_id in key_ids]


# 单例
_processor: Optional[TextProcessor] = None


def get_text_processor() -> TextProcessor:
    """获取全局 TextProcessor 实例"""
    global _processor
    if _processor is None:
        _processor = TextProcessor()
    return _processor
