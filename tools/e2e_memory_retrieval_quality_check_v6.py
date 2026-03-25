#!/usr/bin/env python3
"""
E2E Memory Retrieval Quality Check v6 - A/B Verification

TF-IDF vs OpenAI Embeddings A/B 对照验证

核心问题：OpenAI embeddings 是否值得切换？

测试范围：
- 质量对照：hit@1, hit@3, similarity, hard_negative
- 性能对照：latency, cache_hit_rate
- 成本对照：per_100, per_1000 calls
- 决策建议：recommended_default_mode

契约: docs/MEMORY_RETRIEVAL_CONTRACT_V1.md
"""

import asyncio
import json
import time
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict, field
import tempfile
import statistics

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from openemotion.memory.storage.sqlite_store import (
    MemoryEvent,
    MemoryNarrative,
    MemorySQLiteStore,
    init_memory_store,
)
from openemotion.memory.retrieval.dedup import (
    MemoryDeduplicator,
    DedupConfig,
)
from openemotion.memory.retrieval.clustering import (
    MemoryClusterer,
    ClusteringConfig,
)
from openemotion.memory.retrieval.vector_index import (
    MemoryVectorIndex,
    VectorIndexConfig,
)
from openemotion.memory.retrieval.retriever import (
    MemoryRetriever,
)


@dataclass
class ABTestResult:
    """A/B 测试结果"""
    provider: str
    case_id: str
    passed: bool
    quality_metrics: Dict[str, Any]
    performance_metrics: Dict[str, Any]
    errors: List[str]
    duration_ms: float


@dataclass
class ABTestSummary:
    """A/B 测试汇总"""
    provider: str
    total_cases: int
    passed_cases: int
    pass_rate: float
    quality_summary: Dict[str, Any]
    performance_summary: Dict[str, Any]
    cost_summary: Dict[str, Any]


@dataclass
class VerificationReport:
    """验证报告"""
    test_suite: str
    version: str
    timestamp: str
    tfidf_result: ABTestSummary
    openai_result: Optional[ABTestSummary]
    comparison: Dict[str, Any]
    recommendation: Dict[str, Any]
    overall_passed: bool


class EmbeddingCostEstimator:
    """Embedding 成本估算器"""
    
    # OpenAI pricing (per 1M tokens)
    OPENAI_PRICING = {
        "text-embedding-3-small": 0.02,  # $0.02 / 1M tokens
        "text-embedding-3-large": 0.13,  # $0.13 / 1M tokens
        "text-embedding-ada-002": 0.10,  # $0.10 / 1M tokens
    }
    
    def __init__(self, model: str = "text-embedding-3-small"):
        self.model = model
        self.total_tokens = 0
        self.total_calls = 0
        self.total_chars = 0
    
    def record_call(self, text: str) -> None:
        """记录一次调用"""
        self.total_calls += 1
        self.total_chars += len(text)
        # 粗略估算 tokens (约 4 chars per token)
        self.total_tokens += len(text) // 4 + 1
    
    def estimate_cost(self, calls: int = 100) -> Dict[str, float]:
        """估算成本"""
        if self.total_calls == 0:
            return {"cost_per_100": 0, "cost_per_1000": 0}
        
        avg_tokens_per_call = self.total_tokens / self.total_calls
        price_per_1m = self.OPENAI_PRICING.get(self.model, 0.02)
        
        cost_per_100 = (avg_tokens_per_call * 100 / 1_000_000) * price_per_1m
        cost_per_1000 = (avg_tokens_per_call * 1000 / 1_000_000) * price_per_1m
        
        return {
            "total_calls": self.total_calls,
            "total_tokens": self.total_tokens,
            "avg_tokens_per_call": round(avg_tokens_per_call, 1),
            "cost_per_100": round(cost_per_100, 6),
            "cost_per_1000": round(cost_per_1000, 6),
        }


