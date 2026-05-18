"""
OpenEmotion Agent Runtime - Intent Mapper

P2-A.2: Maps natural language requests to structured operation intents.

Extracts:
- Operation type (list_dir, read_file, write_file, mkdir, exists)
- Target path
- Additional parameters (content, etc.)

This ensures user intent is correctly captured before tool execution.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Tuple
from enum import Enum
import re
import os


class OperationType(str, Enum):
    """Supported operation types."""
    LIST_DIR = "list_dir"
    READ_FILE = "read_file"
    WRITE_FILE = "write_file"
    MKDIR = "mkdir"
    EXISTS = "exists"
    UNKNOWN = "unknown"


@dataclass
class OperationIntent:
    """
    Structured representation of a user's operation intent.
    
    This is the result of parsing a natural language request
    into actionable parameters.
    """
    operation: OperationType
    target_path: Optional[str] = None
    target_name: Optional[str] = None
    content: Optional[str] = None
    confidence: float = 0.0
    raw_text: str = ""
    extraction_notes: List[str] = field(default_factory=list)
    
    def is_valid(self) -> bool:
        """Check if the intent has required parameters."""
        if self.operation == OperationType.UNKNOWN:
            return False
        if self.operation in (OperationType.LIST_DIR, OperationType.READ_FILE, 
                              OperationType.MKDIR, OperationType.EXISTS):
            return self.target_path is not None
        if self.operation == OperationType.WRITE_FILE:
            return self.target_path is not None
        return False
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "operation": self.operation.value,
            "target_path": self.target_path,
            "target_name": self.target_name,
            "content": self.content,
            "confidence": self.confidence,
            "extraction_notes": self.extraction_notes
        }


class IntentMapper:
    """
    Maps natural language requests to structured operation intents.
    
    P2-A.2 implementation:
    - Parses operation type from Chinese expressions
    - Extracts target paths with robust pattern matching
    - Validates extracted parameters
    """
    
    # Operation type patterns
    LIST_DIR_PATTERNS = [
        r"看看\s*(.+?)\s*[里裡]?\s*(?:有)?哪些文件",
        r"列出\s*(.+?)\s*(?:目录|目錄|文件|檔案)",
        r"(?:查看|看看|展示|显示|列出)\s*(.+?)\s*(?:目录|目錄)",
        r"(.+?)\s*[里裡]?\s*(?:有)?(?:什么|哪些)(?:文件|内容)",
        r"浏览\s*(.+)",
        r"ls\s+(.+)",
    ]
    
    READ_FILE_PATTERNS = [
        r"(?:读取|阅读|打开|查看|看看)\s*(.+?\.[a-zA-Z0-9]+)\s*(?:文件)?(?:内容)?",
        r"(?:读取|阅读|打开|查看|看看)\s*(.+?)\s*(?:文件)?(?:内容)?",
        r"cat\s+(.+)",
        r"read\s+(.+)",
        r"显示\s*(.+?)\s*(?:文件)?内容",
    ]
    
    WRITE_FILE_PATTERNS = [
        # Pattern: "在 X 里创建一个 Y 文件" - match directory and filename separately
        r"(?:在|于)\s*(.+?)\s*[里裡下]?\s*(?:创建|建立|新建|写|写入)\s*(?:一个)?\s*(.+?\.\w+)\s*(?:文件)?",
        r"(?:在|于)\s*(.+?)\s*[里裡下]?\s*(?:创建|建立|新建|写|写入)\s*(?:一个)?\s*([\w\-\.]+\.\w+)\s*(?:文件)?",
        r"(?:创建|建立|新建)\s*(.+?\.\w+)\s*(?:文件)?\s*(?:在|于)\s*(.+)",
        r"(?:写入|写)\s*(.+?\.\w+)\s*(?:文件)?",
        r"touch\s+(.+?\.\w+)",
        r"创建\s*(.+?\.\w+)\s*(?:文件)",
    ]
    
    MKDIR_PATTERNS = [
        r"(?:在|于)\s*(.+?)\s*[里裡下]?\s*(?:创建|建立|新建)\s*(?:一个)?\s*(?:目录|文件夹)",
        r"(?:创建|建立|新建)\s*(.+?)\s*(?:目录|文件夹)",
        r"mkdir\s+(.+)",
    ]
    
    EXISTS_PATTERNS = [
        r"(?:检查|确认|查看)\s*(.+?)\s*(?:是否)?存在",
        r"(.+?)\s*(?:存在吗|有没有)",
        r"test\s+-e\s+(.+)",
    ]
    
    def __init__(self):
        """Initialize intent mapper with compiled patterns."""
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Pre-compile regex patterns for performance."""
        self._list_dir_re = [re.compile(p, re.IGNORECASE) for p in self.LIST_DIR_PATTERNS]
        self._read_file_re = [re.compile(p, re.IGNORECASE) for p in self.READ_FILE_PATTERNS]
        self._write_file_re = [re.compile(p, re.IGNORECASE) for p in self.WRITE_FILE_PATTERNS]
        self._mkdir_re = [re.compile(p, re.IGNORECASE) for p in self.MKDIR_PATTERNS]
        self._exists_re = [re.compile(p, re.IGNORECASE) for p in self.EXISTS_PATTERNS]
    
    def parse(self, text: str) -> OperationIntent:
        """
        Parse natural language text into structured operation intent.
        
        Args:
            text: User's request text
        
        Returns:
            OperationIntent with extracted parameters
        """
        text = text.strip()
        notes = []
        
        # Try each operation type in order of specificity
        
        # 1. Try WRITE_FILE (most specific)
        intent = self._try_write_file(text, notes)
        if intent:
            return intent
        
        # 2. Try MKDIR
        intent = self._try_mkdir(text, notes)
        if intent:
            return intent
        
        # 3. Try EXISTS
        intent = self._try_exists(text, notes)
        if intent:
            return intent
        
        # 4. Try LIST_DIR
        intent = self._try_list_dir(text, notes)
        if intent:
            return intent
        
        # 5. Try READ_FILE
        intent = self._try_read_file(text, notes)
        if intent:
            return intent
        
        # Fallback: Unknown operation
        notes.append("No operation pattern matched")
        return OperationIntent(
            operation=OperationType.UNKNOWN,
            raw_text=text,
            confidence=0.0,
            extraction_notes=notes
        )
    
    def _try_list_dir(self, text: str, notes: List[str]) -> Optional[OperationIntent]:
        """Try to parse as LIST_DIR operation."""
        for pattern in self._list_dir_re:
            match = pattern.search(text)
            if match:
                path_raw = match.group(1).strip()
                path = self._extract_path(path_raw, notes)
                
                if path:
                    # Clean trailing slashes and punctuation
                    path = path.rstrip('/').rstrip('\\').rstrip('。').rstrip('，')
                    
                    notes.append(f"LIST_DIR matched, path: {path}")
                    return OperationIntent(
                        operation=OperationType.LIST_DIR,
                        target_path=path,
                        raw_text=text,
                        confidence=0.85,
                        extraction_notes=notes
                    )
        return None
    
    def _try_read_file(self, text: str, notes: List[str]) -> Optional[OperationIntent]:
        """Try to parse as READ_FILE operation."""
        for pattern in self._read_file_re:
            match = pattern.search(text)
            if match:
                path_raw = match.group(1).strip()
                path = self._extract_path(path_raw, notes)
                
                if path:
                    notes.append(f"READ_FILE matched, path: {path}")
                    return OperationIntent(
                        operation=OperationType.READ_FILE,
                        target_path=path,
                        raw_text=text,
                        confidence=0.85,
                        extraction_notes=notes
                    )
        return None
    
    def _try_write_file(self, text: str, notes: List[str]) -> Optional[OperationIntent]:
        """Try to parse as WRITE_FILE operation."""
        for pattern in self._write_file_re:
            match = pattern.search(text)
            if match:
                groups = match.groups()
                
                # Different pattern structures
                if len(groups) >= 2:
                    # Pattern: "在 X 里创建 Y 文件"
                    dir_path = self._extract_path(groups[0].strip(), notes)
                    file_name = self._extract_filename(groups[1].strip(), notes)
                    
                    if dir_path and file_name:
                        # Combine dir and filename
                        full_path = os.path.join(dir_path, file_name)
                        notes.append(f"WRITE_FILE matched, dir: {dir_path}, file: {file_name}, full: {full_path}")
                        return OperationIntent(
                            operation=OperationType.WRITE_FILE,
                            target_path=full_path,
                            target_name=file_name,
                            content="",  # Empty file creation
                            raw_text=text,
                            confidence=0.85,
                            extraction_notes=notes
                        )
                elif len(groups) == 1:
                    # Pattern: "创建 X 文件" - single path
                    path = self._extract_path(groups[0].strip(), notes)
                    if path:
                        notes.append(f"WRITE_FILE matched, path: {path}")
                        return OperationIntent(
                            operation=OperationType.WRITE_FILE,
                            target_path=path,
                            content="",
                            raw_text=text,
                            confidence=0.80,
                            extraction_notes=notes
                        )
        return None
    
    def _try_mkdir(self, text: str, notes: List[str]) -> Optional[OperationIntent]:
        """Try to parse as MKDIR operation."""
        for pattern in self._mkdir_re:
            match = pattern.search(text)
            if match:
                groups = match.groups()
                
                if len(groups) >= 2:
                    # Pattern: "在 X 里创建 Y 目录"
                    parent = self._extract_path(groups[0].strip(), notes)
                    dir_name = groups[1].strip()
                    
                    if parent and dir_name:
                        full_path = os.path.join(parent, dir_name)
                        notes.append(f"MKDIR matched, path: {full_path}")
                        return OperationIntent(
                            operation=OperationType.MKDIR,
                            target_path=full_path,
                            target_name=dir_name,
                            raw_text=text,
                            confidence=0.85,
                            extraction_notes=notes
                        )
                elif len(groups) == 1:
                    path = self._extract_path(groups[0].strip(), notes)
                    if path:
                        notes.append(f"MKDIR matched, path: {path}")
                        return OperationIntent(
                            operation=OperationType.MKDIR,
                            target_path=path,
                            raw_text=text,
                            confidence=0.80,
                            extraction_notes=notes
                        )
        return None
    
    def _try_exists(self, text: str, notes: List[str]) -> Optional[OperationIntent]:
        """Try to parse as EXISTS operation."""
        for pattern in self._exists_re:
            match = pattern.search(text)
            if match:
                path_raw = match.group(1).strip()
                path = self._extract_path(path_raw, notes)
                
                if path:
                    notes.append(f"EXISTS matched, path: {path}")
                    return OperationIntent(
                        operation=OperationType.EXISTS,
                        target_path=path,
                        raw_text=text,
                        confidence=0.85,
                        extraction_notes=notes
                    )
        return None
    
    def _extract_path(self, text: str, notes: List[str]) -> Optional[str]:
        """
        Extract a file/directory path from text.
        
        Handles:
        - Absolute paths (/home/user/...)
        - Paths with Chinese suffixes (里、下、里面)
        - Paths with trailing punctuation
        """
        if not text:
            return None
        
        # Clean common Chinese suffixes and prefixes
        text = text.strip()
        
        # Remove common wrapping characters
        text = text.strip('"\'')
        
        # Look for absolute path patterns
        # Match: /path/to/something followed by optional Chinese suffixes
        path_match = re.search(r'(/[^\s,\。，！？]+?)(?:[里裡下]面?|的|$)', text)
        if path_match:
            path = path_match.group(1).rstrip('/')
            notes.append(f"Extracted absolute path: {path}")
            return path
        
        # Look for relative path patterns
        # Match: path/to/something
        rel_match = re.search(r'([a-zA-Z0-9_\-./\\]+)', text)
        if rel_match:
            path = rel_match.group(1).rstrip('/')
            notes.append(f"Extracted relative path: {path}")
            return path
        
        # Fallback: use the text as-is if it looks like a path
        if '/' in text or '\\' in text:
            path = re.sub(r'[里裡下]面?', '', text).strip().rstrip('/')
            notes.append(f"Used text as path (fallback): {path}")
            return path
        
        notes.append(f"Could not extract path from: {text}")
        return None
    
    def _extract_filename(self, text: str, notes: List[str]) -> Optional[str]:
        """Extract a filename from text."""
        if not text:
            return None
        
        text = text.strip().strip('"\'')
        
        # Remove "文件" suffix if present
        text = re.sub(r'文件$', '', text).strip()
        
        # Remove common Chinese suffixes
        text = re.sub(r'[里裡下]面?$', '', text).strip()
        
        # Check if it looks like a valid filename (including extension)
        if re.match(r'^[\w\-\.]+\.\w+$', text):
            notes.append(f"Valid filename with extension: {text}")
            return text
        
        # Try to extract filename with extension pattern
        name_match = re.search(r'([\w\-]+\.\w+)', text)
        if name_match:
            return name_match.group(1)
        
        # Fallback: try to extract just the name part
        name_match = re.search(r'([\w\-\.]+)', text)
        if name_match:
            candidate = name_match.group(1)
            # If it has an extension or looks like a filename, use it
            if '.' in candidate or len(candidate) > 2:
                return candidate
        
        return text if text else None


# Global instance
_mapper: Optional[IntentMapper] = None


def get_intent_mapper() -> IntentMapper:
    """Get or create global IntentMapper instance."""
    global _mapper
    if _mapper is None:
        _mapper = IntentMapper()
    return _mapper


def parse_intent(text: str) -> OperationIntent:
    """
    Parse natural language text into structured operation intent.
    
    Convenience function using global mapper.
    
    Args:
        text: User's request text
    
    Returns:
        OperationIntent with extracted parameters
    """
    return get_intent_mapper().parse(text)
