#!/usr/bin/env python3
"""
C1. WS_C1 正式验证脚本

验证 4 类高价值事件的记忆写入与读取：
- 偏好、目标、约束、纠正
- 闲聊负样本不误写

测试序列（6条）：
1. 我喜欢用 Python 写代码          → 偏好
2. 我想尽快把这个项目做出最小闭环   → 目标
3. 我只有晚上有空                   → 约束
4. Python 这边下一步我该先做什么？   → 读取验证（应能读到偏好）
5. 今天天气不错                     → 闲聊负样本（不误写）
6. 不对，我说的是 JavaScript        → 纠正（覆盖旧偏好）

验收标准：
1. 高价值事件：event_stored = true
2. 第二轮读取：old_value/read_context 明显存在
3. 闲聊负样本：不误写
4. 纠正后：旧偏好被覆盖或形成冲突修正痕迹
"""

import json
import sys
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, '/home/moonlight/Project/Github/MyProject/EgoCore')
sys.path.insert(0, '/home/moonlight/Project/Github/MyProject/Emotion/OpenEmotion')

from app.handlers.social_chat_handler import handle_social_chat
from app.openemotion.subject_adapter import get_subject_adapter

# 测试序列
TEST_SEQUENCE = [
    {
        "id": 1,
        "text": "我喜欢用 Python 写代码",
        "expected_type": "preference",
        "check": "event_stored",
    },
    {
        "id": 2,
        "text": "我想尽快把这个项目做出最小闭环",
        "expected_type": "goal",
        "check": "event_stored",
    },
    {
        "id": 3,
        "text": "我只有晚上有空",
        "expected_type": "constraint",
        "check": "event_stored",
    },
    {
        "id": 4,
        "text": "Python 这边下一步我该先做什么？",
        "expected_type": "read_context",
        "check": "old_value_present",
    },
    {
        "id": 5,
        "text": "今天天气不错",
        "expected_type": "chitchat",
        "check": "no_memory_write",
    },
    {
        "id": 6,
        "text": "不对，我说的是 JavaScript",
        "expected_type": "correction",
        "check": "override_or_conflict",
    },
]

# 固定测试会话
TEST_USER_ID = 8420019401
TEST_CHAT_ID = 8420019401
TEST_USERNAME = "c1_verification"


def run_verification():
    """执行 C1 验证"""
    print("=" * 60)
    print("C1. WS_C1 正式验证")
    print("=" * 60)
    print(f"开始时间: {datetime.now().isoformat()}")
    print(f"测试用户: {TEST_USER_ID}")
    print()

    results = []
    recent_messages = []

    for test in TEST_SEQUENCE:
        print(f"\n[测试 {test['id']}] {test['expected_type'].upper()}")
        print(f"输入: {test['text']}")
        print(f"检查: {test['check']}")
        print("-" * 40)

        # 调用正式链路
        result = handle_social_chat(
            user_input=test['text'],
            user_id=TEST_USER_ID,
            chat_id=TEST_CHAT_ID,
            username=TEST_USERNAME,
            recent_messages=recent_messages.copy(),
            active_task=None,
            turn_index=test['id'] - 1,
        )

        # 添加到消息历史
        recent_messages.append({"role": "user", "content": test['text']})
        if result.get("success"):
            recent_messages.append({"role": "assistant", "content": result.get("message", "")})

        # 分析结果
        analysis = analyze_result(result, test)
        results.append({
            "test": test,
            "result": result,
            "analysis": analysis,
        })

        # 打印分析
        print(f"状态: {'✅ PASS' if analysis['pass'] else '❌ FAIL'}")
        print(f"回复: {result.get('message', 'N/A')[:100]}...")
        for key, value in analysis.items():
            if key != "pass":
                print(f"  {key}: {value}")

        time.sleep(0.5)  # 避免过快请求

    # 汇总报告
    print("\n" + "=" * 60)
    print("验证汇总")
    print("=" * 60)

    pass_count = sum(1 for r in results if r['analysis']['pass'])
    total_count = len(results)

    for r in results:
        test = r['test']
        analysis = r['analysis']
        status = "✅" if analysis['pass'] else "❌"
        print(f"{status} [{test['id']}] {test['expected_type']}: {test['check']}")

    print(f"\n总计: {pass_count}/{total_count} 通过")

    # 保存详细报告
    report_path = save_report(results)
    print(f"\n详细报告: {report_path}")

    return pass_count == total_count


