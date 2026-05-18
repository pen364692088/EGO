"""
Memory Retrieval Module

记忆检索增强模块，包含：
- dedup: 自动去重
- clustering: 语义聚类
- vector_index: 向量索引
- retriever: 整合检索器

契约: docs/MEMORY_RETRIEVAL_CONTRACT_V1.md
"""

from .dedup import (
    MemoryDeduplicator,
    DedupResult,
    DedupConfig,
    generate_dedup_artifact,
)

from .clustering import (
    MemoryClusterer,
    Cluster,
    ClusteringResult,
    ClusteringConfig,
    generate_cluster_artifact,
)

from .vector_index import (
    MemoryVectorIndex,
    VectorEntry,
    VectorIndexConfig,
)

from .retriever import (
    MemoryRetriever,
    RetrievalHit,
    RetrievalResult,
)


__all__ = [
    # Dedup
    "MemoryDeduplicator",
    "DedupResult",
    "DedupConfig",
    "generate_dedup_artifact",
    
    # Clustering
    "MemoryClusterer",
    "Cluster",
    "ClusteringResult",
    "ClusteringConfig",
    "generate_cluster_artifact",
    
    # Vector Index
    "MemoryVectorIndex",
    "VectorEntry",
    "VectorIndexConfig",
    
    # Retriever
    "MemoryRetriever",
    "RetrievalHit",
    "RetrievalResult",
]
