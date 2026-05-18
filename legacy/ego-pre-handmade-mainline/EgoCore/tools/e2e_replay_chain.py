"""
EgoCore E2E Replay Chain Demo

演示最小主体闭环：
用户消息 → EgoCore 结构化 → OpenEmotion 更新 → EgoCore 决策 → 结果回写

这个脚本展示完整的 E2E 流程，并生成可审计的 artifact。
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict


@dataclass
class ReplayStep:
    """重放步骤"""
    step_id: str
    step_name: str
    timestamp: str
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    success: bool
    duration_ms: float


class E2EReplayChain:
    """
    E2E 重放链

    实现最小主体闭环，每一步都可审计、可回放。
    """

    def __init__(self, artifact_dir: Optional[Path] = None):
        """
        初始化重放链

        Args:
            artifact_dir: artifact 存储目录
        """
        self.artifact_dir = artifact_dir or Path("./artifacts/e2e_replay")
        self.artifact_dir.mkdir(parents=True, exist_ok=True)

        self.chain_id = f"chain_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        self.steps: List[ReplayStep] = []
        self.start_time: Optional[datetime] = None

        # 导入适配器
        from egocore.adapters.openemotion_adapter import OpenEmotionAdapter, AdapterMode
        self.adapter = OpenEmotionAdapter(mode=AdapterMode.MOCK)

    def run(self, user_message: str, actor_id: str = "user_demo") -> Dict[str, Any]:
        """
        运行完整 E2E 闭环

        Args:
            user_message: 用户消息
            actor_id: 用户 ID

        Returns:
            完整闭环结果
        """
        self.start_time = datetime.now(timezone.utc)

        # Step 1: 用户消息进入
        user_event = self._step_user_message(user_message, actor_id)

        # Step 2: EgoCore 结构化事件
        structured_event = self._step_structure_event(user_event)

        # Step 3: OpenEmotion 更新状态
        emotion_output = self._step_openemotion_update(structured_event)

        # Step 4: EgoCore 决策回复
        response_decision = self._step_decide_response(emotion_output)

        # Step 5: 结果回写 artifact
        artifact = self._step_write_artifact(response_decision)

        return {
            "chain_id": self.chain_id,
            "success": True,
            "steps_count": len(self.steps),
            "final_artifact": str(artifact),
            "summary": self._generate_summary(),
        }

    def _step_user_message(self, message: str, actor_id: str) -> Dict[str, Any]:
        """Step 1: 用户消息进入"""
        start = datetime.now(timezone.utc)

        input_data = {
            "raw_message": message,
            "actor_id": actor_id,
        }

        output_data = {
            "event_id": f"evt_{uuid.uuid4().hex[:12]}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor": {
                "actor_id": actor_id,
                "actor_type": "user",
            },
        }

        duration = (datetime.now(timezone.utc) - start).total_seconds() * 1000

        self.steps.append(ReplayStep(
            step_id="S1",
            step_name="user_message_in",
            timestamp=start.isoformat(),
            input_data=input_data,
            output_data=output_data,
            success=True,
            duration_ms=duration,
        ))

        return output_data

    def _step_structure_event(self, user_event: Dict[str, Any]) -> Dict[str, Any]:
        """Step 2: EgoCore 结构化事件"""
        start = datetime.now(timezone.utc)

        input_data = user_event.copy()

        # 构造完整的 EventInput
        output_data = {
            "event_id": user_event["event_id"],
            "timestamp": user_event["timestamp"],
            "actor": user_event["actor"],
            "source": {
                "channel": "telegram",
                "surface": "telegram",
                "session_id": f"session_{uuid.uuid4().hex[:8]}",
            },
            "event_type": "user_message",
            "user_intent": {
                "primary_intent": "task_request",
                "confidence": 0.9,
            },
            "safety_context": {
                "risk_level": "low",
                "flags": [],
            },
            "task_context": {
                "task_id": self.chain_id,
                "task_status": "running",
            },
        }

        duration = (datetime.now(timezone.utc) - start).total_seconds() * 1000

        self.steps.append(ReplayStep(
            step_id="S2",
            step_name="structure_event",
            timestamp=start.isoformat(),
            input_data=input_data,
            output_data=output_data,
            success=True,
            duration_ms=duration,
        ))

        return output_data

    def _step_openemotion_update(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Step 3: OpenEmotion 更新状态"""
        start = datetime.now(timezone.utc)

        input_data = event.copy()

        # 调用 adapter
        output_data = self.adapter.process_event(event)

        duration = (datetime.now(timezone.utc) - start).total_seconds() * 1000

        self.steps.append(ReplayStep(
            step_id="S3",
            step_name="openemotion_update",
            timestamp=start.isoformat(),
            input_data=input_data,
            output_data=output_data,
            success=True,
            duration_ms=duration,
        ))

        return output_data

    def _step_decide_response(self, emotion_output: Dict[str, Any]) -> Dict[str, Any]:
        """Step 4: EgoCore 决策回复"""
        start = datetime.now(timezone.utc)

        input_data = emotion_output.copy()

        # 基于 emotion_output 决策响应
        policy_hint = emotion_output.get("policy_hint", {})
        response_tendency = emotion_output.get("response_tendency", {})

        action_type = policy_hint.get("preferred_action_type", "respond")
        tone = response_tendency.get("tone", "neutral")

        output_data = {
            "decision_id": f"dec_{uuid.uuid4().hex[:8]}",
            "action_type": action_type,
            "tone": tone,
            "response_content": self._generate_response(tone),
            "confidence": emotion_output.get("confidence_metadata", {}).get("overall_confidence", 0.5),
        }

        duration = (datetime.now(timezone.utc) - start).total_seconds() * 1000

        self.steps.append(ReplayStep(
            step_id="S4",
            step_name="decide_response",
            timestamp=start.isoformat(),
            input_data=input_data,
            output_data=output_data,
            success=True,
            duration_ms=duration,
        ))

        return output_data

    def _step_write_artifact(self, decision: Dict[str, Any]) -> Path:
        """Step 5: 结果回写 artifact"""
        start = datetime.now(timezone.utc)

        input_data = decision.copy()

        # 写入 artifact 文件
        artifact_file = self.artifact_dir / f"{self.chain_id}.json"

        artifact = {
            "chain_id": self.chain_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "steps": [asdict(s) for s in self.steps],
            "final_decision": decision,
            "replayable": True,
            "audit_trail": self._generate_audit_trail(),
        }

        with open(artifact_file, 'w') as f:
            json.dump(artifact, f, indent=2)

        output_data = {
            "artifact_path": str(artifact_file),
            "artifact_size_bytes": artifact_file.stat().st_size,
        }

        duration = (datetime.now(timezone.utc) - start).total_seconds() * 1000

        self.steps.append(ReplayStep(
            step_id="S5",
            step_name="write_artifact",
            timestamp=start.isoformat(),
            input_data=input_data,
            output_data=output_data,
            success=True,
            duration_ms=duration,
        ))

        return artifact_file

    def _generate_response(self, tone: str) -> str:
        """生成响应内容"""
        if tone == "warm":
            return "好的，我来帮你处理这个任务。"
        elif tone == "cautious":
            return "让我仔细考虑一下这个请求。"
        else:
            return "收到，正在处理。"

    def _generate_summary(self) -> Dict[str, Any]:
        """生成摘要"""
        total_duration = sum(s.duration_ms for s in self.steps)
        return {
            "total_steps": len(self.steps),
            "total_duration_ms": round(total_duration, 2),
            "all_steps_successful": all(s.success for s in self.steps),
        }

    def _generate_audit_trail(self) -> List[Dict[str, Any]]:
        """生成审计线索"""
        trail = []
        for step in self.steps:
            trail.append({
                "step_id": step.step_id,
                "step_name": step.step_name,
                "timestamp": step.timestamp,
                "success": step.success,
                "input_hash": self._hash_data(step.input_data),
                "output_hash": self._hash_data(step.output_data),
            })
        return trail

    @staticmethod
    def _hash_data(data: Dict[str, Any]) -> str:
        """计算数据哈希"""
        import hashlib
        return hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()[:16]


def run_demo():
    """运行演示"""
    print("=" * 60)
    print("EgoCore E2E Replay Chain Demo")
    print("=" * 60)

    # 创建重放链
    chain = E2EReplayChain(
        artifact_dir=Path("/home/moonlight/Project/Github/MyProject/EgoCore/artifacts/e2e_replay")
    )

    # 运行闭环
    result = chain.run(
        user_message="帮我检查这个代码",
        actor_id="user_moonlight"
    )

    print(f"\nChain ID: {result['chain_id']}")
    print(f"Success: {result['success']}")
    print(f"Steps: {result['steps_count']}")
    print(f"Artifact: {result['final_artifact']}")

    # 打印步骤摘要
    print("\nSteps Summary:")
    for step in chain.steps:
        print(f"  [{step.step_id}] {step.step_name}: {step.duration_ms:.2f}ms")

    print("\n" + "=" * 60)
    print("Replay Chain Complete")
    print("=" * 60)

    return result


if __name__ == "__main__":
    run_demo()
