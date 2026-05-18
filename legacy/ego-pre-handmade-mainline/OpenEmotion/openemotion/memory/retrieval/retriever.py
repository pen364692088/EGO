"""
Memory Retriever Module

记忆检索器，整合：
- 向量检索
- 去重检查
- 语义聚类

契约: docs/MEMORY_RETRIEVAL_CONTRACT_V1.md
"""

import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

from ..storage.sqlite_store import MemorySQLiteStore, MemoryEvent, MemoryNarrative, MemoryPolicy
from .dedup import MemoryDeduplicator, DedupResult, DedupConfig
from .clustering import MemoryClusterer, Cluster, ClusteringConfig
from .vector_index import MemoryVectorIndex, VectorIndexConfig, VectorEntry


@dataclass
class RetrievalHit:
    """检索命中结果"""
    id: str                      # narrative/policy ID
    type: str                    # 'narrative' | 'policy'
    similarity_score: float      # 相似度分数
    matched_text: str            # 匹配的文本
    metadata: Dict[str, Any]     # 元数据
    user_id: str                 # 用户ID (验证用)


@dataclass
class RetrievalResult:
    """检索结果"""
    query: str                   # 原始查询
    user_id: str                 # 用户ID
    hits: List[RetrievalHit]     # 命中结果
    trace_id: str                # 审计追踪ID
    timestamp: str               # 检索时间


