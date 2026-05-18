#!/usr/bin/env python3
"""
E2E Memory Retrieval Quality Check v4

记忆检索质量增强验证脚本

测试范围：
- Case 1: 相似表述命中同一叙事
- Case 2: 重复输入抑制
- Case 3: 近重复但有新增信息
- Case 4: 多事件语义聚类
- Case 5: 多用户隔离下的向量检索
- Case 6: 有检索增强 vs 无检索增强对照

契约: docs/MEMORY_RETRIEVAL_CONTRACT_V1.md
"""

import asyncio
import json
import time
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from openemotion.memory.storage.sqlite_store import (
    MemoryEvent,
    MemoryNarrative,
    MemoryPolicy,
    MemorySQLiteStore,
    init_memory_store,
)
from openemotion.memory.retrieval.dedup import (
    MemoryDeduplicator,
    DedupConfig,
    DedupResult,
)
from openemotion.memory.retrieval.clustering import (
    MemoryClusterer,
    ClusteringConfig,
    Cluster,
)
from openemotion.memory.retrieval.vector_index import (
    MemoryVectorIndex,
    VectorIndexConfig,
)
from openemotion.memory.retrieval.retriever import (
    MemoryRetriever,
    RetrievalResult,
)


@dataclass
class TestCaseResult:
    """测试用例结果"""
    case_id: str
    case_name: str
    passed: bool
    metrics: Dict[str, Any]
    artifacts: List[Dict[str, Any]]
    errors: List[str]
    duration_ms: float


@dataclass
class VerificationReport:
    """验证报告"""
    test_suite: str
    version: str
    timestamp: str
    case_results: List[TestCaseResult]
    summary: Dict[str, Any]
    overall_passed: bool


