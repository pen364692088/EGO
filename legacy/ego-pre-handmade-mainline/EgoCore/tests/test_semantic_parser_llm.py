"""
统一语义解析器 LLM 集成测试

验证 semantic_parse_message() 与真实 LLM 的集成。
"""

import pytest
from app.runtime_v2.semantic_parser import (
    ParsedIntentGraph,
    SemanticSegment,
    build_parser_context,
    heuristic_parse,
    SEGMENT_KINDS,
    REQUEST_MODES,
    _extract_first_json,
)
from app.runtime_v2.state import RuntimeV2State


class TestSemanticParserDataStructures:
    """测试数据结构"""

    def test_semantic_segment_creation(self):
        seg = SemanticSegment(
            text="测试文本",
            kind="task_request",
            confidence=0.9,
            request_mode="execute",
        )
        assert seg.text == "测试文本"
        assert seg.kind == "task_request"
        assert seg.confidence == 0.9
        assert seg.request_mode == "execute"

    def test_parsed_intent_graph_creation(self):
        graph = ParsedIntentGraph(
            segments=[
                SemanticSegment(text="任务", kind="task_request", confidence=0.9),
                SemanticSegment(text="约束", kind="constraint", confidence=0.8),
            ],
            primary_intent="task_request",
            has_status_query=False,
            has_correction=False,
        )
        assert len(graph.segments) == 2
        assert graph.primary_intent == "task_request"
        assert graph.has_status_query is False


class TestHeuristicParser:
    """测试 heuristic parser"""

    def test_explicit_command(self):
        graph = heuristic_parse("/status")
        assert graph.primary_intent == "task_request"
        assert graph.segments[0].kind == "task_request"
        assert graph.segments[0].request_mode == "execute"
        assert graph.parser_source == "heuristic_parser"

    def test_file_path(self):
        """路径 + 明确修改任务 → task_request。"""
        graph = heuristic_parse("/home/moonlight/test.html 配色改成蓝色")
        assert graph.primary_intent == "task_request"
        assert graph.requires_clarification is False
        assert graph.segments[0].request_mode == "write"
        assert graph.parser_source == "heuristic_parser"

    def test_file_path_only(self):
        """只有路径，无执行动词 → reference_material"""
        graph = heuristic_parse("/home/moonlight/test.html")
        assert graph.primary_intent == "reference_material"
        assert graph.requires_clarification is True

    def test_directory_page_creation_request(self):
        graph = heuristic_parse(r"你能帮我在D:\Project\AIProject\MyProject\Test里创建一个介绍egocore的页面吗")
        assert graph.primary_intent == "task_request"
        assert graph.segments[0].request_mode == "write"
        assert graph.segments[0].target_ref == r"D:\Project\AIProject\MyProject\Test"
        assert "format:html" in graph.constraints
        assert "topic:EgoCore" in graph.acceptance_criteria

    def test_explicit_file_read_request_uses_analyze_mode(self):
        graph = heuristic_parse(r"看看这个文件 D:\Project\AIProject\MyProject\Ego\PROJECT_MEMORY.md")
        assert graph.primary_intent == "task_request"
        assert graph.segments[0].request_mode == "analyze"
        assert graph.segments[0].target_ref == r"D:\Project\AIProject\MyProject\Ego\PROJECT_MEMORY.md"

    def test_attachment(self):
        graph = heuristic_parse("[用户发送了文件: test.html]")
        assert graph.primary_intent == "reference_material"
        assert graph.requires_clarification is True

    def test_chat_default(self):
        graph = heuristic_parse("你好")
        assert graph.primary_intent == "chat"
        assert graph.parser_source == "chat_default"

    def test_normal_chat(self):
        graph = heuristic_parse("你觉得怎么样")
        assert graph.primary_intent == "chat"
        assert graph.parser_source == "chat_default"


