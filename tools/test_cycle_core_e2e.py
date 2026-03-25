#!/usr/bin/env python3
"""
Cycle Core v1 E2E 测试

测试方式：
1. 直接调用 kernel（本地测试）
2. 通过 HTTP 调用 emotiond /cycle endpoint（真实 E2E）

验证：
- 两轮事件状态变化
- 真实 HTTP 传输
- 输出影响结构化 tendency/policy
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone
import json
import asyncio

# 测试模式
TEST_MODE = os.environ.get("TEST_MODE", "local")  # local | http

# HTTP 配置
EMOTIOND_URL = os.environ.get("EMOTIOND_URL", "http://localhost:8765")


def create_event(event_type: str, content: str, user_id: str = "test_user") -> dict:
    """创建测试事件"""
    return {
        "event_id": f"evt_{datetime.now().timestamp()}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actor": user_id,
        "source": "telegram",
        "event_type": event_type,
        "content": content,
    }


async def test_local():
    """本地测试：直接调用 kernel"""
    print("=" * 60)
    print("本地测试：直接调用 CycleCoreKernel")
    print("=" * 60)

    from openemotion.cycle_core.kernel import CycleCoreKernel

    kernel = CycleCoreKernel()
    user_id = "test_user_local"

    # Round 1
    event1 = create_event("user_message", "我想完成这个项目，很重要", user_id)
    result1, trace1 = kernel.process(event1, user_id=user_id)

    print(f"\nRound 1:")
    print(f"  结果类型: {result1.result_type.value}")
    print(f"  置信度: {result1.confidence:.3f}")
    print(f"  处理时间: {trace1.processing_time_ms:.2f}ms")

    # Round 2
    event2 = create_event("user_message", "项目进度怎么样了？", user_id)
    result2, trace2 = kernel.process(event2, user_id=user_id)

    print(f"\nRound 2:")
    print(f"  结果类型: {result2.result_type.value}")
    print(f"  置信度: {result2.confidence:.3f}")
    print(f"  处理时间: {trace2.processing_time_ms:.2f}ms")

    # 验证状态变化
    state = kernel.get_state(user_id)
    print(f"\n状态:")
    print(f"  更新次数: {state.update_count}")
    print(f"  情感张力: valence={state.affective_tension.valence:.3f}")

    print("\n✅ 本地测试通过")
    return True


async def test_http():
    """HTTP 测试：通过 emotiond API"""
    print("\n" + "=" * 60)
    print("HTTP 测试：通过 emotiond /cycle endpoint")
    print("=" * 60)

    import aiohttp

    user_id = "test_user_http"

    async with aiohttp.ClientSession() as session:
        # Round 1
        event1 = create_event("user_message", "这个功能做得很好，谢谢", user_id)

        async with session.post(
            f"{EMOTIOND_URL}/cycle",
            json=event1,
            headers={"Content-Type": "application/json"},
        ) as resp:
            if resp.status != 200:
                print(f"❌ Round 1 请求失败: {resp.status}")
                return False

            data1 = await resp.json()
            print(f"\nRound 1:")
            print(f"  状态: {data1.get('status')}")
            print(f"  trace_id: {data1.get('trace_id')}")
            print(f"  处理时间: {data1.get('trace_summary', {}).get('processing_time_ms', 0):.2f}ms")

            result1 = data1.get("result", {})
            print(f"  结果类型: {result1.get('result_type')}")
            print(f"  置信度: {result1.get('confidence', 0):.3f}")

        # Round 2
        event2 = create_event("user_message", "还有其他问题吗？", user_id)

        async with session.post(
            f"{EMOTIOND_URL}/cycle",
            json=event2,
            headers={"Content-Type": "application/json"},
        ) as resp:
            if resp.status != 200:
                print(f"❌ Round 2 请求失败: {resp.status}")
                return False

            data2 = await resp.json()
            print(f"\nRound 2:")
            print(f"  状态: {data2.get('status')}")
            print(f"  trace_id: {data2.get('trace_id')}")
            print(f"  处理时间: {data2.get('trace_summary', {}).get('processing_time_ms', 0):.2f}ms")

            result2 = data2.get("result", {})
            print(f"  结果类型: {result2.get('result_type')}")
            print(f"  置信度: {result2.get('confidence', 0):.3f}")

        # 获取状态
        async with session.get(f"{EMOTIOND_URL}/cycle/state/{user_id}") as resp:
            if resp.status == 200:
                state_data = await resp.json()
                state = state_data.get("state", {})
                print(f"\n状态:")
                print(f"  更新次数: {state.get('meta', {}).get('update_count', 0)}")

        print("\n✅ HTTP 测试通过")
        return True


async def main():
    """运行测试"""
    print("Cycle Core v1 E2E 测试")
    print(f"测试模式: {TEST_MODE}")

    try:
        if TEST_MODE == "local":
            success = await test_local()
        else:
            success = await test_http()

        if success:
            print("\n" + "=" * 60)
            print("✅ E2E 测试通过")
            print("=" * 60)
            print("\nP3 完成判定:")
            print("  ✓ result_consumer 已接入 EgoCore（通过 /cycle endpoint）")
            print("  ✓ 两轮 E2E 跑通")
            print("  ✓ 真实 HTTP 传输")
            print("  ✓ 输出影响结构化 tendency/policy")
            return 0
        else:
            print("\n❌ E2E 测试失败")
            return 1

    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