class MemoryRetrievalV4Verifier:
    """记忆检索 v4 验证器"""
    
    def __init__(
        self,
        test_db_path: str = "./data/test_memory_v4.db",
        vector_db_path: str = "./data/test_vectors_v4.db",
    ):
        self.test_db_path = test_db_path
        self.vector_db_path = vector_db_path
        self.store: Optional[MemorySQLiteStore] = None
        self.retriever: Optional[MemoryRetriever] = None
        
        # 加载测试用例
        self.test_cases = self._load_test_cases()
    
    def _load_test_cases(self) -> Dict[str, Any]:
        """加载测试用例"""
        fixtures_path = Path(__file__).parent.parent / "tests" / "fixtures" / "memory_retrieval_v4_cases.json"
        with open(fixtures_path, "r") as f:
            return json.load(f)
    
    async def setup(self) -> None:
        """初始化测试环境"""
        # 清理旧数据
        for path in [self.test_db_path, self.vector_db_path]:
            if Path(path).exists():
                Path(path).unlink()
        
        # 初始化存储
        self.store = await init_memory_store(self.test_db_path)
        
        # 初始化检索器
        self.retriever = MemoryRetriever(
            store=self.store,
            dedup_config=DedupConfig(
                exact_threshold=1.0,
                near_threshold=0.55,  # 进一步降低以捕获语义相似
                lookback_events=50,
            ),
            clustering_config=ClusteringConfig(
                min_cluster_size=2,
                similarity_threshold=0.6,
            ),
            vector_config=VectorIndexConfig(
                db_path=self.vector_db_path,
                embedding_dim=128,
            ),
        )
        
        await self.retriever.init()
    
    async def teardown(self) -> None:
        """清理测试环境"""
        if self.store:
            await self.store.reset()
    
    def _create_event(
        self,
        event_data: Dict[str, Any],
        trace_id: str,
    ) -> MemoryEvent:
        """创建测试事件"""
        return MemoryEvent(
            id=event_data["id"],
            user_id=event_data["user_id"],
            identity_handle=f"identity_{event_data['user_id']}",
            trace_id=trace_id,
            case_id=event_data["id"].split("_")[1],
            session_epoch="test_session",
            timestamp=time.time(),
            event_type=event_data["event_type"],
            payload=event_data["payload"],
        )
    
    async def run_all_cases(self) -> VerificationReport:
        """运行所有测试用例"""
        results = []
        
        for case_data in self.test_cases["cases"]:
            result = await self.run_case(case_data)
            results.append(result)
        
        # 汇总
        passed_count = sum(1 for r in results if r.passed)
        
        summary = {
            "total_cases": len(results),
            "passed": passed_count,
            "failed": len(results) - passed_count,
            "pass_rate": passed_count / len(results) if results else 0,
            "metrics": self._aggregate_metrics(results),
        }
        
        return VerificationReport(
            test_suite="memory_retrieval_v4",
            version="1.0.0",
            timestamp=datetime.now(timezone.utc).isoformat(),
            case_results=results,
            summary=summary,
            overall_passed=all(r.passed for r in results),
        )
    
    async def run_case(self, case_data: Dict[str, Any]) -> TestCaseResult:
        """运行单个测试用例"""
        start_time = time.time()
        case_id = case_data["case_id"]
        case_name = case_data["case_name"]
        artifacts = []
        errors = []
        metrics = {}
        
        print(f"\n{'='*60}")
        print(f"Running {case_id}: {case_name}")
        print(f"{'='*60}")
        
        try:
            if case_id == "case_1":
                metrics = await self._run_case_1(case_data, artifacts)
            elif case_id == "case_2":
                metrics = await self._run_case_2(case_data, artifacts)
            elif case_id == "case_3":
                metrics = await self._run_case_3(case_data, artifacts)
            elif case_id == "case_4":
                metrics = await self._run_case_4(case_data, artifacts)
            elif case_id == "case_5":
                metrics = await self._run_case_5(case_data, artifacts)
            elif case_id == "case_6":
                metrics = await self._run_case_6(case_data, artifacts)
            else:
                errors.append(f"Unknown case_id: {case_id}")
        
        except Exception as e:
            errors.append(f"Exception: {str(e)}")
        
        duration_ms = (time.time() - start_time) * 1000
        
        # 判断是否通过
        expected = case_data.get("expected", {})
        passed = self._check_expectations(metrics, expected, errors)
        
        print(f"\n{'✅' if passed else '❌'} Case {case_id}: {'PASS' if passed else 'FAIL'}")
        print(f"   Metrics: {json.dumps(metrics, indent=2)}")
        if errors:
            print(f"   Errors: {errors}")
        
        return TestCaseResult(
            case_id=case_id,
            case_name=case_name,
            passed=passed,
            metrics=metrics,
            artifacts=artifacts,
            errors=errors,
            duration_ms=duration_ms,
        )
    
    async def _run_case_1(
        self,
        case_data: Dict[str, Any],
        artifacts: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Case 1: 相似表述命中同一叙事"""
        trace_id = f"trace_case_1_{time.time()}"
        
        # 创建事件
        events = [
            self._create_event(e, trace_id)
            for e in case_data["events"]
        ]
        
        # 处理事件
        written_events = []
        for event in events:
            dedup_result = await self.retriever.check_duplicate(event, trace_id)
            artifacts.append({
                "event_id": event.id,
                "dedup_status": dedup_result.dedup_status,
            })
            
            if dedup_result.dedup_status == "unique":
                await self.store.write_event(event)
                written_events.append(event)
        
        # 创建叙事
        narrative = MemoryNarrative(
            id=f"narrative_case_1_{hashlib.md5(trace_id.encode()).hexdigest()[:8]}",
            user_id=events[0].user_id,
            trace_id=trace_id,
            case_id="case_1",
            source_event_ids=[e.id for e in written_events],
            theme="coding_preference",
            summary="User prefers dark theme for coding",
            confidence=0.85,
        )
        await self.store.write_narrative(narrative)
        
        # 索引叙事
        await self.retriever.index_narrative(narrative)
        
        # 查询
        query_event = events[-1]
        result = await self.retriever.retrieve_narratives(
            query_text=query_event.payload.get("query", ""),
            user_id=query_event.user_id,
            trace_id=trace_id,
            top_k=3,
        )
        
        # 检查命中
        hit_ids = [h.id for h in result.hits]
        narrative_hit = narrative.id in hit_ids
        max_similarity = max([h.similarity_score for h in result.hits]) if result.hits else 0
        
        return {
            "events_written": len(written_events),
            "narrative_hit": narrative_hit,
            "hit_count": len(result.hits),
            "max_similarity": round(max_similarity, 4),
            "dedup_stats": self.retriever.deduplicator.get_stats(),
        }
    
    async def _run_case_2(
        self,
        case_data: Dict[str, Any],
        artifacts: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Case 2: 重复输入抑制"""
        trace_id = f"trace_case_2_{time.time()}"
        
        events = [
            self._create_event(e, trace_id)
            for e in case_data["events"]
        ]
        
        # 处理事件并收集去重结果
        dedup_results = []
        written_count = 0
        suppressed_count = 0
        
        for event in events:
            result = await self.retriever.check_duplicate(event, trace_id)
            dedup_results.append(result)
            
            artifacts.append({
                "event_id": event.id,
                "dedup_status": result.dedup_status,
                "dedup_reason": result.dedup_reason,
                "similarity_score": result.similarity_score,
            })
            
            if result.dedup_status == "unique":
                await self.store.write_event(event)
                written_count += 1
            else:
                suppressed_count += 1
        
        # 创建叙事
        narratives = await self.store.query_narratives_by_user(events[0].user_id)
        
        return {
            "total_events": len(events),
            "unique_events": written_count,
            "suppressed_events": suppressed_count,
            "duplicate_suppression_rate": suppressed_count / len(events),
            "narrative_count": len(narratives),
            "dedup_artifacts_count": len([a for a in artifacts if a.get("dedup_status") != "unique"]),
        }
    
    async def _run_case_3(
        self,
        case_data: Dict[str, Any],
        artifacts: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Case 3: 近重复但有新增信息"""
        trace_id = f"trace_case_3_{time.time()}"
        
        events = [
            self._create_event(e, trace_id)
            for e in case_data["events"]
        ]
        
        dedup_statuses = []
        for event in events:
            result = await self.retriever.check_duplicate(event, trace_id)
            dedup_statuses.append(result.dedup_status)
            
            artifacts.append({
                "event_id": event.id,
                "dedup_status": result.dedup_status,
                "payload": event.payload,
            })
            
            # 近重复但允许更新
            if result.dedup_status == "unique":
                await self.store.write_event(event)
            elif result.dedup_status == "near_duplicate":
                # 允许更新已有叙事（简化实现）
                await self.store.write_event(event)
                artifacts[-1]["action"] = "narrative_updated"
        
        # 检查新增信息是否保留
        stored_events = await self.store.query_events_by_user(events[0].user_id)
        has_additional_topics = any(
            "additional_topics" in e.payload
            for e in stored_events
        )
        
        return {
            "dedup_statuses": dedup_statuses,
            "events_stored": len(stored_events),
            "new_info_preserved": has_additional_topics,
        }
    
    async def _run_case_4(
        self,
        case_data: Dict[str, Any],
        artifacts: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Case 4: 多事件语义聚类"""
        trace_id = f"trace_case_4_{time.time()}"
        
        events = [
            self._create_event(e, trace_id)
            for e in case_data["events"]
        ]
        
        # 写入事件
        for event in events:
            await self.store.write_event(event)
        
        # 聚类
        clusters = await self.retriever.cluster_user_events(
            user_id=events[0].user_id,
            trace_id=trace_id,
        )
        
        for cluster in clusters:
            artifacts.append({
                "cluster_id": cluster.cluster_id,
                "event_count": len(cluster.event_ids),
                "theme": cluster.theme,
                "summary": cluster.summary,
                "confidence": cluster.confidence,
            })
        
        # 检查聚类质量
        morning_cluster = None
        for cluster in clusters:
            if "morning" in cluster.theme.lower():
                morning_cluster = cluster
                break
        
        return {
            "cluster_count": len(clusters),
            "morning_cluster_size": len(morning_cluster.event_ids) if morning_cluster else 0,
            "morning_cluster_theme": morning_cluster.theme if morning_cluster else None,
            "cluster_summary_available": morning_cluster is not None and bool(morning_cluster.summary),
        }
    
    async def _run_case_5(
        self,
        case_data: Dict[str, Any],
        artifacts: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Case 5: 多用户隔离下的向量检索"""
        trace_id = f"trace_case_5_{time.time()}"
        
        user_a = self.test_cases["users"]["user_a"]
        user_b = self.test_cases["users"]["user_b"]
        
        # 创建用户 A 的事件
        for event_data in case_data["events_user_a"]:
            event = self._create_event(event_data, trace_id)
            await self.store.write_event(event)
            
            # 创建叙事
            narrative = MemoryNarrative(
                id=f"narrative_a_{event.id}",
                user_id=user_a,
                trace_id=trace_id,
                case_id="case_5",
                source_event_ids=[event.id],
                theme=event.payload.get("activity", "activity"),
                summary=event.payload.get("content", ""),
                confidence=0.8,
            )
            await self.store.write_narrative(narrative)
            await self.retriever.index_narrative(narrative)
        
        # 创建用户 B 的事件
        for event_data in case_data["events_user_b"]:
            event = self._create_event(event_data, trace_id)
            await self.store.write_event(event)
            
            narrative = MemoryNarrative(
                id=f"narrative_b_{event.id}",
                user_id=user_b,
                trace_id=trace_id,
                case_id="case_5",
                source_event_ids=[event.id],
                theme=event.payload.get("activity", "activity"),
                summary=event.payload.get("content", ""),
                confidence=0.8,
            )
            await self.store.write_narrative(narrative)
            await self.retriever.index_narrative(narrative)
        
        # 用户 A 查询
        query_a = case_data["query_user_a"]["text"]
        result_a = await self.retriever.retrieve_narratives(
            query_text=query_a,
            user_id=user_a,
            trace_id=trace_id,
            top_k=5,
        )
        
        # 用户 B 查询
        query_b = case_data["query_user_b"]["text"]
        result_b = await self.retriever.retrieve_narratives(
            query_text=query_b,
            user_id=user_b,
            trace_id=trace_id,
            top_k=5,
        )
        
        # 验证隔离
        user_a_hit_ids = {h.id for h in result_a.hits}
        user_b_hit_ids = {h.id for h in result_b.hits}
        
        # 检查交叉污染
        cross_contamination = user_a_hit_ids & user_b_hit_ids
        
        # 检查所有命中都属于正确用户
        wrong_user_in_a = [h for h in result_a.hits if h.user_id != user_a]
        wrong_user_in_b = [h for h in result_b.hits if h.user_id != user_b]
        
        artifacts.append({
            "user_a_hits": [h.id for h in result_a.hits],
            "user_b_hits": [h.id for h in result_b.hits],
            "cross_contamination": list(cross_contamination),
        })
        
        return {
            "user_a_hit_count": len(result_a.hits),
            "user_b_hit_count": len(result_b.hits),
            "wrong_user_recall_count": len(wrong_user_in_a) + len(wrong_user_in_b),
            "cross_contamination_count": len(cross_contamination),
            "isolation_valid": len(cross_contamination) == 0 and len(wrong_user_in_a) == 0 and len(wrong_user_in_b) == 0,
        }
    
    async def _run_case_6(
        self,
        case_data: Dict[str, Any],
        artifacts: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Case 6: 有检索增强 vs 无检索增强对照"""
        trace_id = f"trace_case_6_{time.time()}"
        
        events = [
            self._create_event(e, trace_id)
            for e in case_data["events"]
        ]
        
        # === Baseline: 无增强 ===
        baseline_store = await init_memory_store("./data/test_baseline.db")
        
        for event in events:
            # 直接写入，无去重
            await baseline_store.write_event(event)
        
        baseline_narratives = await baseline_store.query_narratives_by_user(events[0].user_id)
        
        # 简单关键词搜索作为 baseline
        query = case_data["query"]
        baseline_events = await baseline_store.query_events_by_user(events[0].user_id)
        baseline_match_count = sum(
            1 for e in baseline_events
            if any(kw in json.dumps(e.payload).lower() for kw in query.lower().split())
        )
        
        # === Enhanced: 有增强 ===
        # 使用去重
        written_count = 0
        suppressed_count = 0
        
        for event in events:
            result = await self.retriever.check_duplicate(event, trace_id)
            if result.dedup_status == "unique":
                await self.store.write_event(event)
                written_count += 1
            else:
                suppressed_count += 1
        
        # 聚类
        clusters = await self.retriever.cluster_user_events(
            user_id=events[0].user_id,
            trace_id=trace_id,
        )
        
        # 向量检索
        enhanced_result = await self.retriever.retrieve_narratives(
            query_text=query,
            user_id=events[0].user_id,
            trace_id=trace_id,
            top_k=5,
        )
        
        # 对比
        artifacts.append({
            "baseline": {
                "events_stored": len(baseline_events),
                "match_count": baseline_match_count,
                "dedup_applied": False,
                "clustering_applied": False,
            },
            "enhanced": {
                "events_stored": written_count,
                "suppressed_count": suppressed_count,
                "cluster_count": len(clusters),
                "retrieval_hit_count": len(enhanced_result.hits),
                "dedup_applied": True,
                "clustering_applied": True,
            },
        })
        
        # 清理 baseline
        await baseline_store.reset()
        
        return {
            "baseline_events": len(baseline_events),
            "enhanced_events": written_count,
            "duplicate_suppression_rate": suppressed_count / len(events),
            "cluster_count": len(clusters),
            "enhanced_hit_count": len(enhanced_result.hits),
            "enhanced_better": written_count < len(baseline_events),  # 更少的冗余事件
        }
    
    def _check_expectations(
        self,
        metrics: Dict[str, Any],
        expected: Dict[str, Any],
        errors: List[str],
    ) -> bool:
        """检查是否满足期望"""
        if not expected:
            return True
        
        passed = True
        
        # Case 1: narrative_hit, min_similarity
        if "narrative_hit" in expected:
            if not metrics.get("narrative_hit"):
                errors.append("Expected narrative_hit=True, got False")
                passed = False
        
        if "min_similarity" in expected:
            if metrics.get("max_similarity", 0) < expected["min_similarity"]:
                errors.append(f"Expected min_similarity={expected['min_similarity']}, got {metrics.get('max_similarity')}")
                passed = False
        
        # Case 2: duplicate_count, narrative_count
        if "duplicate_count" in expected:
            suppressed = metrics.get("suppressed_events", 0)
            if suppressed != expected["duplicate_count"]:
                errors.append(f"Expected duplicate_count={expected['duplicate_count']}, got {suppressed}")
                passed = False
        
        # Case 5: wrong_user_recall_count
        if "wrong_user_recall_count" in expected:
            if metrics.get("wrong_user_recall_count", -1) != expected["wrong_user_recall_count"]:
                errors.append(f"Expected wrong_user_recall_count={expected['wrong_user_recall_count']}, got {metrics.get('wrong_user_recall_count')}")
                passed = False
        
        if "isolation_valid" in expected:
            if not metrics.get("isolation_valid"):
                errors.append("Expected isolation_valid=True, got False")
                passed = False
        
        # Case 6: enhanced_better
        if "enhanced_better_than_baseline" in expected:
            if not metrics.get("enhanced_better"):
                errors.append("Expected enhanced better than baseline")
                passed = False
        
        return passed
    
    def _aggregate_metrics(self, results: List[TestCaseResult]) -> Dict[str, Any]:
        """汇总指标"""
        total_events_checked = 0
        total_duplicates_suppressed = 0
        total_clusters_created = 0
        total_wrong_user_recalls = 0
        
        for r in results:
            m = r.metrics
            total_events_checked += m.get("events_written", 0) + m.get("suppressed_events", 0)
            total_duplicates_suppressed += m.get("suppressed_events", 0)
            total_clusters_created += m.get("cluster_count", 0)
            total_wrong_user_recalls += m.get("wrong_user_recall_count", 0)
        
        return {
            "total_events_checked": total_events_checked,
            "total_duplicates_suppressed": total_duplicates_suppressed,
            "total_clusters_created": total_clusters_created,
            "total_wrong_user_recalls": total_wrong_user_recalls,
            "duplicate_suppression_rate": (
                total_duplicates_suppressed / total_events_checked
                if total_events_checked > 0 else 0
            ),
        }
    
    def generate_report(self, report: VerificationReport) -> str:
        """生成报告"""
        lines = [
            "# Memory Retrieval Enhancement v4 - Verification Report",
            "",
            f"- **Test Suite**: {report.test_suite}",
            f"- **Version**: {report.version}",
            f"- **Timestamp**: {report.timestamp}",
            f"- **Overall**: {'✅ PASS' if report.overall_passed else '❌ FAIL'}",
            "",
            "---",
            "",
            "## Summary",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Total Cases | {report.summary['total_cases']} |",
            f"| Passed | {report.summary['passed']} |",
            f"| Failed | {report.summary['failed']} |",
            f"| Pass Rate | {report.summary['pass_rate']:.1%} |",
            "",
            "---",
            "",
            "## Case Results",
            "",
        ]
        
        for case in report.case_results:
            status = "✅ PASS" if case.passed else "❌ FAIL"
            lines.append(f"### {case.case_id}: {case.case_name}")
            lines.append("")
            lines.append(f"**Status**: {status}")
            lines.append(f"**Duration**: {case.duration_ms:.2f}ms")
            lines.append("")
            
            if case.metrics:
                lines.append("**Metrics**:")
                lines.append("```json")
                lines.append(json.dumps(case.metrics, indent=2))
                lines.append("```")
                lines.append("")
            
            if case.errors:
                lines.append("**Errors**:")
                for err in case.errors:
                    lines.append(f"- {err}")
                lines.append("")
            
            lines.append("---")
            lines.append("")
        
        # Aggregate metrics
        lines.append("## Aggregate Metrics")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(report.summary["metrics"], indent=2))
        lines.append("```")
        lines.append("")
        
        # Three red lines
        lines.append("---")
        lines.append("")
        lines.append("## Three Red Lines (Still Enforced)")
        lines.append("")
        lines.append("- ❌ Do NOT claim WS-C/C1 completed")
        lines.append("- ❌ Do NOT proceed to WS-C/C2")
        lines.append("- ❌ Do NOT claim MVP13-15 completed")
        lines.append("")
        
        return "\n".join(lines)


async def main():
    """主函数"""
    print("=" * 60)
    print("Memory Retrieval Enhancement v4 - E2E Verification")
    print("=" * 60)
    
    verifier = MemoryRetrievalV4Verifier()
    
    try:
        await verifier.setup()
        report = await verifier.run_all_cases()
        
        # 打印报告
        print("\n" + "=" * 60)
        print("VERIFICATION REPORT")
        print("=" * 60)
        print(verifier.generate_report(report))
        
        # 保存报告
        report_path = Path(__file__).parent.parent / "docs" / "MEMORY_RETRIEVAL_ENHANCEMENT_V4_REPORT.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(report_path, "w") as f:
            f.write(verifier.generate_report(report))
        
        print(f"\n📄 Report saved to: {report_path}")
        
        # 返回状态码
        return 0 if report.overall_passed else 1
    
    finally:
        await verifier.teardown()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
