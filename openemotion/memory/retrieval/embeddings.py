"""
Memory Embeddings Module

Embedding 抽象层，支持：
- TF-IDF baseline (本地，无依赖)
- OpenAI Embeddings API (高质量，需 API key)
- Embedding cache

契约: docs/MEMORY_RETRIEVAL_CONTRACT_V1.md
"""

import json
import hashlib
import math
import os
import time
import asyncio
import urllib.request
import urllib.error
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class EmbeddingResult:
    """Embedding 计算结果"""
    text: str
    embedding: List[float]
    model: str
    dimension: int
    cached: bool
    timestamp: str


class EmbeddingProvider(ABC):
    """Embedding 提供者抽象类"""
    
    @abstractmethod
    async def embed(self, text: str) -> EmbeddingResult:
        """计算文本 embedding"""
        pass
    
    @abstractmethod
    def get_model_name(self) -> str:
        """获取模型名称"""
        pass
    
    @abstractmethod
    def get_dimension(self) -> int:
        """获取向量维度"""
        pass


class TfidfEmbeddingProvider(EmbeddingProvider):
    """
    TF-IDF Embedding 提供者 (Baseline)
    
    本地计算，无外部依赖，但语义能力有限
    """
    
    def __init__(self, dimension: int = 128):
        self.dimension = dimension
        self._doc_freq: Dict[str, int] = {}
        self._doc_count = 0
    
    def get_model_name(self) -> str:
        return "tfidf-baseline"
    
    def get_dimension(self) -> int:
        return self.dimension
    
    async def embed(self, text: str) -> EmbeddingResult:
        """计算 TF-IDF embedding"""
        tokens = self._tokenize(text)
        
        if not tokens:
            return EmbeddingResult(
                text=text,
                embedding=[0.0] * self.dimension,
                model=self.get_model_name(),
                dimension=self.dimension,
                cached=False,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        
        embedding = [0.0] * self.dimension
        
        # TF 权重
        token_counts = {}
        for token in tokens:
            token_counts[token] = token_counts.get(token, 0) + 1
        
        total_tokens = len(tokens)
        
        for token, count in token_counts.items():
            tf = count / total_tokens
            
            # 使用稳定的 hash 映射
            base_dim = int(hashlib.md5(token.encode()).hexdigest(), 16) % (self.dimension - 2)
            
            for offset in range(3):
                dim = (base_dim + offset) % self.dimension
                embedding[dim] += tf * (1.0 - offset * 0.25)
        
        # L2 normalize
        norm = math.sqrt(sum(x * x for x in embedding))
        if norm > 0:
            embedding = [x / norm for x in embedding]
        
        return EmbeddingResult(
            text=text,
            embedding=embedding,
            model=self.get_model_name(),
            dimension=self.dimension,
            cached=False,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
    
    def _tokenize(self, text: str) -> List[str]:
        """分词"""
        tokens = text.lower().split()
        cleaned = []
        for token in tokens:
            clean = "".join(c for c in token if c.isalnum())
            if clean and len(clean) > 1:
                cleaned.append(clean)
        return cleaned


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """
    OpenAI Embedding 提供者
    
    高质量语义 embedding，需要 API key
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "text-embedding-3-small",
        cache_dir: Optional[str] = None,
    ):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model
        self.cache_dir = Path(cache_dir or "./data/embedding_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 维度映射
        self._model_dimensions = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
        }
        
        self._cache: Dict[str, EmbeddingResult] = {}
        self._stats = {
            "api_calls": 0,
            "cache_hits": 0,
            "errors": 0,
        }
    
    def get_model_name(self) -> str:
        return f"openai-{self.model}"
    
    def get_dimension(self) -> int:
        return self._model_dimensions.get(self.model, 1536)
    
    async def embed(self, text: str) -> EmbeddingResult:
        """计算 OpenAI embedding"""
        # 检查缓存
        cache_key = self._get_cache_key(text)
        
        if cache_key in self._cache:
            self._stats["cache_hits"] += 1
            result = self._cache[cache_key]
            result.cached = True
            return result
        
        # 检查磁盘缓存
        cached_result = await self._load_from_disk_cache(cache_key)
        if cached_result:
            self._stats["cache_hits"] += 1
            self._cache[cache_key] = cached_result
            cached_result.cached = True
            return cached_result
        
        # 调用 API
        result = await self._call_api(text)
        
        # 缓存结果
        self._cache[cache_key] = result
        await self._save_to_disk_cache(cache_key, result)
        
        return result
    
    def _get_cache_key(self, text: str) -> str:
        """生成缓存 key"""
        combined = f"{self.model}:{text}"
        return hashlib.md5(combined.encode()).hexdigest()
    
    async def _load_from_disk_cache(self, cache_key: str) -> Optional[EmbeddingResult]:
        """从磁盘加载缓存"""
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        if not cache_file.exists():
            return None
        
        try:
            # 使用同步读取（在异步上下文中）
            with open(cache_file, "r") as f:
                data = json.load(f)
            
            return EmbeddingResult(
                text=data["text"],
                embedding=data["embedding"],
                model=data["model"],
                dimension=data["dimension"],
                cached=True,
                timestamp=data["timestamp"],
            )
        except Exception:
            return None
    
    async def _save_to_disk_cache(self, cache_key: str, result: EmbeddingResult) -> None:
        """保存到磁盘缓存"""
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        data = {
            "text": result.text,
            "embedding": result.embedding,
            "model": result.model,
            "dimension": result.dimension,
            "timestamp": result.timestamp,
        }
        
        # 使用同步写入
        with open(cache_file, "w") as f:
            json.dump(data, f)
    
    async def _call_api(self, text: str) -> EmbeddingResult:
        """调用 OpenAI API"""
        self._stats["api_calls"] += 1
        
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not set")
        
        url = "https://api.openai.com/v1/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        data = {
            "input": text,
            "model": self.model,
        }
        
        try:
            # 使用标准库 urllib（同步调用，在异步上下文中运行）
            req = urllib.request.Request(
                url,
                data=json.dumps(data).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            
            # 在线程池中运行同步 IO
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: urllib.request.urlopen(req, timeout=30),
            )
            
            result_data = response.read().decode("utf-8")
            result = json.loads(result_data)
            
            embedding = result["data"][0]["embedding"]
            
            return EmbeddingResult(
                text=text,
                embedding=embedding,
                model=self.get_model_name(),
                dimension=len(embedding),
                cached=False,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        
        except urllib.error.HTTPError as e:
            error_text = e.read().decode("utf-8")
            self._stats["errors"] += 1
            raise Exception(f"OpenAI API error: {e.code} - {error_text}")
        except Exception as e:
            self._stats["errors"] += 1
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self._stats,
            "cache_size": len(self._cache),
            "model": self.model,
        }


class HybridEmbeddingProvider(EmbeddingProvider):
    """
    混合 Embedding 提供者
    
    优先使用 upgraded provider，失败时降级到 baseline
    """
    
    def __init__(
        self,
        primary: EmbeddingProvider,
        fallback: EmbeddingProvider,
    ):
        self.primary = primary
        self.fallback = fallback
    
    def get_model_name(self) -> str:
        return f"hybrid({self.primary.get_model_name()})"
    
    def get_dimension(self) -> int:
        return self.primary.get_dimension()
    
    async def embed(self, text: str) -> EmbeddingResult:
        """计算 embedding，失败时降级"""
        try:
            return await self.primary.embed(text)
        except Exception as e:
            print(f"Primary embedding failed, using fallback: {e}")
            return await self.fallback.embed(text)


class EmbeddingProviderFactory:
    """Embedding 提供者工厂"""
    
    @staticmethod
    def create(
        provider_type: str = "tfidf",
        dimension: int = 128,
        openai_model: str = "text-embedding-3-small",
        cache_dir: Optional[str] = None,
    ) -> EmbeddingProvider:
        """
        创建 embedding provider
        
        Args:
            provider_type: "tfidf", "openai", "hybrid"
            dimension: TF-IDF 向量维度
            openai_model: OpenAI 模型名称
            cache_dir: 缓存目录
            
        Returns:
            EmbeddingProvider
        """
        if provider_type == "tfidf":
            return TfidfEmbeddingProvider(dimension=dimension)
        
        elif provider_type == "openai":
            return OpenAIEmbeddingProvider(
                model=openai_model,
                cache_dir=cache_dir,
            )
        
        elif provider_type == "hybrid":
            primary = OpenAIEmbeddingProvider(
                model=openai_model,
                cache_dir=cache_dir,
            )
            fallback = TfidfEmbeddingProvider(dimension=dimension)
            return HybridEmbeddingProvider(primary, fallback)
        
        else:
            raise ValueError(f"Unknown provider type: {provider_type}")