class TestSegmentKinds:
    """测试 segment kinds 枚举"""

    def test_all_valid_kinds(self):
        valid_kinds = {
            "task_request", "status_query", "constraint", "background",
            "clarification", "correction", "acceptance_criteria",
            "reference_material", "small_talk",
        }
        assert SEGMENT_KINDS == valid_kinds

    def test_all_valid_request_modes(self):
        valid_modes = {
            "execute", "analyze", "design", "compare",
            "write", "summarize", "unknown",
        }
        assert REQUEST_MODES == valid_modes


class TestRuntimeActionDecision:
    """测试 runtime action 决策"""

    def test_status_query_when_busy(self):
        from app.runtime_v2.semantic_parser import decide_runtime_action

        graph = ParsedIntentGraph(
            has_status_query=True,
            primary_intent="status_query",
        )

        # 模拟 busy state
        class MockState:
            def is_busy(self):
                return True

        action = decide_runtime_action(graph, MockState())
        assert action == "chat"

    def test_status_query_when_idle(self):
        """空闲态下不应把状态查询硬判成 runtime status 快路。"""
        from app.runtime_v2.semantic_parser import decide_runtime_action

        graph = ParsedIntentGraph(
            has_status_query=True,
            primary_intent="status_query",
        )

        # 模拟 idle state
        class MockState:
            def is_busy(self):
                return False

        action = decide_runtime_action(graph, MockState())
        assert action == "chat"

    def test_status_query_with_pending_result_continuation_uses_runtime_status(self):
        from app.runtime_v2.semantic_parser import decide_runtime_action

        graph = ParsedIntentGraph(
            has_status_query=True,
            primary_intent="status_query",
        )

        class MockState:
            pending_result_continuation = {"requested_mode": "write", "status": "pending"}

            def is_busy(self):
                return False

        action = decide_runtime_action(graph, MockState())
        assert action == "return_runtime_status"

    def test_correction_priority(self):
        from app.runtime_v2.semantic_parser import decide_runtime_action

        graph = ParsedIntentGraph(
            has_correction=True,
            primary_intent="task_request",
        )

        class MockState:
            def is_busy(self):
                return False

        action = decide_runtime_action(graph, MockState())
        assert action == "repair_or_reframe"

    def test_task_request_execution(self):
        from app.runtime_v2.semantic_parser import decide_runtime_action

        graph = ParsedIntentGraph(
            primary_intent="task_request",
            requires_clarification=False,
        )

        class MockState:
            def is_busy(self):
                return False

        action = decide_runtime_action(graph, MockState())
        assert action == "execute_task"

    def test_reference_material_needs_clarification(self):
        from app.runtime_v2.semantic_parser import decide_runtime_action

        graph = ParsedIntentGraph(
            primary_intent="reference_material",
            requires_clarification=True,
        )

        class MockState:
            def is_busy(self):
                return False

        action = decide_runtime_action(graph, MockState())
        assert action == "waiting_input"


class TestParserSourceFidelity:
    """
    测试 parser_source 保真性。

    核心要求：parser_source 必须真实反映实际命中的解析路径。
    - semantic_parser: 真正走 LLM 解析且成功返回有效结果
    - heuristic_parser: 因 timeout/error/empty 回退到 heuristic 且 heuristic 命中
    - chat_default: heuristic 也未命中，只能默认聊天
    """

    def test_heuristic_explicit_command_source(self):
        """显式命令 → heuristic_parser"""
        graph = heuristic_parse("/status")
        assert graph.parser_source == "heuristic_parser"

    def test_heuristic_path_source(self):
        """文件路径 → heuristic_parser"""
        graph = heuristic_parse("/home/user/test.py")
        assert graph.parser_source == "heuristic_parser"

    def test_heuristic_attachment_source(self):
        """附件标记 → heuristic_parser"""
        graph = heuristic_parse("[用户发送了文件: test.py]")
        assert graph.parser_source == "heuristic_parser"

    def test_chat_default_source(self):
        """无显式信号 → chat_default"""
        graph = heuristic_parse("你好")
        assert graph.parser_source == "chat_default"

    def test_chat_default_natural_language(self):
        """自然语言无显式信号 → chat_default（heuristic 不处理执行动词）"""
        graph = heuristic_parse("创建一个任务单")
        # heuristic 禁止处理执行动词，应 fallback 到 chat_default
        assert graph.parser_source == "chat_default"

    def test_chat_default_mixed_input(self):
        """混合输入无显式硬信号 → chat_default"""
        graph = heuristic_parse("帮我修改这个文件，生成一个报告")
        # 无显式路径/命令/附件，heuristic 不处理执行动词 → chat_default
        assert graph.parser_source == "chat_default"


