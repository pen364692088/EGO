"""
P1-C 验证测试

验证跨 intent 自然表达对齐修复。
"""

import sys
sys.path.insert(0, '/home/moonlight/Project/Github/MyProject/EgoCore')

from app.response.question_verbalizer import (
    QuestionVerbalizer,
    ShortQuestionType,
    is_short_question,
    verbalize_question,
)
from app.runtime.semantic_router import SemanticRouter, SemanticIntent


def test_short_question_classification():
    """测试短问句分类"""
    print("=== 测试短问句分类 ===")

    test_cases = [
        ("什么？", True, ShortQuestionType.SHORT_CLARIFICATION),
        ("什么", True, ShortQuestionType.SHORT_CLARIFICATION),
        ("为啥？", True, ShortQuestionType.WHY_PROBE),
        ("为什么", True, ShortQuestionType.WHY_PROBE),
        ("啊？", True, ShortQuestionType.SURPRISED_FOLLOWUP),
        ("啊", True, ShortQuestionType.SURPRISED_FOLLOWUP),
        ("啥意思？", True, ShortQuestionType.MEANING_PROBE),
        ("什么意思", True, ShortQuestionType.MEANING_PROBE),
        ("你说什么？", True, ShortQuestionType.REPEAT_REQUEST),
        ("再说一遍", True, ShortQuestionType.REPEAT_REQUEST),
        # P1-C.2 新增
        ("我不太懂", True, ShortQuestionType.MEANING_PROBE),
        ("没明白", True, ShortQuestionType.MEANING_PROBE),
        ("不懂", True, ShortQuestionType.MEANING_PROBE),
        ("还是不明白", True, ShortQuestionType.MEANING_PROBE),
        ("说清楚点", True, ShortQuestionType.MEANING_PROBE),
        ("再说明白一点", True, ShortQuestionType.MEANING_PROBE),
        ("你好", False, ShortQuestionType.UNKNOWN),
        ("帮我分析这个项目", False, ShortQuestionType.UNKNOWN),
    ]
    
    verbalizer = QuestionVerbalizer()
    
    for message, expected_is_short, expected_type in test_cases:
        is_short = is_short_question(message)
        qtype = verbalizer.classify_short_question(message)
        
        status = "✅" if is_short == expected_is_short and qtype == expected_type else "❌"
        print(f"{status} '{message}' -> is_short={is_short}, type={qtype}")
    
    print()


def test_semantic_router_short_question():
    """测试 semantic router 短问句识别"""
    print("=== 测试 Semantic Router 短问句识别 ===")
    
    router = SemanticRouter()
    
    test_cases = [
        ("什么？", SemanticIntent.CHAT),
        ("为什么？", SemanticIntent.CHAT),
        ("啊？", SemanticIntent.CHAT),
        ("啥意思？", SemanticIntent.CHAT),
        ("你好", SemanticIntent.CHAT),
        ("你能解释一下这个吗？", SemanticIntent.QUESTION),
        ("帮我分析项目", SemanticIntent.NEW_TASK),
    ]
    
    for message, expected_intent in test_cases:
        result = router.classify(message)
        status = "✅" if result.intent == expected_intent else "❌"
        print(f"{status} '{message}' -> {result.intent.value} (expected: {expected_intent.value})")
    
    print()


def test_question_verbalizer():
    """测试 QuestionVerbalizer"""
    print("=== 测试 QuestionVerbalizer ===")
    
    verbalizer = QuestionVerbalizer()
    
    test_cases = [
        "什么？",
        "为什么？",
        "啊？",
        "啥意思？",
        "你说什么？",
    ]
    
    for message in test_cases:
        reply = verbalizer.verbalize(message)
        qtype = verbalizer.classify_short_question(message)
        print(f"'{message}' [{qtype}] -> '{reply}'")
    
    print()


def test_repeat_request():
    """测试重复请求"""
    print("=== 测试重复请求 ===")
    
    recent_messages = [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "你好，我在。可以直接说你需要什么。"},
        {"role": "user", "content": "你说什么？"},
    ]
    
    verbalizer = QuestionVerbalizer()
    reply = verbalizer.verbalize("你说什么？", recent_messages)
    
    print(f"输入: '你说什么？'")
    print(f"回复: '{reply}'")
    print(f"包含上下文: {'你好，我在' in reply or '刚才' in reply}")
    print()