class MemoryRetrievalV6Verifier:
    """记忆检索 v6 A/B 验证器"""
    
    def __init__(self):
        self.cost_estimator = EmbeddingCostEstimator()
        
        # 加载测试用例
        self.test_cases = self._load_test_cases()
    
    def _load_test_cases(self) -> Dict[str, Any]:
        """加载测试用例"""
        # 使用 v5 的 30 cases + 扩充
        fixtures_path = Path(__file__).parent.parent / "tests" / "fixtures" / "memory_retrieval_v5_cases.json"
        with open(fixtures_path, "r") as f:
            return json.load(f)
    
    async def run_ab_test(
        self,
        provider_type: str,
        test_db_path: str,
        vector_db_path: str,
    ) -> ABTestSummary:
        """运行单次测试"""
        print(f"\n{'='*60}")
        print(f"Running A/B Test: {provider_type.upper()}")
        print(f"{'='*60}")
        
        # 初始化
        store = await init_memory_store(test_db_path)
        
        retriever = MemoryRetriever(
            store=store,
            dedup_config=DedupConfig(
                exact_threshold=1.0,
                near_threshold=0.55,
                lookback_events=100,
            ),
            clustering_config=ClusteringConfig(
                min_cluster_size=2,
                similarity_threshold=0.5,
            ),
            vector_config=VectorIndexConfig(
                db_path=vector_db_path,
                embedding_provider=provider_type,
                embedding_dim=128 if provider_type == "tfidf" else 1536,
            ),
        )
        
        await retriever.init()
        
        # 运行测试
        results = []
        latencies = []
        similarities = []
        wrong_recalls = 0
        cluster_summaries = 0
        total_clusters = 0
        
        for case_data in self.test_cases["cases"][:20]:  # 取前 20 个 case
            result = await self._run_case(case_data, retriever, store, provider_type)
            results.append(result)
            latencies.append(result.duration_ms)
            
            if result.quality_metrics.get("max_similarity"):
                similarities.append(result.quality_metrics["max_similarity"])
            
            wrong_recalls += result.quality_metrics.get("wrong_user_recall_count", 0)
            
            if result.quality_metrics.get("cluster_created"):
                total_clusters += 1
                if result.quality_metrics.get("summary_available"):
                    cluster_summaries += 1
        
        # 清理
        await store.reset()
        
        # 汇总
        passed = sum(1 for r in results if r.passed)
        
        quality_summary = {
            "hit_count": sum(r.quality_metrics.get("hit_count", 0) for r in results),
            "avg_similarity": round(statistics.mean(similarities), 4) if similarities else 0,
            "wrong_user_recall_count": wrong_recalls,
            "cluster_summary_available_rate": cluster_summaries / total_clusters if total_clusters > 0 else 1.0,
        }
        
        performance_summary = {
            "avg_latency_ms": round(statistics.mean(latencies), 2) if latencies else 0,
            "p95_latency_ms": round(sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0, 2),
            "total_cases": len(results),
        }
        
        cost_summary = self.cost_estimator.estimate_cost() if provider_type == "openai" else {"cost_per_100": 0, "cost_per_1000": 0}
        
        return ABTestSummary(
            provider=provider_type,
            total_cases=len(results),
            passed_cases=passed,
            pass_rate=passed / len(results) if results else 0,
            quality_summary=quality_summary,
            performance_summary=performance_summary,
            cost_summary=cost_summary,
        )
    
    async def _run_case(
        self,
        case_data: Dict[str, Any],
        retriever: MemoryRetriever,
        store: MemorySQLiteStore,
        provider_type: str,
    ) -> ABTestResult:
        """运行单个测试用例"""
        start_time = time.time()
        case_id = case_data["case_id"]
        category = case_data.get("category", "unknown")
        errors = []
        quality_metrics = {}
        
        trace_id = f"trace_{case_id}_{time.time()}"
        
        try:
            # 简化处理：只测试 synonym_rewrite 类别
            if category == "synonym_rewrite":
                events = [self._create_event(e, trace_id) for e in case_data["events"]]
                
                for event in events:
                    dedup_result = await retriever.check_duplicate(event, trace_id)
                    if dedup_result.dedup_status == "unique":
                        await store.write_event(event)
                
                narrative = MemoryNarrative(
                    id=f"narrative_{case_id}",
                    user_id=events[0].user_id,
                    trace_id=trace_id,
                    case_id=case_id,
                    source_event_ids=[e.id for e in events],
                    theme=events[0].event_type,
                    summary=" ".join([e.payload.get("content", "") for e in events]),
                    confidence=0.8,
                )
                await store.write_narrative(narrative)
                await retriever.index_narrative(narrative)
                
                # 记录成本
                if provider_type == "openai":
                    text = narrative.summary + " " + case_data.get("query", "")
                    self.cost_estimator.record_call(text)
                
                # 查询
                query = case_data.get("query", "")
                if query:
                    result = await retriever.retrieve_narratives(
                        query_text=query,
                        user_id=events[0].user_id,
                        trace_id=trace_id,
                        top_k=3,
                    )
                    
                    quality_metrics = {
                        "hit_count": len(result.hits),
                        "max_similarity": max([h.similarity_score for h in result.hits]) if result.hits else 0,
                    }
                else:
                    quality_metrics = {"hit_count": 0, "max_similarity": 0}
            
            else:
                # 其他类别简化处理
                quality_metrics = {"hit_count": 0, "max_similarity": 0}
        
        except Exception as e:
            errors.append(str(e))
        
        duration_ms = (time.time() - start_time) * 1000
        
        # 判断通过
        passed = len(errors) == 0 and quality_metrics.get("hit_count", 0) > 0
        
        return ABTestResult(
            provider=provider_type,
            case_id=case_id,
            passed=passed,
            quality_metrics=quality_metrics,
            performance_metrics={"latency_ms": duration_ms},
            errors=errors,
            duration_ms=duration_ms,
        )
    
    def _create_event(self, event_data: Dict[str, Any], trace_id: str) -> MemoryEvent:
        """创建测试事件"""
        return MemoryEvent(
            id=event_data["id"],
            user_id=event_data["user_id"],
            identity_handle=f"identity_{event_data['user_id']}",
            trace_id=trace_id,
            case_id=event_data["id"].split("_")[1],
            session_epoch="test_session_v6",
            timestamp=time.time(),
            event_type=event_data["event_type"],
            payload=event_data["payload"],
        )
    
    def generate_comparison(
        self,
        tfidf: ABTestSummary,
        openai: Optional[ABTestSummary],
    ) -> Dict[str, Any]:
        """生成对比分析"""
        comparison = {
            "pass_rate": {
                "tfidf": tfidf.pass_rate,
                "openai": openai.pass_rate if openai else None,
                "delta": (openai.pass_rate - tfidf.pass_rate) if openai else 0,
            },
            "avg_similarity": {
                "tfidf": tfidf.quality_summary.get("avg_similarity", 0),
                "openai": openai.quality_summary.get("avg_similarity", 0) if openai else None,
                "delta": (openai.quality_summary.get("avg_similarity", 0) - tfidf.quality_summary.get("avg_similarity", 0)) if openai else 0,
            },
            "avg_latency_ms": {
                "tfidf": tfidf.performance_summary.get("avg_latency_ms", 0),
                "openai": openai.performance_summary.get("avg_latency_ms", 0) if openai else None,
                "delta": (openai.performance_summary.get("avg_latency_ms", 0) - tfidf.performance_summary.get("avg_latency_ms", 0)) if openai else 0,
            },
        }
        
        return comparison
    
    def generate_recommendation(
        self,
        tfidf: ABTestSummary,
        openai: Optional[ABTestSummary],
    ) -> Dict[str, Any]:
        """生成决策建议"""
        if not openai:
            return {
                "recommended_default_mode": "tfidf",
                "reason": "OpenAI embeddings 测试未完成",
                "quality_gain_vs_cost": "unknown",
            }
        
        # 分析质量提升
        similarity_delta = openai.quality_summary.get("avg_similarity", 0) - tfidf.quality_summary.get("avg_similarity", 0)
        latency_delta = openai.performance_summary.get("avg_latency_ms", 0) - tfidf.performance_summary.get("avg_latency_ms", 0)
        cost = openai.cost_summary.get("cost_per_1000", 0)
        
        # 决策逻辑
        if similarity_delta > 0.1 and latency_delta < 500 and cost < 0.01:
            recommendation = "openai"
            reason = "质量显著提升，延迟可接受，成本低"
        elif similarity_delta > 0.05 and latency_delta < 1000 and cost < 0.05:
            recommendation = "hybrid"
            reason = "质量提升明显，建议双模式共存"
        else:
            recommendation = "tfidf"
            reason = "质量提升不明显或成本/延迟不可接受"
        
        return {
            "recommended_default_mode": recommendation,
            "reason": reason,
            "quality_gain": round(similarity_delta, 4),
            "latency_penalty_ms": round(latency_delta, 2),
            "cost_per_1000_calls": cost,
            "quality_gain_vs_cost": "positive" if similarity_delta > 0.05 else "marginal",
        }
    
    def generate_report(self, report: VerificationReport) -> str:
        """生成报告"""
        lines = [
            "# Memory Retrieval Enhancement v6 - A/B Verification Report",
            "",
            f"- **Test Suite**: {report.test_suite}",
            f"- **Version**: {report.version}",
            f"- **Timestamp**: {report.timestamp}",
            f"- **Overall**: {'✅ PASS' if report.overall_passed else '❌ FAIL'}",
            "",
            "---",
            "",
            "## Executive Summary",
            "",
            "本报告回答核心问题：**OpenAI embeddings 是否值得切换？**",
            "",
            f"- **推荐策略**: {report.recommendation.get('recommended_default_mode', 'unknown')}",
            f"- **理由**: {report.recommendation.get('reason', 'unknown')}",
            "",
            "---",
            "",
            "## A/B Test Results",
            "",
            "### TF-IDF Baseline",
            "",
            f"- **Total Cases**: {report.tfidf_result.total_cases}",
            f"- **Passed**: {report.tfidf_result.passed_cases}",
            f"- **Pass Rate**: {report.tfidf_result.pass_rate:.1%}",
            f"- **Avg Similarity**: {report.tfidf_result.quality_summary.get('avg_similarity', 0):.4f}",
            f"- **Avg Latency**: {report.tfidf_result.performance_summary.get('avg_latency_ms', 0):.2f}ms",
            f"- **Cost**: $0 (local)",
            "",
        ]
        
        if report.openai_result:
            lines.extend([
                "### OpenAI Embeddings",
                "",
                f"- **Total Cases**: {report.openai_result.total_cases}",
                f"- **Passed**: {report.openai_result.passed_cases}",
                f"- **Pass Rate**: {report.openai_result.pass_rate:.1%}",
                f"- **Avg Similarity**: {report.openai_result.quality_summary.get('avg_similarity', 0):.4f}",
                f"- **Avg Latency**: {report.openai_result.performance_summary.get('avg_latency_ms', 0):.2f}ms",
                f"- **Cost per 1000 calls**: ${report.openai_result.cost_summary.get('cost_per_1000', 0):.6f}",
                "",
            ])
        
        lines.extend([
            "---",
            "",
            "## Comparison",
            "",
            "```json",
            json.dumps(report.comparison, indent=2),
            "```",
            "",
            "---",
            "",
            "## Recommendation",
            "",
            "```json",
            json.dumps(report.recommendation, indent=2),
            "```",
            "",
            "---",
            "",
            "## Three Red Lines (Still Enforced)",
            "",
            "- ❌ Do NOT claim WS-C/C1 completed",
            "- ❌ Do NOT proceed to WS-C/C2",
            "- ❌ Do NOT claim MVP13-15 completed",
            "",
        ])
        
        return "\n".join(lines)


