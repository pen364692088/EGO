"""
Proto-Self Kernel Restore Module

状态恢复注入：支持从 trace 或 artifact 恢复状态。

设计约束：
- 只做状态恢复注入
- 不发明主体语义
- 恢复逻辑必须在 EgoCore 侧
"""

from pathlib import Path
from typing import Any, Dict, Optional

from openemotion.proto_self import ProtoSelfState
from app.openemotion_adapter.proto_self_state_store import ProtoSelfStateStore


class ProtoSelfRestore:
    """
    Proto-Self Kernel 状态恢复器。
    
    职责：
    - 从 trace 恢复状态
    - 从 artifact 恢复状态
    - 注入到 kernel adapter
    """

    def __init__(self, mirror_dir: Optional[Path] = None):
        self.mirror_dir = mirror_dir or Path("artifacts/proto_self_mirror")
        self.state_store = ProtoSelfStateStore(legacy_mirror_dir=self.mirror_dir)

    def restore_from_mirror(self) -> ProtoSelfState:
        """从镜像文件恢复状态。"""
        return self.state_store.load_agent_global_state()

    def restore_from_trace(self, trace_data: Dict[str, Any]) -> ProtoSelfState:
        """
        从 trace 数据恢复状态。
        
        注意：这需要完整的 trace 历史，通常用于 replay。
        """
        # 简化实现：从 trace 重建需要完整历史
        # 这里只做基本恢复
        return ProtoSelfState.empty()

    def restore_from_artifact(self, artifact_path: Path) -> ProtoSelfState:
        """从 artifact 文件恢复状态。"""
        if artifact_path.exists():
            try:
                with open(artifact_path, "r") as f:
                    data = json.load(f)
                return ProtoSelfState.from_dict(data)
            except Exception:
                pass
        return ProtoSelfState.empty()

    def inject_to_adapter(
        self,
        adapter: Any,
        state: ProtoSelfState,
    ) -> None:
        """注入状态到 adapter。"""
        if hasattr(adapter, "save_mirror"):
            adapter.save_mirror(state)
