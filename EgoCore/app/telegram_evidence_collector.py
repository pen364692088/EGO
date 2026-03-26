"""
Telegram Evidence Collector - E4 真实证据采集

用途: 在 Telegram 消息处理流程中收集完整的 E4 证据包

证据包 6 项:
1. raw_update - 原始 Telegram update
2. normalized_event - 归一化事件
3. openemotion_result - OpenEmotion 结构化结果
4. response_plan - EgoCore 响应计划
5. outbox_record - 实际发送记录
6. timeline/tape/replay - 审计链

使用方式:
    from app.telegram_evidence_collector import TelegramEvidenceCollector

    collector = TelegramEvidenceCollector()
    collector.capture_update(update)
    collector.capture_normalized_event(event)
    collector.capture_openemotion_result(result)
    collector.capture_response_plan(plan)
    collector.capture_outbox_record(record)
    collector.finalize_sample()
"""

import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict, field


@dataclass
class E4EvidenceSample:
    """E4 证据样本"""
    sample_id: str
    timestamp: str
    evidence_level: str = "E4"
    source_type: str = "real_channel"
    channel: str = "telegram"

    # 6 项必需证据
    raw_update: Optional[Dict[str, Any]] = None
    normalized_event: Optional[Dict[str, Any]] = None
    openemotion_result: Optional[Dict[str, Any]] = None
    response_plan: Optional[Dict[str, Any]] = None
    outbox_record: Optional[Dict[str, Any]] = None

    # 审计链
    timeline: List[Dict[str, Any]] = field(default_factory=list)
    tape: Optional[Dict[str, Any]] = None
    replay: Optional[Dict[str, Any]] = None
    replay_hash: Optional[str] = None

    # 完整性检查
    evidence_completeness: Dict[str, bool] = field(default_factory=dict)

    def check_completeness(self) -> Dict[str, bool]:
        """检查证据完整性"""
        self.evidence_completeness = {
            "raw_update": self.raw_update is not None,
            "normalized_event": self.normalized_event is not None,
            "openemotion_result": self.openemotion_result is not None,
            "response_plan": self.response_plan is not None,
            "outbox_record": self.outbox_record is not None,
            "timeline": len(self.timeline) > 0,
            "tape": self.tape is not None,
            "replay": self.replay is not None,
        }
        return self.evidence_completeness

    def is_complete(self) -> bool:
        """检查是否满足最小证据包要求。"""
        completeness = self.check_completeness()
        required = [
            "raw_update",
            "normalized_event",
            "openemotion_result",
            "response_plan",
            "outbox_record",
            "timeline",
            "tape",
            "replay",
        ]
        return all(completeness.get(k, False) for k in required)


