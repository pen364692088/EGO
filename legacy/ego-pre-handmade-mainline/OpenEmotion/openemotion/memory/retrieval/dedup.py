"""
Memory Deduplication Module

自动去重模块，支持：
- Exact duplicate 检测
- Near duplicate 检测
- 用户隔离
- 可审计 artifact

契约: docs/MEMORY_RETRIEVAL_CONTRACT_V1.md
"""

import json
import hashlib
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

from ..storage.sqlite_store import MemoryEvent, MemorySQLiteStore


@dataclass
class DedupResult:
    """去重判定结果"""
    event_id: str
    dedup_status: str  # 'unique' | 'exact_duplicate' | 'near_duplicate'
    dedup_reason: str
    matched_event_id: Optional[str]
    similarity_score: float
    trace_id: str
    timestamp: str


class DedupConfig:
    """去重配置"""
    
    def __init__(
        self,
        exact_threshold: float = 1.0,
        near_threshold: float = 0.55,  # 进一步降低阈值以捕获语义相似
        lookback_events: int = 50,
        text_fields: List[str] = None,
    ):
        self.exact_threshold = exact_threshold
        self.near_threshold = near_threshold
        self.lookback_events = lookback_events
        self.text_fields = text_fields or ["content", "summary", "description"]


class MemoryDeduplicator:
    """
    记忆去重器
    
    功能：
    - 检测完全重复事件
    - 检测近似重复事件
    - 用户隔离
    - 生成可审计 artifact
    """
    
    def __init__(
        self,
        store: MemorySQLiteStore,
        config: Optional[DedupConfig] = None,
    ):
        self.store = store
        self.config = config or DedupConfig()
        
        # 统计
        self.stats = {
            "events_checked": 0,
            "unique_events": 0,
            "exact_duplicates": 0,
            "near_duplicates": 0,
        }
    
    async def check_duplicate(
        self,
        event: MemoryEvent,
        trace_id: str,
    ) -> DedupResult:
        """
        检查事件是否重复
        
        Args:
            event: 待检查事件
            trace_id: 审计追踪ID
            
        Returns:
            DedupResult: 去重判定结果
        """
        self.stats["events_checked"] += 1
        
        # 1. 查询该用户最近的事件
        recent_events = await self.store.query_events_by_user(
            user_id=event.user_id,
            limit=self.config.lookback_events,
        )
        
        # 2. 检查完全重复
        for existing_event in recent_events:
            if existing_event.id == event.id:
                continue  # 跳过自己
            
            exact_sim = self._compute_exact_similarity(event, existing_event)
            if exact_sim >= self.config.exact_threshold:
                self.stats["exact_duplicates"] += 1
                return DedupResult(
                    event_id=event.id,
                    dedup_status="exact_duplicate",
                    dedup_reason=f"Payload完全匹配 (event_type={event.event_type})",
                    matched_event_id=existing_event.id,
                    similarity_score=1.0,
                    trace_id=trace_id,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
        
        # 3. 检查近似重复
        for existing_event in recent_events:
            if existing_event.id == event.id:
                continue
            
            if existing_event.event_type != event.event_type:
                continue  # 不同类型不比较
            
            near_sim = self._compute_near_similarity(event, existing_event)
            if near_sim >= self.config.near_threshold:
                self.stats["near_duplicates"] += 1
                return DedupResult(
                    event_id=event.id,
                    dedup_status="near_duplicate",
                    dedup_reason=f"相似度={near_sim:.2f} 超过阈值 {self.config.near_threshold}",
                    matched_event_id=existing_event.id,
                    similarity_score=near_sim,
                    trace_id=trace_id,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
        
        # 4. 唯一事件
        self.stats["unique_events"] += 1
        return DedupResult(
            event_id=event.id,
            dedup_status="unique",
            dedup_reason="无匹配的已有事件",
            matched_event_id=None,
            similarity_score=0.0,
            trace_id=trace_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
    
    def _compute_exact_similarity(
        self,
        event1: MemoryEvent,
        event2: MemoryEvent,
    ) -> float:
        """
        计算完全相似度
        
        条件：
        - event_type 相同
        - payload 所有字段完全相同
        """
        if event1.event_type != event2.event_type:
            return 0.0
        
        # 比较 payload
        payload1 = json.dumps(event1.payload, sort_keys=True)
        payload2 = json.dumps(event2.payload, sort_keys=True)
        
        if payload1 == payload2:
            return 1.0
        
        return 0.0
    
    def _compute_near_similarity(
        self,
        event1: MemoryEvent,
        event2: MemoryEvent,
    ) -> float:
        """
        计算近似相似度
        
        方法：
        - 提取文本字段内容
        - 计算文本重叠度（词袋 + n-gram）
        - 计算核心字段匹配度
        """
        # 提取文本内容
        text1 = self._extract_text(event1.payload)
        text2 = self._extract_text(event2.payload)
        
        if not text1 or not text2:
            # 没有文本字段，退化为字段匹配
            return self._field_overlap(event1.payload, event2.payload)
        
        # 计算文本相似度 (Jaccard)
        tokens1 = set(text1.lower().split())
        tokens2 = set(text2.lower().split())
        
        if not tokens1 or not tokens2:
            return 0.0
        
        intersection = tokens1 & tokens2
        union = tokens1 | tokens2
        
        jaccard = len(intersection) / len(union) if union else 0.0
        
        # 计算字符级 n-gram 相似度（捕获轻微改写）
        char_ngram_sim = self._char_ngram_similarity(text1, text2, n=3)
        
        # 结合字段匹配度
        field_sim = self._field_overlap(event1.payload, event2.payload)
        
        # 加权平均：增加字符 n-gram 权重以捕获轻微改写
        return 0.4 * jaccard + 0.35 * char_ngram_sim + 0.25 * field_sim
    
    def _char_ngram_similarity(self, text1: str, text2: str, n: int = 3) -> float:
        """计算字符级 n-gram 相似度"""
        # 生成 n-gram
        def get_ngrams(text, n):
            text = text.lower().replace(" ", "")
            return set(text[i:i+n] for i in range(len(text) - n + 1))
        
        ngrams1 = get_ngrams(text1, n)
        ngrams2 = get_ngrams(text2, n)
        
        if not ngrams1 or not ngrams2:
            return 0.0
        
        intersection = ngrams1 & ngrams2
        union = ngrams1 | ngrams2
        
        return len(intersection) / len(union) if union else 0.0
    
    def _extract_text(self, payload: Dict[str, Any]) -> str:
        """从 payload 提取文本字段"""
        texts = []
        for field in self.config.text_fields:
            if field in payload:
                val = payload[field]
                if isinstance(val, str):
                    texts.append(val)
                elif isinstance(val, (list, dict)):
                    texts.append(json.dumps(val))
        return " ".join(texts)
    
    def _field_overlap(
        self,
        payload1: Dict[str, Any],
        payload2: Dict[str, Any],
    ) -> float:
        """计算字段重叠度"""
        keys1 = set(payload1.keys())
        keys2 = set(payload2.keys())
        
        common_keys = keys1 & keys2
        if not common_keys:
            return 0.0
        
        matching = 0
        for key in common_keys:
            val1 = json.dumps(payload1[key], sort_keys=True)
            val2 = json.dumps(payload2[key], sort_keys=True)
            if val1 == val2:
                matching += 1
        
        return matching / len(common_keys)
    
    async def check_batch(
        self,
        events: List[MemoryEvent],
        trace_id: str,
    ) -> List[DedupResult]:
        """批量检查事件"""
        results = []
        for event in events:
            result = await self.check_duplicate(event, trace_id)
            results.append(result)
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = self.stats["events_checked"]
        return {
            **self.stats,
            "duplicate_rate": (
                (self.stats["exact_duplicates"] + self.stats["near_duplicates"]) / total
                if total > 0 else 0.0
            ),
        }


def generate_dedup_artifact(result: DedupResult) -> Dict[str, Any]:
    """
    生成去重 artifact
    
    用于存储到 artifacts 目录
    """
    return {
        "artifact_type": "dedup_check",
        "event_id": result.event_id,
        "dedup_status": result.dedup_status,
        "dedup_reason": result.dedup_reason,
        "matched_event_id": result.matched_event_id,
        "similarity_score": result.similarity_score,
        "trace_id": result.trace_id,
        "timestamp": result.timestamp,
    }
