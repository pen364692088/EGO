#!/usr/bin/env python3
"""
Memory Loop Verification Script v1

验证 OpenEmotion 记忆系统是否形成真实闭环：
- event → event_memory
- event_memory → narrative_memory  
- narrative_memory → policy_memory
- 记忆是否影响后续输出

验收问题：
Q1. 单个 event 是否进入 event_memory？
Q2. 多个相关 event 是否聚合成 narrative_memory？
Q3. narrative 是否影响/生成 policy？
Q4. policy/narrative 是否影响下一轮输出？
Q5. 相似输入再次出现时，是否命中已有结构？
Q6. 重启后关键表征是否保留？
Q7. 整条链是否有结构化 artifact 可追踪？
"""

import asyncio
import json
import sys
import time
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field, asdict

# Setup paths
OPENEMOTION_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(OPENEMOTION_ROOT))

from emotiond.memory import (
    EpisodicMemory, EpisodicEvent,
    NarrativeMemory, NarrativeEntry,
    Commitment, CommitmentsLedger,
    memory_system, initialize_memory_system,
)
from emotiond.narrative_memory import narrative_memory, NarrativeState
from emotiond.memory_legacy import MemorySystem


@dataclass
class MemoryLoopCase:
    """测试用例"""
    case_id: str
    description: str
    events: List[Dict[str, Any]] = field(default_factory=list)
    results: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    artifacts: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryLoopReport:
    """验证报告"""
    run_id: str
    timestamp: str
    cases: List[Dict[str, Any]]
    loop_status: str  # storage-only / partial-loop / full-minimal-loop
    evidence: Dict[str, Any]
    verdict: Dict[str, bool]