class TestHeuristicResponsibility:
    """
    测试 heuristic 职责收窄：只处理显式硬信号，不处理自然语言执行动词。
    """

    def test_heuristic_does_not_handle_creation_verbs(self):
        """heuristic 不处理'创建'动词"""
        graph = heuristic_parse("创建一个配置文件")
        # 不应识别为 task_request
        assert graph.parser_source == "chat_default"

    def test_heuristic_does_not_handle_modification_verbs(self):
        """heuristic 不处理'修改/改'动词"""
        graph = heuristic_parse("修改这个配置")
        assert graph.parser_source == "chat_default"

    def test_heuristic_does_not_handle_execution_verbs(self):
        """heuristic 不处理'执行/运行/跑'动词"""
        graph = heuristic_parse("执行这个脚本")
        assert graph.parser_source == "chat_default"

        graph = heuristic_parse("运行程序")
        assert graph.parser_source == "chat_default"

        graph = heuristic_parse("跑一下测试")
        assert graph.parser_source == "chat_default"

    def test_heuristic_does_not_handle_write_verbs(self):
        """heuristic 不处理'写/生成'动词"""
        graph = heuristic_parse("写个函数")
        assert graph.parser_source == "chat_default"

        graph = heuristic_parse("生成报告")
        assert graph.parser_source == "chat_default"

    def test_heuristic_does_not_handle_fix_verbs(self):
        """heuristic 不处理'修复'动词"""
        graph = heuristic_parse("修复这个 bug")
        assert graph.parser_source == "chat_default"

    def test_heuristic_does_not_handle_delete_verbs(self):
        """heuristic 不处理'删除'动词"""
        graph = heuristic_parse("删除这个文件")
        assert graph.parser_source == "chat_default"

    def test_heuristic_only_handles_explicit_signals(self):
        """heuristic 只处理显式硬信号"""
        # 显式命令
        graph = heuristic_parse("/run")
        assert graph.parser_source == "heuristic_parser"

        # 显式路径
        graph = heuristic_parse("/tmp/test.txt")
        assert graph.parser_source == "heuristic_parser"

        # 附件标记
        graph = heuristic_parse("[附件: doc.pdf]")
        assert graph.parser_source == "heuristic_parser"


