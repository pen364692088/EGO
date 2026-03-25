"""
Memory Vector Index Module

向量索引模块，支持：
- 本地 embedding 缓存
- 向量存储
- 相似度计算
- 用户隔离
- 多 embedding provider 支持

契约: docs/MEMORY_RETRIEVAL_CONTRACT_V1.md
"""

import json
import hashlib
import math
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict
import aiosqlite

from .embeddings import (
    EmbeddingProvider,
    EmbeddingProviderFactory,
    TfidfEmbeddingProvider,
    OpenAIEmbeddingProvider,
)


@dataclass
class VectorEntry:
    """向量条目"""
    id: str                      # narrative/policy ID
    type: str                    # 'narrative' | 'policy'
    user_id: str                 # 用户ID
    text: str                    # 原始文本
    embedding: List[float]       # 向量
    embedding_model: str         # embedding 模型
    metadata: Dict[str, Any]     # 元数据
    created_at: str


class VectorIndexConfig:
    """向量索引配置"""
    
    def __init__(
        self,
        db_path: Optional[str] = None,
        embedding_provider: str = "tfidf",  # "tfidf", "openai", "hybrid"
        embedding_dim: int = 128,
        openai_model: str = "text-embedding-3-small",
        cache_dir: Optional[str] = None,
    ):
        self.db_path = db_path or "./data/memory_vectors.db"
        self.embedding_provider = embedding_provider
        self.embedding_dim = embedding_dim
        self.openai_model = openai_model
        self.cache_dir = cache_dir