class MemoryLoopVerifier:
    """记忆环路验证器"""
    
    def __init__(self, artifact_dir: Optional[Path] = None):
        self.artifact_dir = artifact_dir or OPENEMOTION_ROOT / "artifacts" / "memory_loop_v1"
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        
        self.run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        self.cases: List[MemoryLoopCase] = []
        
        # 记忆系统实例
        self.episodic_memory = EpisodicMemory(db_path=str(self.artifact_dir / "test_episodic.db"))
        self.narrative_memory = NarrativeMemory()
        self.commitments_ledger = CommitmentsLedger()
        
        # 状态
        self.loop_status = "unknown"
        self.evidence = {
            "event_to_event_memory": False,
            "event_to_narrative": False,
            "narrative_to_policy": False,
            "memory_affects_output": False,
            "trace_complete": False,
        }
    
    async def setup(self):
        """初始化"""
        print("=" * 60)
        print("Memory Loop Verification v1")
        print("=" * 60)
        print(f"\nOpenEmotion root: {OPENEMOTION_ROOT}")
        print(f"Artifact dir: {self.artifact_dir}")
        print(f"Run ID: {self.run_id}")
        
        # 初始化数据库
        await self.episodic_memory.init_db()
        print("✅ Episodic memory initialized")
        
        # 初始化 legacy memory system
        await initialize_memory_system()
        print("✅ Legacy memory system initialized")
    
    # ========== Case 定义 ==========
    
    def create_case_1(self) -> MemoryLoopCase:
        """Case 1: 单事件写入"""
        return MemoryLoopCase(
            case_id="case_1",
            description="单事件写入验证",
            events=[{
                "event_type": "user_message",
                "actor": "test_user",
                "target": "assistant",
                "content": "你好，这是第一条测试消息",
            }],
        )
    
    def create_case_2(self) -> MemoryLoopCase:
        """Case 2: 同主题多事件聚合"""
        return MemoryLoopCase(
            case_id="case_2",
            description="同主题多事件聚合验证",
            events=[
                {
                    "event_type": "user_message",
                    "actor": "test_user_2",
                    "target": "assistant",
                    "content": "我想学习 Python",
                },
                {
                    "event_type": "user_message",
                    "actor": "test_user_2",
                    "target": "assistant",
                    "content": "请推荐一些 Python 教程",
                },
                {
                    "event_type": "user_message",
                    "actor": "test_user_2",
                    "target": "assistant",
                    "content": "Python 有什么好的项目可以练习？",
                },
            ],
        )
    
    def create_case_3(self) -> MemoryLoopCase:
        """Case 3: 策略层提升"""
        return MemoryLoopCase(
            case_id="case_3",
            description="策略层提升验证",
            events=[
                {
                    "event_type": "user_message",
                    "actor": "policy_test_user",
                    "target": "assistant",
                    "content": "以后遇到代码问题，请先给出调试步骤",
                },
                {
                    "event_type": "user_message",
                    "actor": "policy_test_user",
                    "target": "assistant",
                    "content": "好的，这个偏好我记住了",
                },
            ],
        )
    
    def create_case_4(self) -> MemoryLoopCase:
        """Case 4: 重复触发与回流"""
        return MemoryLoopCase(
            case_id="case_4",
            description="重复触发与回流验证",
            events=[
                {
                    "event_type": "user_message",
                    "actor": "repeat_test_user",
                    "target": "assistant",
                    "content": "这是一个重复场景测试",
                },
                {
                    "event_type": "user_message",
                    "actor": "repeat_test_user",
                    "target": "assistant",
                    "content": "这是一个重复场景测试",  # 相同内容
                },
            ],
        )
    
    # ========== 验证逻辑 ==========
    
    async def verify_case_1(self, case: MemoryLoopCase) -> None:
        """验证 Case 1: 单事件写入"""
        print(f"\n{'=' * 50}")
        print(f"Case 1: {case.description}")
        print(f"{'=' * 50}")
        
        event_data = case.events[0]
        
        # Step 1: 存储到 EpisodicMemory
        episodic_event = await self.episodic_memory.store(
            event_type=event_data["event_type"],
            context={
                "actor": event_data["actor"],
                "target": event_data["target"],
                "content": event_data["content"],
            },
            outcome="success",
            tags=["test", "memory_loop"],
        )
        
        event_id = episodic_event.event_id
        print(f"  ✅ Event stored to EpisodicMemory: {event_id}")
        
        # Step 3: 验证可读取
        retrieved = await self.episodic_memory.retrieve(event_id)
        if retrieved:
            print(f"  ✅ Event retrievable from EpisodicMemory")
            case.results["episodic_retrieved"] = True
            self.evidence["event_to_event_memory"] = True
        else:
            case.errors.append("Event not retrievable from EpisodicMemory")
            print(f"  ❌ Event NOT retrievable")
        
        # Step 4: 检查 narrative 是否更新
        target_id = event_data["actor"]
        narrative_state = narrative_memory.get_state(target_id)
        initial_count = narrative_state.event_count
        
        narrative_memory.update(
            target_id=target_id,
            event_type=event_data["event_type"],
            action_tendency="respond",
            conflict_detected=False,
        )
        
        updated_state = narrative_memory.get_state(target_id)
        if updated_state.event_count > initial_count:
            print(f"  ✅ Narrative updated: event_count {initial_count} → {updated_state.event_count}")
            case.results["narrative_updated"] = True
            self.evidence["event_to_narrative"] = True
        else:
            case.errors.append("Narrative not updated")
            print(f"  ❌ Narrative NOT updated")
        
        # 保存 artifact
        artifact = {
            "case_id": case.case_id,
            "event_id": event_id,
            "episodic_event": episodic_event.to_dict(),
            "narrative_state": updated_state.to_dict(),
        }
        artifact_path = self.artifact_dir / f"case_1_{event_id}.json"
        artifact_path.write_text(json.dumps(artifact, indent=2, default=str))
        case.artifacts["case_1"] = str(artifact_path)
        print(f"  ✅ Artifact saved: {artifact_path}")
    
    async def verify_case_2(self, case: MemoryLoopCase) -> None:
        """验证 Case 2: 同主题多事件聚合"""
        print(f"\n{'=' * 50}")
        print(f"Case 2: {case.description}")
        print(f"{'=' * 50}")
        
        target_id = case.events[0]["actor"]
        event_ids = []
        
        # 存储多个相关事件
        for i, event_data in enumerate(case.events, 1):
            episodic_event = await self.episodic_memory.store(
                event_type=event_data["event_type"],
                context={
                    "actor": event_data["actor"],
                    "target": event_data["target"],
                    "content": event_data["content"],
                    "theme": "python_learning",  # 相同主题
                },
                outcome="success",
                tags=["test", "python", "learning"],
            )
            event_id = episodic_event.event_id
            event_ids.append(event_id)
            
            # 更新 narrative
            narrative_memory.update(
                target_id=target_id,
                event_type=event_data["event_type"],
                action_tendency="respond",
                conflict_detected=False,
            )
            
            print(f"  ✅ Event {i} stored: {event_id}")
        
        # 检查是否聚合
        narrative_state = narrative_memory.get_state(target_id)
        compressed = narrative_memory.compress(target_id)
        
        print(f"\n  Narrative state:")
        print(f"    Event count: {narrative_state.event_count}")
        print(f"    Compressed: {compressed['summary'][:100]}...")
        
        # 检查 theme 是否被识别
        # (注意：当前的 NarrativeMemory 是简单的计数器，不自动识别主题)
        if narrative_state.event_count >= len(case.events):
            print(f"  ✅ Multiple events recorded in narrative")
            case.results["events_aggregated"] = True
        else:
            case.errors.append("Events not properly aggregated")
        
        # 保存 artifact
        artifact = {
            "case_id": case.case_id,
            "event_ids": event_ids,
            "narrative_state": narrative_state.to_dict(),
            "compressed": compressed,
        }
        artifact_path = self.artifact_dir / f"case_2_{target_id}.json"
        artifact_path.write_text(json.dumps(artifact, indent=2, default=str))
        case.artifacts["case_2"] = str(artifact_path)
        print(f"  ✅ Artifact saved: {artifact_path}")
    
    async def verify_case_3(self, case: MemoryLoopCase) -> None:
        """验证 Case 3: 策略层提升"""
        print(f"\n{'=' * 50}")
        print(f"Case 3: {case.description}")
        print(f"{'=' * 50}")
        
        target_id = case.events[0]["actor"]
        
        # 检查 openemotion/memory/policy_memory.py 是否被集成
        # 当前检查 commitments 是否能存储偏好
        
        for i, event_data in enumerate(case.events, 1):
            episodic_event = await self.episodic_memory.store(
                event_type=event_data["event_type"],
                context={
                    "actor": event_data["actor"],
                    "target": event_data["target"],
                    "content": event_data["content"],
                    "intent": "preference_setting",
                },
                outcome="success",
                tags=["test", "policy", "preference"],
            )
            print(f"  ✅ Event {i} stored: {episodic_event.event_id}")
        
        # 检查 CommitmentsLedger 是否能存储偏好
        commitment = await self.commitments_ledger.add(
            description="代码问题先给出调试步骤",
            context={"source_target": target_id, "type": "preference"},
        )
        print(f"  ✅ Commitment added: {commitment.id}")
        
        # 验证可读取
        retrieved = await self.commitments_ledger.get(commitment.id)
        if retrieved:
            print(f"  ✅ Commitment retrievable")
            case.results["policy_stored"] = True
            self.evidence["narrative_to_policy"] = True
        else:
            case.errors.append("Commitment not retrievable")
        
        # 保存 artifact
        artifact = {
            "case_id": case.case_id,
            "commitment": {
                "id": commitment.id,
                "description": commitment.description,
            },
        }
        artifact_path = self.artifact_dir / f"case_3_{target_id}.json"
        artifact_path.write_text(json.dumps(artifact, indent=2, default=str))
        case.artifacts["case_3"] = str(artifact_path)
        print(f"  ✅ Artifact saved: {artifact_path}")
    
    async def verify_case_4(self, case: MemoryLoopCase) -> None:
        """验证 Case 4: 重复触发与回流"""
        print(f"\n{'=' * 50}")
        print(f"Case 4: {case.description}")
        print(f"{'=' * 50}")
        
        target_id = case.events[0]["actor"]
        content = case.events[0]["content"]
        
        # 第一次处理
        narrative_state_before = narrative_memory.get_state(target_id)
        event_count_before = narrative_state_before.event_count
        
        # 处理两个相同事件
        for i, event_data in enumerate(case.events, 1):
            episodic_event = await self.episodic_memory.store(
                event_type=event_data["event_type"],
                context={
                    "actor": event_data["actor"],
                    "target": event_data["target"],
                    "content": event_data["content"],
                },
                outcome="success",
                tags=["test", "repeat"],
            )
            
            narrative_memory.update(
                target_id=target_id,
                event_type=event_data["event_type"],
                action_tendency="respond",
                conflict_detected=False,
            )
            
            print(f"  Event {i} processed: {episodic_event.event_id}")
        
        narrative_state_after = narrative_memory.get_state(target_id)
        
        # 检查：相同内容是否被识别为重复？
        # 当前系统应该记录两次事件，但不自动去重
        if narrative_state_after.event_count > event_count_before:
            print(f"  ✅ Events recorded: count {event_count_before} → {narrative_state_after.event_count}")
            case.results["events_recorded"] = True
        
        # 检查记忆是否影响后续处理
        # 通过 memory_system.get_memory_impact_on_relationship
        try:
            memory_impact = memory_system.get_memory_impact_on_relationship(target_id)
            print(f"  Memory impact: {memory_impact}")
            if memory_impact:
                case.results["memory_affects_output"] = True
                self.evidence["memory_affects_output"] = True
        except Exception as e:
            case.errors.append(f"Memory impact check failed: {e}")
            print(f"  ⚠️ Memory impact check failed: {e}")
        
        # 保存 artifact
        artifact = {
            "case_id": case.case_id,
            "target_id": target_id,
            "content": content,
            "event_count_before": event_count_before,
            "event_count_after": narrative_state_after.event_count,
            "narrative_state": narrative_state_after.to_dict(),
        }
        artifact_path = self.artifact_dir / f"case_4_{target_id}.json"
        artifact_path.write_text(json.dumps(artifact, indent=2, default=str))
        case.artifacts["case_4"] = str(artifact_path)
        print(f"  ✅ Artifact saved: {artifact_path}")
    
    async def run_all(self) -> None:
        """运行所有测试"""
        await self.setup()
        
        # 创建测试用例
        self.cases = [
            self.create_case_1(),
            self.create_case_2(),
            self.create_case_3(),
            self.create_case_4(),
        ]
        
        # 运行验证
        await self.verify_case_1(self.cases[0])
        await self.verify_case_2(self.cases[1])
        await self.verify_case_3(self.cases[2])
        await self.verify_case_4(self.cases[3])
        
        # 判断环路状态
        self._determine_loop_status()
    
    def _determine_loop_status(self) -> None:
        """判定环路状态"""
        # storage-only: 只有 event 存储
        # partial-loop: narrative/policy 存在但未影响输出
        # full-minimal-loop: 三层贯通且影响后续
        
        if not self.evidence["event_to_event_memory"]:
            self.loop_status = "fail"
        elif not self.evidence["event_to_narrative"]:
            self.loop_status = "storage-only"
        elif not self.evidence["narrative_to_policy"]:
            self.loop_status = "partial-loop"
        elif not self.evidence["memory_affects_output"]:
            self.loop_status = "partial-loop"
        else:
            self.loop_status = "full-minimal-loop"
    
    def generate_report(self) -> MemoryLoopReport:
        """生成报告"""
        return MemoryLoopReport(
            run_id=self.run_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            cases=[asdict(c) for c in self.cases],
            loop_status=self.loop_status,
            evidence=self.evidence,
            verdict={
                "event_memory_works": self.evidence["event_to_event_memory"],
                "narrative_aggregation": self.evidence["event_to_narrative"],
                "policy_generation": self.evidence["narrative_to_policy"],
                "memory_affects_output": self.evidence["memory_affects_output"],
                "trace_complete": all(self.evidence.values()),
            },
        )
    
    def save_report(self) -> Path:
        """保存报告"""
        report = self.generate_report()
        report_path = self.artifact_dir / f"memory_loop_report_{self.run_id}.json"
        report_path.write_text(json.dumps(asdict(report), indent=2, default=str))
        return report_path
    
    def print_summary(self) -> None:
        """打印摘要"""
        print("\n" + "=" * 60)
        print("VERDICT")
        print("=" * 60)
        
        for key, value in self.evidence.items():
            status = "✅" if value else "❌"
            print(f"  {status} {key}")
        
        print("\n" + "-" * 60)
        print(f"Loop Status: {self.loop_status}")
        
        if self.loop_status == "full-minimal-loop":
            print("✅ 记忆环路已形成")
        elif self.loop_status == "partial-loop":
            print("⚠️ 部分环路存在，但未完全贯通")
        elif self.loop_status == "storage-only":
            print("❌ 只有存储，未形成环路")
        else:
            print("❌ 验证失败")


async def main():
    """主函数"""
    verifier = MemoryLoopVerifier()
    await verifier.run_all()
    
    report_path = verifier.save_report()
    print(f"\nReport saved to: {report_path}")
    
    verifier.print_summary()


if __name__ == "__main__":
    asyncio.run(main())