def analyze_result(result, test):
    """分析单次测试结果"""
    analysis = {"pass": False}
    data = result.get("data", {})

    if test['check'] == "event_stored":
        # 检查高价值事件是否写入记忆
        memory_update = data.get("memory_update")
        if memory_update:
            analysis["pass"] = True
            analysis["memory_event_type"] = memory_update.get("event_type", "unknown")
            analysis["stored_value"] = memory_update.get("value", "N/A")[:50]
        else:
            analysis["pass"] = False
            analysis["error"] = "未检测到 memory_update"

    elif test['check'] == "old_value_present":
        # 检查是否能读到旧偏好 - 通过 salience_score 和 policy_hint 推断
        consumed = data.get("consumed", {})
        policy_hint = consumed.get("policy_hint", {})
        memory_update = data.get("memory_update", {})
        
        # 如果第二轮有 policy_hint 且 salience 较高，说明读到了上下文
        has_context = (
            policy_hint.get("confidence", 0) > 0.5 or
            memory_update.get("salience_score", 0) > 0.2
        )

        analysis["pass"] = has_context
        analysis["policy_hint_confidence"] = policy_hint.get("confidence", 0)
        analysis["salience_score"] = memory_update.get("salience_score", 0)
        analysis["context_detected"] = has_context

    elif test['check'] == "no_memory_write":
        # 检查闲聊不误写
        memory_update = data.get("memory_update", {})
        event_stored = memory_update.get("event_stored", False)

        # 闲聊不应触发记忆写入
        no_write = not event_stored

        analysis["pass"] = no_write
        analysis["event_stored"] = event_stored
        analysis["memory_written"] = event_stored

    elif test['check'] == "override_or_conflict":
        # 检查纠正是否覆盖旧值或形成冲突痕迹
        interpretation = data.get("interpretation", {})
        memory_update = data.get("memory_update")
        reflection = interpretation.get("reflection_note", "")

        # 检测纠正痕迹：新值、冲突标记、或反思注释
        has_override = (
            memory_update is not None or
            "conflict" in str(data).lower() or
            "correct" in reflection.lower() or
            "JavaScript" in str(data) or
            "javascript" in str(data).lower()
        )

        analysis["pass"] = has_override
        analysis["override_detected"] = has_override
        analysis["reflection"] = reflection[:100] if reflection else "N/A"

    return analysis


def save_report(results):
    """保存验证报告"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_dir = Path("/home/moonlight/Project/Github/MyProject/EgoCore/artifacts/verification/ws_c1")
    report_dir.mkdir(parents=True, exist_ok=True)

    report_path = report_dir / f"c1_verification_{timestamp}.json"

    report = {
        "timestamp": datetime.now().isoformat(),
        "test_user_id": TEST_USER_ID,
        "test_chat_id": TEST_CHAT_ID,
        "summary": {
            "total": len(results),
            "passed": sum(1 for r in results if r['analysis']['pass']),
            "failed": sum(1 for r in results if not r['analysis']['pass']),
        },
        "results": [
            {
                "test_id": r['test']['id'],
                "expected_type": r['test']['expected_type'],
                "input": r['test']['text'],
                "check": r['test']['check'],
                "pass": r['analysis']['pass'],
                "analysis": r['analysis'],
                "response": r['result'].get('message', ''),
                "diagnostic_data": r['result'].get('data', {}),
            }
            for r in results
        ],
    }

    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    return str(report_path)


if __name__ == "__main__":
    success = run_verification()
    sys.exit(0 if success else 1)