@pytest.mark.asyncio
class TestSemanticParserIntegration:
    """
    集成测试：验证 parser_source 在三条路径上的保真性。

    三条路径：
    1. semantic_parser: LLM 调用成功且返回有效结果
    2. heuristic_parser: LLM 失败/超时/空结果，且 heuristic 命中显式信号
    3. chat_default: LLM 失败/无结果，且 heuristic 也未命中
    """

    async def test_path_1_semantic_parser_success(self):
        """路径1：LLM 成功 → parser_source = semantic_parser"""
        from app.runtime_v2.semantic_parser import semantic_parse_message

        # Mock LLM client 返回有效结果
        class MockLLMClient:
            async def complete(self, prompt):
                class Response:
                    content = '{"segments": [{"text": "测试任务", "kind": "task_request", "confidence": 0.9, "request_mode": "execute"}]}'
                return Response()

        graph = await semantic_parse_message(
            text="测试任务",
            recent_turns=[],
            runtime_snapshot={},
            llm_client=MockLLMClient(),
        )

        assert graph.parser_source == "semantic_parser"
        assert graph.primary_intent == "task_request"

    async def test_path_2_heuristic_fallback_on_empty_result(self):
        """路径2：LLM 返回空结果 → 回退 heuristic → parser_source = heuristic_parser"""
        from app.runtime_v2.semantic_parser import semantic_parse_message

        # Mock LLM client 返回空结果
        class MockLLMClient:
            async def complete(self, prompt):
                class Response:
                    content = '{"segments": []}'
                return Response()

        graph = await semantic_parse_message(
            text="/home/user/test.py",  # 有显式路径，heuristic 会命中
            recent_turns=[],
            runtime_snapshot={},
            llm_client=MockLLMClient(),
        )

        # 因 empty result 回退，且 heuristic 命中路径 → heuristic_parser
        assert graph.parser_source == "heuristic_parser"
        assert graph.primary_intent == "reference_material"

    async def test_path_3_chat_default_on_no_signal(self):
        """路径3：LLM 失败 + heuristic 无命中 → parser_source = chat_default"""
        from app.runtime_v2.semantic_parser import semantic_parse_message

        # Mock LLM client 抛出异常
        class MockLLMClient:
            async def complete(self, prompt):
                raise Exception("LLM failed")

        graph = await semantic_parse_message(
            text="随便聊聊",  # 无显式信号
            recent_turns=[],
            runtime_snapshot={},
            llm_client=MockLLMClient(),
        )

        # LLM 失败，heuristic 也未命中 → chat_default
        assert graph.parser_source == "chat_default"
        assert graph.primary_intent == "chat"

    async def test_path_2b_heuristic_on_timeout(self):
        """路径2b：LLM 超时 → 回退 heuristic → parser_source = heuristic_parser"""
        from app.runtime_v2.semantic_parser import semantic_parse_message
        import asyncio

        # Mock LLM client 永远不解雇（模拟超时）
        class MockLLMClient:
            async def complete(self, prompt):
                await asyncio.sleep(100)  # 会触发超时
                return None

        graph = await semantic_parse_message(
            text="/status",  # 显式命令
            recent_turns=[],
            runtime_snapshot={},
            llm_client=MockLLMClient(),
            timeout=0.01,  # 极短超时
        )

        # 超时回退，heuristic 命中命令 → heuristic_parser
        assert graph.parser_source == "heuristic_parser"

    async def test_path_2c_heuristic_on_invalid_json(self):
        """路径2c：LLM 返回无效 JSON → 回退 heuristic → parser_source 绝不是 semantic_parser"""
        from app.runtime_v2.semantic_parser import semantic_parse_message

        # Mock LLM client 返回无效 JSON
        class MockLLMClient:
            async def complete(self, prompt):
                class Response:
                    content = 'this is not valid json at all'
                return Response()

        graph = await semantic_parse_message(
            text="/home/user/test.py",  # 有显式路径，heuristic 会命中
            recent_turns=[],
            runtime_snapshot={},
            llm_client=MockLLMClient(),
        )

        # 无效 JSON 回退，heuristic 命中路径 → heuristic_parser
        # 绝不能是 semantic_parser
        assert graph.parser_source == "heuristic_parser"
        assert graph.parser_source != "semantic_parser"
        assert graph.primary_intent == "reference_material"

    async def test_path_1b_semantic_parser_handles_ordinary_discussion(self):
        from app.runtime_v2.semantic_parser import semantic_parse_message

        class MockLLMClient:
            async def complete(self, prompt):
                class Response:
                    content = '{"segments": [{"text": "你觉得什么才是构建一个有自我意识的AI最核心的框架?", "kind": "small_talk", "confidence": 0.93}]}'
                return Response()

        graph = await semantic_parse_message(
            text="你觉得什么才是构建一个有自我意识的AI最核心的框架?",
            recent_turns=[],
            runtime_snapshot={"task_status": "idle"},
            llm_client=MockLLMClient(),
        )

        assert graph.parser_source == "semantic_parser"
        assert graph.primary_intent == "small_talk"


