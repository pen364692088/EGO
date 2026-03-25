"""
Memory Semantic Clustering Module

语义聚类模块，支持：
- 用户隔离聚类
- 主题提取
- 摘要生成
- Cluster -> Narrative 映射
- 可解释性增强

契约: docs/MEMORY_RETRIEVAL_CONTRACT_V1.md
"""

import json
import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict, Counter

from ..storage.sqlite_store import MemoryEvent, MemorySQLiteStore


@dataclass
class Cluster:
    """语义聚类"""
    cluster_id: str
    user_id: str
    event_ids: List[str]
    theme: str
    summary: str
    confidence: float
    keywords: List[str]
    representative_event_ids: List[str]  # 代表性事件
    event_types: List[str]               # 事件类型分布
    time_range: Optional[Dict[str, str]] # 时间范围
    created_at: str
    updated_at: str
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def is_interpretable(self) -> bool:
        """检查聚类是否可解释"""
        return bool(self.theme) and bool(self.summary) and len(self.representative_event_ids) > 0


@dataclass
class ClusteringResult:
    """聚类结果"""
    clusters: List[Cluster]
    user_id: str
    trace_id: str
    timestamp: str
    interpretable_rate: float  # 可解释聚类比例


class ClusteringConfig:
    """聚类配置"""
    
    def __init__(
        self,
        min_cluster_size: int = 2,
        max_cluster_size: int = 20,
        similarity_threshold: float = 0.6,
        max_clusters: int = 50,
        max_keywords: int = 8,
        max_representatives: int = 3,
    ):
        self.min_cluster_size = min_cluster_size
        self.max_cluster_size = max_cluster_size
        self.similarity_threshold = similarity_threshold
        self.max_clusters = max_clusters
        self.max_keywords = max_keywords
        self.max_representatives = max_representatives


