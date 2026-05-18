"""
Proto-Self Kernel Trace Bridge

Trace 写入桥接：把 Proto-Self Kernel trace 导出为兼容镜像。

设计约束：
- 只做兼容镜像写入，不做主账本
- 不改变 trace 内容
- 主账本存在时，bridge 只能作为 fallback / mirror
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


class ProtoSelfTraceBridge:
    """
    Proto-Self Kernel trace 兼容桥接器。
    
    职责：
    - 接收 kernel 输出的 trace_payload
    - 写入兼容 jsonl 镜像
    - 供历史回放/调试读取
    """

    def __init__(
        self,
        trace_file: Optional[Path] = None,
        trace_dir: Optional[Path] = None,
    ):
        if trace_file:
            self.trace_file = trace_file
        elif trace_dir:
            self.trace_file = trace_dir / "proto_self_trace.jsonl"
        else:
            self.trace_file = Path("logs/proto_self_trace.jsonl")

        self.trace_file.parent.mkdir(parents=True, exist_ok=True)

    def write(self, trace_payload: Dict[str, Any]) -> None:
        """写入 trace payload。"""
        # 确保有 timestamp
        if "timestamp" not in trace_payload or not trace_payload["timestamp"]:
            trace_payload["timestamp"] = datetime.now().isoformat()

        # 追加写入
        with open(self.trace_file, "a") as f:
            f.write(json.dumps(trace_payload, default=str) + "\n")

    def read_traces(
        self,
        event_id: Optional[str] = None,
        limit: int = 100,
    ) -> list:
        """读取 trace 记录。"""
        traces = []
        if not self.trace_file.exists():
            return traces

        with open(self.trace_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    trace = json.loads(line)
                    if event_id is None or trace.get("event_id") == event_id:
                        traces.append(trace)
                except json.JSONDecodeError:
                    continue

        return traces[-limit:]

    def get_latest_trace(self) -> Optional[Dict[str, Any]]:
        """获取最新的 trace 记录。"""
        traces = self.read_traces(limit=1)
        return traces[0] if traces else None

    def clear(self) -> None:
        """清空 trace 文件。"""
        if self.trace_file.exists():
            self.trace_file.unlink()