class MemoryRetriever:
    """
    记忆检索器
    
    整合去重、聚类、向量检索
    """
    
    def __init__(
        self,
        store: MemorySQLiteStore,
        dedup_config: Optional[DedupConfig] = None,
        clustering_config: Optional[ClusteringConfig] = None,
        vector_config: Optional[VectorIndexConfig] = None,
    ):
        self.store = store
        
        # 初始化各模块
        self.deduplicator = MemoryDeduplicator(store, dedup_config)
        self.clusterer = MemoryClusterer(store, clustering_config)
        self.vector_index = MemoryVectorIndex(vector_config)
        
        # 统计
        self.stats = {
            "queries_processed": 0,
            "dedup_checks": 0,
            "clusterings": 0,
            "vector_searches": 0,
        }
    
    async def init(self) -> None:
        """初始化所有模块"""
        await self.store.init_db()
        await self.vector_index.init_db()
    
    # ========== Dedup ==========
    
    async def check_duplicate(
        self,
        event: MemoryEvent,
        trace_id: str,
    ) -> DedupResult:
        """检查事件重复"""
        self.stats["dedup_checks"] += 1
        return await self.deduplicator.check_duplicate(event, trace_id)
    
    # ========== Clustering ==========
    
    async def cluster_user_events(
        self,
        user_id: str,
        trace_id: str,
        limit: int = 100,
    ) -> List[Cluster]:
        """对用户事件进行聚类"""
        self.stats["clusterings"] += 1
        
        events = await self.store.query_events_by_user(user_id, limit=limit)
        if not events:
            return []
        
        result = await self.clusterer.cluster_events(events, user_id, trace_id)
        return result.clusters
    
    # ========== Vector Retrieval ==========
    
    async def index_narrative(
        self,
        narrative: MemoryNarrative,
    ) -> None:
        """索引叙事"""
        text = f"{narrative.theme} {narrative.summary}"
        await self.vector_index.index_entry(
            id=narrative.id,
            type="narrative",
            user_id=narrative.user_id,
            text=text,
            metadata={
                "theme": narrative.theme,
                "confidence": narrative.confidence,
                "source_event_ids": narrative.source_event_ids,
            },
        )
    
    async def index_policy(
        self,
        policy: MemoryPolicy,
    ) -> None:
        """索引策略"""
        text = f"{policy.policy_key}: {policy.policy_value}"
        await self.vector_index.index_entry(
            id=policy.id,
            type="policy",
            user_id=policy.user_id,
            text=text,
            metadata={
                "policy_key": policy.policy_key,
                "policy_value": policy.policy_value,
                "confidence": policy.confidence,
            },
        )
    
    async def retrieve(
        self,
        query_text: str,
        user_id: str,
        trace_id: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> RetrievalResult:
        """
        检索相关记忆
        
        Args:
            query_text: 查询文本
            user_id: 用户ID (硬隔离)
            trace_id: 审计追踪ID
            top_k: 返回数量
            filters: 可选过滤条件
            
        Returns:
            RetrievalResult: 检索结果
        """
        self.stats["queries_processed"] += 1
        self.stats["vector_searches"] += 1
        
        # 向量检索
        results = await self.vector_index.search(
            query_text=query_text,
            user_id=user_id,
            top_k=top_k,
        )
        
        # 转换为 RetrievalHit
        hits = []
        for entry, similarity in results:
            hit = RetrievalHit(
                id=entry.id,
                type=entry.type,
                similarity_score=round(similarity, 4),
                matched_text=entry.text,
                metadata=entry.metadata,
                user_id=entry.user_id,
            )
            
            # 应用过滤器
            if filters:
                if not self._match_filters(hit, filters):
                    continue
            
            hits.append(hit)
        
        return RetrievalResult(
            query=query_text,
            user_id=user_id,
            hits=hits,
            trace_id=trace_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
    
    def _match_filters(self, hit: RetrievalHit, filters: Dict[str, Any]) -> bool:
        """检查是否匹配过滤条件"""
        for key, value in filters.items():
            if key == "type":
                if hit.type != value:
                    return False
            elif key in hit.metadata:
                if hit.metadata[key] != value:
                    return False
        return True
    
    async def retrieve_narratives(
        self,
        query_text: str,
        user_id: str,
        trace_id: str,
        top_k: int = 3,
    ) -> RetrievalResult:
        """只检索叙事"""
        return await self.retrieve(
            query_text=query_text,
            user_id=user_id,
            trace_id=trace_id,
            top_k=top_k,
            filters={"type": "narrative"},
        )
    
    async def retrieve_policies(
        self,
        query_text: str,
        user_id: str,
        trace_id: str,
        top_k: int = 3,
    ) -> RetrievalResult:
        """只检索策略"""
        return await self.retrieve(
            query_text=query_text,
            user_id=user_id,
            trace_id=trace_id,
            top_k=top_k,
            filters={"type": "policy"},
        )
    
    # ========== End-to-End Flow ==========
    
    async def process_event(
        self,
        event: MemoryEvent,
        trace_id: str,
    ) -> Dict[str, Any]:
        """
        处理事件的完整流程
        
        1. 去重检查
        2. 写入存储 (如果 unique)
        3. 更新聚类
        4. 更新向量索引
        
        Returns:
            处理结果 artifact
        """
        artifacts = {
            "event_id": event.id,
            "trace_id": trace_id,
        }
        
        # 1. 去重检查
        dedup_result = await self.check_duplicate(event, trace_id)
        artifacts["dedup"] = {
            "status": dedup_result.dedup_status,
            "reason": dedup_result.dedup_reason,
            "similarity_score": dedup_result.similarity_score,
        }
        
        if dedup_result.dedup_status != "unique":
            artifacts["action"] = "skipped_duplicate"
            return artifacts
        
        # 2. 写入存储
        await self.store.write_event(event)
        artifacts["action"] = "written"
        
        # 3. 更新聚类 (异步，不阻塞)
        # 实际实现中可以后台处理
        # clusters = await self.cluster_user_events(event.user_id, trace_id)
        
        return artifacts
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self.stats,
            "dedup": self.deduplicator.get_stats(),
            "clustering": self.clusterer.get_stats(),
            "vector_index": self.vector_index.get_stats(),
        }
    
    async def verify_user_isolation(
        self,
        user_a: str,
        user_b: str,
        trace_id: str,
    ) -> Dict[str, Any]:
        """
        验证多用户隔离
        
        Returns:
            隔离验证结果
        """
        # 为 user_a 创建测试查询
        test_query = "test isolation query"
        
        # 检索 user_a
        result_a = await self.retrieve(
            query_text=test_query,
            user_id=user_a,
            trace_id=trace_id,
            top_k=10,
        )
        
        # 检索 user_b
        result_b = await self.retrieve(
            query_text=test_query,
            user_id=user_b,
            trace_id=trace_id,
            top_k=10,
        )
        
        # 验证无交叉
        ids_a = {h.id for h in result_a.hits}
        ids_b = {h.id for h in result_b.hits}
        
        cross_contamination = ids_a & ids_b
        
        # 验证所有命中都属于正确用户
        wrong_user_in_a = [h for h in result_a.hits if h.user_id != user_a]
        wrong_user_in_b = [h for h in result_b.hits if h.user_id != user_b]
        
        return {
            "user_a": user_a,
            "user_b": user_b,
            "isolation_valid": (
                len(cross_contamination) == 0
                and len(wrong_user_in_a) == 0
                and len(wrong_user_in_b) == 0
            ),
            "cross_contamination_count": len(cross_contamination),
            "wrong_user_in_a": len(wrong_user_in_a),
            "wrong_user_in_b": len(wrong_user_in_b),
            "trace_id": trace_id,
        }