class MemoryClusterer:
    """
    记忆语义聚类器
    
    功能：
    - 事件聚类
    - 主题提取
    - 摘要生成
    - 用户隔离
    - 可解释性保证
    """
    
    def __init__(
        self,
        store: MemorySQLiteStore,
        config: Optional[ClusteringConfig] = None,
    ):
        self.store = store
        self.config = config or ClusteringConfig()
        
        # 缓存
        self._clusters: Dict[str, Cluster] = {}
        
        # 统计
        self.stats = {
            "events_clustered": 0,
            "clusters_created": 0,
            "clusters_updated": 0,
            "interpretable_clusters": 0,
        }
    
    async def cluster_events(
        self,
        events: List[MemoryEvent],
        user_id: str,
        trace_id: str,
    ) -> ClusteringResult:
        """
        对事件进行聚类
        
        Args:
            events: 待聚类事件列表
            user_id: 用户ID (必须与所有 event.user_id 一致)
            trace_id: 审计追踪ID
            
        Returns:
            ClusteringResult: 聚类结果
        """
        # 验证用户隔离
        for event in events:
            if event.user_id != user_id:
                raise ValueError(
                    f"Event user_id={event.user_id} != query user_id={user_id}"
                )
        
        if not events:
            return ClusteringResult(
                clusters=[],
                user_id=user_id,
                trace_id=trace_id,
                timestamp=datetime.now(timezone.utc).isoformat(),
                interpretable_rate=1.0,
            )
        
        # 提取特征
        event_features = []
        for event in events:
            features = self._extract_features(event)
            event_features.append((event, features))
        
        # 聚类
        clusters = self._cluster_by_similarity(event_features, user_id)
        
        # 更新统计
        self.stats["events_clustered"] += len(events)
        self.stats["clusters_created"] += len(clusters)
        self.stats["interpretable_clusters"] += sum(1 for c in clusters if c.is_interpretable())
        
        # 缓存 clusters
        for cluster in clusters:
            self._clusters[cluster.cluster_id] = cluster
        
        # 计算可解释率
        interpretable_rate = sum(1 for c in clusters if c.is_interpretable()) / len(clusters) if clusters else 1.0
        
        return ClusteringResult(
            clusters=clusters,
            user_id=user_id,
            trace_id=trace_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            interpretable_rate=round(interpretable_rate, 2),
        )
    
    def _extract_features(self, event: MemoryEvent) -> Dict[str, Any]:
        """从事件提取聚类特征"""
        text = self._extract_text(event.payload)
        keywords = self._extract_keywords(text)
        
        return {
            "event_type": event.event_type,
            "keywords": keywords,
            "payload_keys": list(event.payload.keys()),
            "timestamp": event.timestamp,
            "text": text,
        }
    
    def _extract_text(self, payload: Dict[str, Any]) -> str:
        """提取文本内容"""
        texts = []
        text_fields = ["content", "summary", "description", "message", "text"]
        
        for key, val in payload.items():
            if key in text_fields and isinstance(val, str):
                texts.append(val)
            elif isinstance(val, str) and len(val) > 10:
                texts.append(val)
        
        return " ".join(texts)
    
    def _extract_keywords(self, text: str) -> Set[str]:
        """提取关键词"""
        stopwords = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "have", "has", "had", "do", "does", "did", "will", "would",
            "could", "should", "may", "might", "must", "shall", "can",
            "this", "that", "these", "those", "it", "its", "they",
            "them", "their", "he", "she", "him", "her", "his", "hers",
            "i", "me", "my", "mine", "we", "us", "our", "ours",
            "you", "your", "yours", "and", "or", "but", "if", "then",
            "else", "when", "where", "which", "who", "whom", "whose",
            "what", "why", "how", "all", "each", "every", "both",
            "few", "more", "most", "other", "some", "such", "no",
            "not", "only", "own", "same", "so", "than", "too", "very",
            "just", "also", "now", "here", "there", "when", "where",
            "to", "of", "in", "for", "on", "with", "at", "by", "from",
            "about", "into", "through", "during", "before", "after",
            "above", "below", "between", "under", "again", "further",
            "am", "being", "has", "do", "doing", "did", "does",
        }
        
        tokens = text.lower().split()
        keywords = set()
        
        for token in tokens:
            cleaned = "".join(c for c in token if c.isalnum())
            if cleaned and cleaned not in stopwords and len(cleaned) > 2:
                keywords.add(cleaned)
        
        return keywords
    
    def _cluster_by_similarity(
        self,
        event_features: List[Tuple[MemoryEvent, Dict[str, Any]]],
        user_id: str,
    ) -> List[Cluster]:
        """基于相似度聚类"""
        # 按 event_type 分组
        by_type: Dict[str, List[Tuple[MemoryEvent, Dict[str, Any]]]] = defaultdict(list)
        for event, features in event_features:
            by_type[features["event_type"]].append((event, features))
        
        clusters = []
        
        for event_type, items in by_type.items():
            # 在每个 event_type 内按关键词聚类
            type_clusters = self._cluster_by_keywords(items, user_id, event_type)
            clusters.extend(type_clusters)
        
        return clusters
    
    def _cluster_by_keywords(
        self,
        items: List[Tuple[MemoryEvent, Dict[str, Any]]],
        user_id: str,
        event_type: str,
    ) -> List[Cluster]:
        """按关键词相似度聚类"""
        clusters = []
        used = set()
        
        for i, (event1, features1) in enumerate(items):
            if i in used:
                continue
            
            # 找相似的事件
            similar: List[Tuple[MemoryEvent, Dict[str, Any]]] = [(event1, features1)]
            similar_indices = {i}
            
            for j, (event2, features2) in enumerate(items):
                if j <= i or j in used:
                    continue
                
                # 计算关键词重叠
                kw1 = features1["keywords"]
                kw2 = features2["keywords"]
                
                if not kw1 or not kw2:
                    continue
                
                intersection = kw1 & kw2
                union = kw1 | kw2
                jaccard = len(intersection) / len(union) if union else 0.0
                
                if jaccard >= self.config.similarity_threshold:
                    similar.append((event2, features2))
                    similar_indices.add(j)
                    
                    if len(similar) >= self.config.max_cluster_size:
                        break
            
            # 创建 cluster
            if len(similar) >= self.config.min_cluster_size:
                cluster = self._create_cluster(similar, user_id, event_type)
                clusters.append(cluster)
                used.update(similar_indices)
        
        return clusters
    
    def _create_cluster(
        self,
        items: List[Tuple[MemoryEvent, Dict[str, Any]]],
        user_id: str,
        event_type: str,
    ) -> Cluster:
        """创建可解释的 cluster"""
        events = [item[0] for item in items]
        features_list = [item[1] for item in items]
        
        # 合并关键词
        all_keywords: Set[str] = set()
        for features in features_list:
            all_keywords.update(features["keywords"])
        
        # 计算关键词频率
        keyword_freq = Counter()
        for features in features_list:
            for kw in features["keywords"]:
                keyword_freq[kw] += 1
        
        # 生成 cluster_id
        event_ids = [e.id for e in events]
        cluster_id = self._generate_cluster_id(user_id, event_ids)
        
        # 提取主题（使用最高频关键词）
        top_keywords = [kw for kw, _ in keyword_freq.most_common(self.config.max_keywords)]
        theme = self._extract_theme(event_type, top_keywords)
        
        # 生成摘要
        summary = self._generate_summary(events, theme, len(items))
        
        # 选择代表性事件（按时间排序，选最近的）
        sorted_events = sorted(events, key=lambda e: e.timestamp, reverse=True)
        representative_ids = [e.id for e in sorted_events[:self.config.max_representatives]]
        
        # 计算置信度
        confidence = min(1.0, len(events) / 5.0)
        
        # 事件类型分布
        event_types = list(set(e.event_type for e in events))
        
        # 时间范围
        timestamps = [e.timestamp for e in events]
        time_range = {
            "start": datetime.fromtimestamp(min(timestamps), timezone.utc).isoformat(),
            "end": datetime.fromtimestamp(max(timestamps), timezone.utc).isoformat(),
        } if timestamps else None
        
        now = datetime.now(timezone.utc).isoformat()
        
        return Cluster(
            cluster_id=cluster_id,
            user_id=user_id,
            event_ids=event_ids,
            theme=theme,
            summary=summary,
            confidence=round(confidence, 2),
            keywords=top_keywords,
            representative_event_ids=representative_ids,
            event_types=event_types,
            time_range=time_range,
            created_at=now,
            updated_at=now,
        )
    
    def _generate_cluster_id(self, user_id: str, event_ids: List[str]) -> str:
        """生成 cluster ID"""
        combined = f"{user_id}:{':'.join(sorted(event_ids))}"
        hash_val = hashlib.md5(combined.encode()).hexdigest()[:12]
        return f"cluster_{hash_val}"
    
    def _extract_theme(
        self,
        event_type: str,
        keywords: List[str],
    ) -> str:
        """提取主题"""
        if not keywords:
            return event_type
        
        top_3 = keywords[:3]
        return f"{event_type}: {', '.join(top_3)}"
    
    def _generate_summary(
        self,
        events: List[MemoryEvent],
        theme: str,
        count: int,
    ) -> str:
        """生成可解释摘要"""
        # 收集事件内容片段
        contents = []
        for event in events[:3]:  # 最多取前3个
            text = self._extract_text(event.payload)
            if text:
                # 截取前50字符
                contents.append(text[:50] + "..." if len(text) > 50 else text)
        
        content_summary = "; ".join(contents) if contents else "no text content"
        
        return f"聚类包含 {count} 个相关事件，主题: {theme}。代表性内容: {content_summary}"
    
    async def get_cluster(self, cluster_id: str) -> Optional[Cluster]:
        """获取 cluster"""
        return self._clusters.get(cluster_id)
    
    async def get_clusters_for_user(self, user_id: str) -> List[Cluster]:
        """获取用户的所有 cluster"""
        return [c for c in self._clusters.values() if c.user_id == user_id]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = self.stats["clusters_created"]
        interpretable = self.stats["interpretable_clusters"]
        
        return {
            **self.stats,
            "cached_clusters": len(self._clusters),
            "interpretable_rate": interpretable / total if total > 0 else 0,
        }


def generate_cluster_artifact(cluster: Cluster) -> Dict[str, Any]:
    """生成 cluster artifact"""
    return {
        "artifact_type": "cluster",
        "cluster_id": cluster.cluster_id,
        "user_id": cluster.user_id,
        "event_count": len(cluster.event_ids),
        "theme": cluster.theme,
        "summary": cluster.summary,
        "confidence": cluster.confidence,
        "keywords": cluster.keywords,
        "representative_event_ids": cluster.representative_event_ids,
        "is_interpretable": cluster.is_interpretable(),
        "created_at": cluster.created_at,
    }