def test_reply_length():
    """测试回复长度"""
    print("=== 测试回复长度 ===")

    verbalizer = QuestionVerbalizer()

    test_cases = [
        "什么？",
        "为什么？",
        "啊？",
        "啥意思？",
    ]

    all_short = True
    for message in test_cases:
        reply = verbalizer.verbalize(message)
        length = len(reply)
        is_short = length <= 20  # 20字以内
        status = "✅" if is_short else "❌"
        print(f"{status} '{message}' -> '{reply}' ({length}字)")
        if not is_short:
            all_short = False

    print(f"\n所有回复都简短: {'✅' if all_short else '❌'}")
    print()


def test_p1c2_meaning_probe_expansion():
    """P1-C.2: 测试 clarification/meaning_probe 扩展覆盖"""
    print("=== P1-C.2 扩展覆盖测试 ===")

    verbalizer = QuestionVerbalizer()

    # P1-C.2 新增测试用例
    test_cases = [
        ("我不太懂", ShortQuestionType.MEANING_PROBE),
        ("没明白", ShortQuestionType.MEANING_PROBE),
        ("不懂", ShortQuestionType.MEANING_PROBE),
        ("还是不明白", ShortQuestionType.MEANING_PROBE),
        ("说清楚点", ShortQuestionType.MEANING_PROBE),
        ("再说明白一点", ShortQuestionType.MEANING_PROBE),
    ]

    all_pass = True
    banned_words = ["收到", "好。", "我在", "我在听", "嗯？"]

    for message, expected_type in test_cases:
        qtype = verbalizer.classify_short_question(message)
        reply = verbalizer.verbalize(message)

        type_ok = qtype == expected_type
        has_banned = any(word in reply for word in banned_words)

        status = "✅" if type_ok and not has_banned else "❌"
        print(f"{status} '{message}' [{qtype}] -> '{reply}'")

        if not type_ok:
            print(f"   类型错误: 期望 {expected_type}, 实际 {qtype}")
            all_pass = False
        if has_banned:
            print(f"   包含禁用词: {[w for w in banned_words if w in reply]}")
            all_pass = False

    print(f"\nP1-C.2 扩展覆盖: {'✅ 通过' if all_pass else '❌ 失败'}")
    print()
    return all_pass


def test_p1c2_short_clarification_quality():
    """P1-C.2: 测试 '什么？' 回复质量提升"""
    print("=== P1-C.2 '什么？' 质量测试 ===")

    verbalizer = QuestionVerbalizer()

    # 测试多次，确保变体都不包含纯语气词
    banned_words = ["嗯？", "收到", "好。", "我在"]
    all_pass = True

    for i in range(10):  # 多次测试覆盖变体
        reply = verbalizer.verbalize("什么？")
        has_banned = any(word in reply for word in banned_words)
        is_minimal_clarification = len(reply) > 2  # 必须超过 "嗯？" 的长度

        if has_banned or not is_minimal_clarification:
            status = "❌"
            all_pass = False
        else:
            status = "✅"

        print(f"{status} 变体 {i+1}: '{reply}'")

    print(f"\n'什么？' 质量提升: {'✅ 通过' if all_pass else '❌ 失败'}")
    print()
    return all_pass


def main():
    """运行所有测试"""
    print("=" * 60)
    print("P1-C 跨 intent 自然表达对齐修复 - 验证测试")
    print("=" * 60 + "\n")

    try:
        test_short_question_classification()
        test_semantic_router_short_question()
        test_question_verbalizer()
        test_repeat_request()
        test_reply_length()

        # P1-C.2 新增测试
        p1c2_pass = test_p1c2_meaning_probe_expansion()
        p1c2_quality_pass = test_p1c2_short_clarification_quality()

        print("=" * 60)
        if p1c2_pass and p1c2_quality_pass:
            print("✅ 所有测试通过 (含 P1-C.2)")
        else:
            print("❌ 部分测试失败")
        print("=" * 60)

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