def test_build_parser_context_includes_recent_result_and_last_reply() -> None:
    state = RuntimeV2State(session_id="telegram:dm:1")
    state.get_chat_state().recent_user_turns = ["你好", "排版有些问题 你检查一下"]
    state.get_chat_state().recent_assistant_replies = ["你好。", "好的，你是指刚才那个页面排版吗？"]
    state.recent_delivered_result_context = {
        "target_name": "bilili_lookalike.html",
        "target_path": r"D:\Project\AIProject\MyProject\Test2\bilili_lookalike.html",
    }

    context = build_parser_context([], state)

    assert context["runtime_snapshot"]["recent_delivered_result_context"]["target_name"] == "bilili_lookalike.html"
    assert context["runtime_snapshot"]["last_assistant_reply"] == "好的，你是指刚才那个页面排版吗？"
    assert len(context["recent_turns_summary"]) >= 2


class TestDesignContractSamples:
    """
    测试设计合同中的验收样例（heuristic 版本）。

    注：完整测试需要 LLM，这里只测试 heuristic 行为。
    """

    def test_sample_1_discussion(self):
        """样例1：讨论性句式"""
        graph = heuristic_parse("你觉得要怎么实现比较好？")
        # heuristic 不识别自然语言，默认 chat
        assert graph.primary_intent == "chat"

    def test_sample_2_status_query(self):
        """样例2：自然语言进度词不再进入 control-plane，默认按聊天处理。"""
        graph = heuristic_parse("好了吗")
        assert graph.primary_intent == "chat"

    def test_sample_3_task_with_path(self):
        """样例3：路径 + 明确修改任务 → task_request。"""
        graph = heuristic_parse("把 /home/x.html 改成蓝色")
        assert graph.primary_intent == "task_request"
        assert graph.requires_clarification is False
        assert graph.segments[0].request_mode == "write"
        assert graph.parser_source == "heuristic_parser"

    def test_sample_8_attachment(self):
        """样例8：附件"""
        graph = heuristic_parse("文件发你了，先看看要不要按任务单执行")
        # 无显式信号，默认 chat
        assert graph.primary_intent == "chat"


class TestJsonExtraction:
    """测试 JSON 提取功能（处理 LLM 返回 JSON 后带额外内容的情况）"""

    def test_extract_first_json_basic(self):
        """测试基础 JSON 提取"""

        text = '{"segments": [{"text": "hello", "kind": "task_request"}]}'
        result = _extract_first_json(text)
        assert result == text

    def test_extract_first_json_with_trailing_content(self):
        """测试 JSON 后带额外 markdown 内容"""

        text = '{"segments": [{"text": "hello", "kind": "task_request"}]}\n\n| 字段 | 说明 |\n|------|------|\n'
        result = _extract_first_json(text)
        assert result == '{"segments": [{"text": "hello", "kind": "task_request"}]}'

    def test_extract_first_json_with_nested_objects(self):
        """测试嵌套对象提取"""

        text = '{"outer": {"inner": {"deep": "value"}}, "list": [1, 2, 3]} trailing text'
        result = _extract_first_json(text)
        assert result == '{"outer": {"inner": {"deep": "value"}}, "list": [1, 2, 3]}'

    def test_extract_first_json_with_string_containing_braces(self):
        """测试字符串中包含花括号的情况"""

        text = '{"text": "contains { and } in string", "kind": "task_request"} extra'
        result = _extract_first_json(text)
        assert result == '{"text": "contains { and } in string", "kind": "task_request"}'

    def test_extract_first_json_with_escaped_quotes(self):
        """测试转义引号的情况"""

        text = '{"text": "say \\"hello\\"", "kind": "task_request"} more text'
        result = _extract_first_json(text)
        assert result == '{"text": "say \\"hello\\"", "kind": "task_request"}'

    def test_extract_first_json_with_whitespace_prefix(self):
        """测试带有前导空白的情况"""

        text = '   \n  {"segments": []} trailing text'
        result = _extract_first_json(text)
        assert result == '{"segments": []}'

    def test_extract_first_json_empty_string(self):
        """测试空字符串"""

        text = ''
        result = _extract_first_json(text)
        assert result == ''

    def test_extract_first_json_no_json_object(self):
        """测试没有 JSON 对象的情况"""

        text = 'just plain text without json'
        result = _extract_first_json(text)
        assert result == text  # 返回原字符串，让后续解析报错