class MemoryVectorIndex:
    """
    记忆向量索引
    
    功能：
    - 向量存储与检索
    - 用户隔离
    - 多 embedding provider 支持
    """
    
    def __init__(
        self,
        config: Optional[VectorIndexConfig] = None,
    ):
        self.config = config or VectorIndexConfig()
        self._initialized = False
        
        # 创建 embedding provider
        self.embedding_provider = EmbeddingProviderFactory.create(
            provider_type=self.config.embedding_provider,
            dimension=self.config.embedding_dim,
            openai_model=self.config.openai_model,
            cache_dir=self.config.cache_dir,
        )
        
        # 缓存
        self._vectors: Dict[str, VectorEntry] = {}
        self._user_vectors: Dict[str, List[str]] = defaultdict(list)  # user_id -> [id, ...]
        
        # 统计
        self.stats = {
            "vectors_indexed": 0,
            "vectors_retrieved": 0,
            "queries_processed": 0,
            "embedding_model": self.embedding_provider.get_model_name(),
        }
    
    async def init_db(self) -> None:
        """初始化数据库"""
        from pathlib import Path
        Path(self.config.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        async with aiosqlite.connect(self.config.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS vector_index (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    text TEXT NOT NULL,
                    embedding TEXT NOT NULL,
                    embedding_model TEXT NOT NULL,
                    metadata TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_vectors_user_id 
                ON vector_index(user_id)
            """)
            
            await db.commit()
        
        self._initialized = True
    
    async def index_entry(
        self,
        id: str,
        type: str,
        user_id: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        索引一个条目
        
        Args:
            id: 条目ID (narrative/policy ID)
            type: 类型 ('narrative' | 'policy')
            user_id: 用户ID
            text: 文本内容
            metadata: 元数据
        """
        if not self._initialized:
            await self.init_db()
        
        # 计算 embedding
        embedding_result = await self.embedding_provider.embed(text)
        embedding = embedding_result.embedding
        
        # 存储到数据库
        entry = VectorEntry(
            id=id,
            type=type,
            user_id=user_id,
            text=text,
            embedding=embedding,
            embedding_model=embedding_result.model,
            metadata=metadata or {},
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        
        async with aiosqlite.connect(self.config.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO vector_index
                (id, type, user_id, text, embedding, embedding_model, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.id,
                entry.type,
                entry.user_id,
                entry.text,
                json.dumps(entry.embedding),
                entry.embedding_model,
                json.dumps(entry.metadata),
                entry.created_at,
            ))
            await db.commit()
        
        # 缓存
        self._vectors[id] = entry
        if id not in self._user_vectors[user_id]:
            self._user_vectors[user_id].append(id)
        
        self.stats["vectors_indexed"] += 1
    
    async def search(
        self,
        query_text: str,
        user_id: str,
        top_k: int = 5,
    ) -> List[Tuple[VectorEntry, float]]:
        """
        搜索相似条目
        
        Args:
            query_text: 查询文本
            user_id: 用户ID (硬隔离)
            top_k: 返回数量
            
        Returns:
            List of (VectorEntry, similarity_score)
        """
        if not self._initialized:
            await self.init_db()
        
        self.stats["queries_processed"] += 1
        
        # 查询 embedding
        query_result = await self.embedding_provider.embed(query_text)
        query_embedding = query_result.embedding
        
        # 获取该用户的所有向量
        user_entries = await self._get_user_entries(user_id)
        
        if not user_entries:
            return []
        
        # 计算相似度
        results = []
        for entry in user_entries:
            sim = self._cosine_similarity(query_embedding, entry.embedding)
            results.append((entry, sim))
        
        # 排序并返回 top_k
        results.sort(key=lambda x: x[1], reverse=True)
        
        self.stats["vectors_retrieved"] += min(top_k, len(results))
        
        return results[:top_k]
    
    async def _get_user_entries(self, user_id: str) -> List[VectorEntry]:
        """获取用户的所有向量条目"""
        # 先检查缓存
        if user_id in self._user_vectors:
            entries = []
            for id in self._user_vectors[user_id]:
                if id in self._vectors:
                    entries.append(self._vectors[id])
            return entries
        
        # 从数据库加载
        async with aiosqlite.connect(self.config.db_path) as db:
            cursor = await db.execute(
                """
                SELECT id, type, user_id, text, embedding, embedding_model, metadata, created_at
                FROM vector_index
                WHERE user_id = ?
                """,
                (user_id,)
            )
            rows = await cursor.fetchall()
        
        entries = []
        for row in rows:
            entry = VectorEntry(
                id=row[0],
                type=row[1],
                user_id=row[2],
                text=row[3],
                embedding=json.loads(row[4]),
                embedding_model=row[5],
                metadata=json.loads(row[6]) if row[6] else {},
                created_at=row[7],
            )
            entries.append(entry)
            self._vectors[entry.id] = entry
        
        if entries:
            self._user_vectors[user_id] = [e.id for e in entries]
        
        return entries
    
    def _cosine_similarity(
        self,
        vec1: List[float],
        vec2: List[float],
    ) -> float:
        """计算余弦相似度"""
        if len(vec1) != len(vec2):
            return 0.0
        
        dot = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot / (norm1 * norm2)
    
    async def delete_entry(self, id: str) -> None:
        """删除条目"""
        if not self._initialized:
            await self.init_db()
        
        async with aiosqlite.connect(self.config.db_path) as db:
            await db.execute(
                "DELETE FROM vector_index WHERE id = ?", (id,)
            )
            await db.commit()
        
        # 清理缓存
        if id in self._vectors:
            entry = self._vectors[id]
            if entry.user_id in self._user_vectors:
                self._user_vectors[entry.user_id] = [
                    x for x in self._user_vectors[entry.user_id] if x != id
                ]
            del self._vectors[id]
    
    async def clear_user(self, user_id: str) -> None:
        """清除用户所有向量"""
        if not self._initialized:
            await self.init_db()
        
        async with aiosqlite.connect(self.config.db_path) as db:
            await db.execute(
                "DELETE FROM vector_index WHERE user_id = ?", (user_id,)
            )
            await db.commit()
        
        # 清理缓存
        if user_id in self._user_vectors:
            for id in self._user_vectors[user_id]:
                if id in self._vectors:
                    del self._vectors[id]
            del self._user_vectors[user_id]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self.stats,
            "cached_vectors": len(self._vectors),
            "user_count": len(self._user_vectors),
        }