class TelegramEvidenceCollector:
    """
    Telegram 证据收集器

    在 Telegram 消息处理流程中嵌入，自动收集 E4 证据。
    """

    def __init__(
        self,
        artifacts_dir: Optional[Path] = None,
        *,
        source_type: str = "real_channel",
        channel: str = "telegram",
        evidence_level: str = "E4",
    ):
        if artifacts_dir is None:
            # 使用绝对路径
            ego_root = Path(__file__).parent.parent.parent
            artifacts_dir = ego_root / "artifacts" / "telegram_real_mainline_v1" / "real_telegram"
        self.artifacts_dir = Path(artifacts_dir)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.source_type = source_type
        self.channel = channel
        self.evidence_level = evidence_level

        self._current_sample: Optional[E4EvidenceSample] = None
        self._samples: List[E4EvidenceSample] = []

    def start_sample(self, update: Dict[str, Any]) -> E4EvidenceSample:
        """开始新样本采集"""
        sample_id = f"sample_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hashlib.md5(str(update.get('update_id', 0)).encode()).hexdigest()[:8]}"

        self._current_sample = E4EvidenceSample(
            sample_id=sample_id,
            timestamp=datetime.now().isoformat(),
            evidence_level=self.evidence_level,
            source_type=self.source_type,
            channel=self.channel,
        )

        # 自动捕获 raw_update
        self.capture_update(update)

        return self._current_sample

    def capture_update(self, update: Dict[str, Any]) -> None:
        """捕获原始 Telegram update"""
        if not self._current_sample:
            return

        # 脱敏：移除敏感信息
        sanitized_update = self._sanitize_update(update)

        self._current_sample.raw_update = sanitized_update
        self._current_sample.timeline.append({
            "stage": "update_received",
            "timestamp": datetime.now().isoformat(),
            "update_id": update.get("update_id"),
        })

    def capture_normalized_event(self, event: Dict[str, Any]) -> None:
        """捕获归一化事件"""
        if not self._current_sample:
            return

        self._current_sample.normalized_event = event
        self._current_sample.timeline.append({
            "stage": "event_normalized",
            "timestamp": datetime.now().isoformat(),
            "event_id": event.get("event_id"),
        })

    def capture_openemotion_result(self, result: Dict[str, Any]) -> None:
        """捕获 OpenEmotion 结构化结果"""
        if not self._current_sample:
            return

        self._current_sample.openemotion_result = result
        self._current_sample.timeline.append({
            "stage": "openemotion_processed",
            "timestamp": datetime.now().isoformat(),
        })

    def capture_response_plan(self, plan: Dict[str, Any]) -> None:
        """捕获 EgoCore 响应计划"""
        if not self._current_sample:
            return

        self._current_sample.response_plan = plan
        self._current_sample.timeline.append({
            "stage": "response_planned",
            "timestamp": datetime.now().isoformat(),
        })

    def capture_outbox_record(self, record: Dict[str, Any]) -> None:
        """捕获实际发送记录"""
        if not self._current_sample:
            return

        self._current_sample.outbox_record = record
        self._current_sample.timeline.append({
            "stage": "message_sent",
            "timestamp": datetime.now().isoformat(),
            "chat_id": record.get("chat_id"),
            "message_id": record.get("message_id"),
        })

    def finalize_sample(self) -> Optional[E4EvidenceSample]:
        """完成样本采集并保存"""
        if not self._current_sample:
            return None

        # 生成 replay hash
        self._current_sample.replay_hash = self._generate_replay_hash()

        # 生成 tape
        self._current_sample.tape = {
            "tape_id": f"tape_{self._current_sample.sample_id}",
            "timestamp": self._current_sample.timestamp,
            "evidence_level": self._current_sample.evidence_level,
            "source_type": self._current_sample.source_type,
            "channel": self._current_sample.channel,
            "update_id": self._current_sample.raw_update.get("update_id") if self._current_sample.raw_update else None,
            "trace_id": self._current_sample.sample_id,
            "normalized_event_id": (
                self._current_sample.normalized_event.get("event_id")
                if self._current_sample.normalized_event else None
            ),
        }
        self._current_sample.replay = self._build_replay()

        # 检查完整性
        self._current_sample.check_completeness()

        # 保存到文件
        self._save_sample(self._current_sample)

        sample = self._current_sample
        self._samples.append(sample)
        self._current_sample = None

        return sample

    def _sanitize_update(self, update: Dict[str, Any]) -> Dict[str, Any]:
        """脱敏处理：移除敏感信息"""
        sanitized = update.copy()

        # 移除可能敏感的字段
        if "message" in sanitized:
            message = sanitized["message"]
            # 保留结构和关键字段，移除个人敏感信息
            sanitized["message"] = {
                "message_id": message.get("message_id"),
                "date": message.get("date"),
                "chat": {
                    "id": message.get("chat", {}).get("id"),
                    "type": message.get("chat", {}).get("type"),
                },
                "from": {
                    "id": message.get("from", {}).get("id"),
                    "is_bot": message.get("from", {}).get("is_bot"),
                    # username 脱敏
                    "username": self._mask_username(message.get("from", {}).get("username")),
                },
                "text": message.get("text", ""),
            }

        return sanitized

    def _mask_username(self, username: Optional[str]) -> Optional[str]:
        """脱敏用户名"""
        if not username:
            return None
        if len(username) <= 3:
            return "***"
        return username[:2] + "*" * (len(username) - 2)

    def _generate_replay_hash(self) -> str:
        """生成可回放哈希"""
        if not self._current_sample:
            return ""

        data = {
            "update_id": self._current_sample.raw_update.get("update_id") if self._current_sample.raw_update else None,
            "timestamp": self._current_sample.timestamp,
            "timeline_length": len(self._current_sample.timeline),
        }

        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:16]

    def _build_replay(self) -> Dict[str, Any]:
        """生成可回放索引。"""
        sample = self._current_sample
        if sample is None:
            return {}
        return {
            "replay_id": f"replay_{sample.sample_id}",
            "timestamp": datetime.now().isoformat(),
            "evidence_level": sample.evidence_level,
            "source_type": sample.source_type,
            "channel": sample.channel,
            "sample_id": sample.sample_id,
            "raw_update_ref": "raw_update.json" if sample.raw_update else None,
            "normalized_event_ref": "normalized_event.json" if sample.normalized_event else None,
            "openemotion_result_ref": "openemotion_result.json" if sample.openemotion_result else None,
            "response_plan_ref": "response_plan.json" if sample.response_plan else None,
            "outbox_record_ref": "outbox_record.json" if sample.outbox_record else None,
            "timeline_ref": "timeline.json" if sample.timeline else None,
            "tape_ref": "tape.json" if sample.tape else None,
            "replay_hash": sample.replay_hash,
        }

    def _save_sample(self, sample: E4EvidenceSample) -> Path:
        """保存样本到文件"""
        sample_dir = self.artifacts_dir / sample.sample_id
        sample_dir.mkdir(parents=True, exist_ok=True)

        # 保存各部分证据
        evidence_files = {
            "raw_update.json": sample.raw_update,
            "normalized_event.json": sample.normalized_event,
            "openemotion_result.json": sample.openemotion_result,
            "response_plan.json": sample.response_plan,
            "outbox_record.json": sample.outbox_record,
            "timeline.json": sample.timeline,
            "tape.json": sample.tape,
            "replay.json": sample.replay,
        }

        for filename, content in evidence_files.items():
            if content is not None:
                with open(sample_dir / filename, "w", encoding="utf-8") as f:
                    json.dump(content, f, indent=2, ensure_ascii=False)

        # 保存完整样本
        with open(sample_dir / "sample.json", "w", encoding="utf-8") as f:
            json.dump(asdict(sample), f, indent=2, ensure_ascii=False)

        # 生成 summary.md
        self._generate_summary(sample, sample_dir)

        return sample_dir

    def _generate_summary(self, sample: E4EvidenceSample, sample_dir: Path) -> None:
        """生成样本摘要"""
        completeness = sample.evidence_completeness

        summary = f"""# E4 证据样本: {sample.sample_id}

## 基本信息

- **样本ID**: {sample.sample_id}
- **时间戳**: {sample.timestamp}
- **证据层级**: {sample.evidence_level}
- **来源类型**: {sample.source_type}
- **渠道**: {sample.channel}

## 证据完整性

| 证据项 | 状态 |
|--------|------|
| raw_update | {"✅" if completeness.get("raw_update") else "❌"} |
| normalized_event | {"✅" if completeness.get("normalized_event") else "❌"} |
| openemotion_result | {"✅" if completeness.get("openemotion_result") else "❌"} |
| response_plan | {"✅" if completeness.get("response_plan") else "❌"} |
| outbox_record | {"✅" if completeness.get("outbox_record") else "❌"} |
| timeline | {"✅" if completeness.get("timeline") else "❌"} |
| tape | {"✅" if completeness.get("tape") else "❌"} |
| replay | {"✅" if completeness.get("replay") else "❌"} |

## 时间线

"""
        for event in sample.timeline:
            summary += f"- {event.get('timestamp', 'N/A')}: {event.get('stage', 'unknown')}\n"

        summary += f"""
## 证明什么

- {sample.channel} 渠道消息成功进入系统
- 消息经过完整处理链路
- 生成了结构化响应

## 不证明什么

- 不证明系统稳定运行
- 不证明关键未知为无
- 不证明已完成观察期
- 不证明跨渠道一致稳定

---
*此样本由 TelegramEvidenceCollector 自动生成*
"""

        with open(sample_dir / "summary.md", "w", encoding="utf-8") as f:
            f.write(summary)

    def get_samples(self) -> List[E4EvidenceSample]:
        """获取所有样本"""
        return self._samples

    def get_complete_samples(self) -> List[E4EvidenceSample]:
        """获取完整样本"""
        return [s for s in self._samples if s.is_complete()]


# 全局收集器实例
_collector: Optional[TelegramEvidenceCollector] = None


def get_evidence_collector() -> TelegramEvidenceCollector:
    """获取全局证据收集器"""
    global _collector
    if _collector is None:
        _collector = TelegramEvidenceCollector()
    return _collector