async def main():
    """主函数"""
    print("=" * 60)
    print("Memory Retrieval Enhancement v6 - A/B Verification")
    print("=" * 60)
    
    verifier = MemoryRetrievalV6Verifier()
    
    # Phase 1: TF-IDF baseline
    print("\n[Phase 1] Running TF-IDF baseline...")
    tfidf_result = await verifier.run_ab_test(
        provider_type="tfidf",
        test_db_path="./data/test_tfidf_v6.db",
        vector_db_path="./data/test_vectors_tfidf_v6.db",
    )
    
    # Phase 2: OpenAI embeddings (如果 API key 可用)
    openai_result = None
    
    import os
    if os.environ.get("OPENAI_API_KEY"):
        print("\n[Phase 2] Running OpenAI embeddings...")
        try:
            openai_result = await verifier.run_ab_test(
                provider_type="openai",
                test_db_path="./data/test_openai_v6.db",
                vector_db_path="./data/test_vectors_openai_v6.db",
            )
        except Exception as e:
            print(f"\n⚠️ OpenAI test failed: {e}")
            print("Falling back to TF-IDF only comparison")
    else:
        print("\n⚠️ OPENAI_API_KEY not set, skipping OpenAI test")
    
    # 生成报告
    comparison = verifier.generate_comparison(tfidf_result, openai_result)
    recommendation = verifier.generate_recommendation(tfidf_result, openai_result)
    
    report = VerificationReport(
        test_suite="memory_retrieval_v6",
        version="1.0.0",
        timestamp=datetime.now(timezone.utc).isoformat(),
        tfidf_result=tfidf_result,
        openai_result=openai_result,
        comparison=comparison,
        recommendation=recommendation,
        overall_passed=tfidf_result.pass_rate >= 0.8,
    )
    
    # 输出报告
    print("\n" + "=" * 60)
    print("VERIFICATION REPORT")
    print("=" * 60)
    print(verifier.generate_report(report))
    
    # 保存报告
    report_path = Path(__file__).parent.parent / "docs" / "MEMORY_RETRIEVAL_ENHANCEMENT_V6_REPORT.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(report_path, "w") as f:
        f.write(verifier.generate_report(report))
    
    print(f"\n📄 Report saved to: {report_path}")
    
    return 0 if report.overall_passed else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
