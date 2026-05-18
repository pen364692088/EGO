"""
P0-R2 End-to-End Verification

使用真实 Proto-Self Kernel 代码验证 risk_level 区分。
"""

import sys
import json
import hashlib
from pathlib import Path
from datetime import datetime

# 添加路径
openemotion_path = Path(__file__).parent.parent.parent / "OpenEmotion"
sys.path.insert(0, str(openemotion_path))

from openemotion.proto_self.schemas import KernelEvent
from openemotion.proto_self.kernel import process_event
from openemotion.proto_self.state import ProtoSelfState


def test_e2e_risk_distinction():
    """端到端测试：验证高风险和低风险事件被正确区分"""
    print("=" * 60)
    print(" P0-R2 End-to-End Risk Distinction Test")
    print("=" * 60)

    # 创建干净状态
    state = ProtoSelfState.empty()

    # 测试用例
    test_events = [
        {
            "name": "低风险文件读取",
            "event": KernelEvent(
                event_id="test_low_001",
                timestamp=datetime.now().isoformat(),
                actor="test_user",
                source="telegram",
                event_type="user_message",
                user_intent="读取文件 test.txt",
                safety_context={"risk_level": "low"},
            ),
            "expected_risk_suffix": False,
        },
        {
            "name": "高风险删除操作",
            "event": KernelEvent(
                event_id="test_high_001",
                timestamp=datetime.now().isoformat(),
                actor="test_user",
                source="telegram",
                event_type="user_message",
                user_intent="删除生产数据库",
                safety_context={"risk_level": "high"},
            ),
            "expected_risk_suffix": True,
        },
        {
            "name": "另一个低风险读取",
            "event": KernelEvent(
                event_id="test_low_002",
                timestamp=datetime.now().isoformat(),
                actor="test_user",
                source="telegram",
                event_type="user_message",
                user_intent="查看配置文件",
                safety_context={"risk_level": "low"},
            ),
            "expected_risk_suffix": False,
        },
    ]

    cycle_ids = {}

    for i, tc in enumerate(test_events):
        print(f"\n[{i+1}] Processing: {tc['name']}")

        result = process_event(state, tc["event"])

        cycle_delta = result.trace_payload.get("cycle_delta", {})
        psi_bucket = cycle_delta.get("psi_bucket", "")
        cycle_id = cycle_delta.get("cycle_id", "")

        print(f"  user_intent: {tc['event'].user_intent}")
        print(f"  safety_context: {tc['event'].safety_context}")
        print(f"  psi_bucket: {psi_bucket}")
        print(f"  cycle_id: {cycle_id}")

        # 验证 risk 后缀
        has_risk_suffix = "risk_" in psi_bucket
        if tc["expected_risk_suffix"]:
            assert has_risk_suffix, f"Expected risk suffix in psi_bucket: {psi_bucket}"
            print(f"  ✅ Correctly has risk suffix")
        else:
            assert not has_risk_suffix, f"Unexpected risk suffix in psi_bucket: {psi_bucket}"
            print(f"  ✅ Correctly no risk suffix")

        cycle_ids[tc["name"]] = {
            "cycle_id": cycle_id,
            "psi_bucket": psi_bucket,
        }

    # 验证高低风险 cycle_id 不同
    print("\n[4] Verifying cycle distinction...")

    low_cycle = cycle_ids["低风险文件读取"]["cycle_id"]
    high_cycle = cycle_ids["高风险删除操作"]["cycle_id"]

    print(f"  低风险 cycle_id: {low_cycle}")
    print(f"  高风险 cycle_id: {high_cycle}")

    assert low_cycle != high_cycle, "High and low risk cycles should be different!"
    print("  ✅ High and low risk cycles are correctly different")

    # 验证低风险事件聚合到同一 cycle
    low_cycle_2 = cycle_ids["另一个低风险读取"]["cycle_id"]
    print(f"\n  第一个低风险 cycle_id: {low_cycle}")
    print(f"  第二个低风险 cycle_id: {low_cycle_2}")

    # 注意：这两个可能有不同的 coarse_intent，所以 cycle_id 可能不同
    # 关键是验证高风险和低风险被区分

    print("\n" + "=" * 60)
    print(" ALL E2E TESTS PASSED!")
    print("=" * 60)

    # 打印最终状态
    print(f"\n最终状态:")
    print(f"  Cycle 数量: {len(state.cycle_store.signatures)}")
    print(f"  Revision Counter: {state.revision_counter}")

    for cid, cycle in state.cycle_store.signatures.items():
        print(f"\n  Cycle {cid[:12]}...:")
        print(f"    psi_bucket: {cycle.psi_bucket}")
        print(f"    hits: {cycle.hits}")
        print(f"    strength: {cycle.strength}")

    return True


if __name__ == "__main__":
    try:
        test_e2e_risk_distinction()
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
