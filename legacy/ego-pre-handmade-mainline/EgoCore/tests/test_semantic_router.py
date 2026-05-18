"""
Tests for Semantic Intent Router - P1 Task 1
"""

import pytest
from app.runtime.semantic_router import (
    SemanticRouter,
    SemanticIntent,
    IntentResult,
    classify_message,
    get_semantic_router
)


class TestSemanticRouter:
    """Test semantic intent classification."""
    
    @pytest.fixture
    def router(self):
        return SemanticRouter()
    
    # ===== CHAT Tests =====
    
    def test_chat_greeting_chinese(self, router):
        """Test Chinese greeting classification."""
        result = router.classify("你好")
        assert result.intent == SemanticIntent.CHAT
        assert result.confidence >= 0.8
    
    def test_chat_greeting_english(self, router):
        """Test English greeting classification."""
        result = router.classify("hello")
        assert result.intent == SemanticIntent.CHAT
    
    def test_chat_are_you_there(self, router):
        """Test presence check classification."""
        result = router.classify("在吗")
        assert result.intent == SemanticIntent.CHAT
    
    def test_chat_ok(self, router):
        """Test acknowledgment classification."""
        result = router.classify("好的")
        assert result.intent == SemanticIntent.CHAT
    
    # ===== QUESTION Tests =====
    
    def test_question_why(self, router):
        """Test why question classification."""
        result = router.classify("为什么会误建任务？")
        assert result.intent == SemanticIntent.QUESTION
    
    def test_question_what(self, router):
        """Test what question classification."""
        result = router.classify("这是什么意思？")
        assert result.intent == SemanticIntent.QUESTION
    
    def test_question_how(self, router):
        """Test how question classification."""
        result = router.classify("如何使用这个功能？")
        assert result.intent == SemanticIntent.QUESTION
    
    def test_question_ends_with_mark(self, router):
        """Test question mark classification."""
        result = router.classify("这个对吗？")
        assert result.intent == SemanticIntent.QUESTION
    
    # ===== NEW_TASK Tests =====
    
    def test_new_task_help_me(self, router):
        """Test 'help me' pattern classification."""
        result = router.classify("帮我检查这个仓库的核心问题")
        assert result.intent == SemanticIntent.NEW_TASK
        assert result.extracted_content is not None
    
    def test_new_task_read(self, router):
        """Test 'read' pattern classification."""
        result = router.classify("读取 README 并总结")
        assert result.intent == SemanticIntent.NEW_TASK
    
    def test_new_task_analyze(self, router):
        """Test 'analyze' pattern classification."""
        result = router.classify("分析一下代码结构")
        assert result.intent == SemanticIntent.NEW_TASK
    
    def test_new_task_create(self, router):
        """Test 'create' pattern classification."""
        result = router.classify("创建一个任务单")
        assert result.intent == SemanticIntent.NEW_TASK
    
    # ===== CONTINUE_TASK Tests =====
    
    def test_continue_simple(self, router):
        """Test simple continue classification."""
        result = router.classify("继续")
        assert result.intent == SemanticIntent.CONTINUE_TASK
    
    def test_continue_go_on(self, router):
        """Test 'go on' pattern classification."""
        result = router.classify("接着做")
        assert result.intent == SemanticIntent.CONTINUE_TASK
    
    def test_continue_what_else(self, router):
        """Test 'what else' pattern classification."""
        result = router.classify("还有呢")
        assert result.intent == SemanticIntent.CONTINUE_TASK
    
    def test_continue_previous_task(self, router):
        """Test 'previous task' pattern classification."""
        result = router.classify("上个任务怎么样了")
        assert result.intent == SemanticIntent.CONTINUE_TASK
    
    def test_continue_resume(self, router):
        """Test 'resume' pattern classification."""
        result = router.classify("恢复任务")
        assert result.intent == SemanticIntent.CONTINUE_TASK
    
    # ===== COMMAND Tests =====
    
    def test_command_new(self, router):
        """Test /new command classification."""
        result = router.classify("/new")
        assert result.intent == SemanticIntent.COMMAND
        assert result.confidence == 1.0
    
    def test_command_run(self, router):
        """Test /run command classification."""
        result = router.classify("/run")
        assert result.intent == SemanticIntent.COMMAND
    
    def test_command_with_args(self, router):
        """Test command with arguments."""
        result = router.classify("/new 帮我分析代码")
        assert result.intent == SemanticIntent.COMMAND
        assert result.extracted_content == "/new"
    
    # ===== HIGH RISK Tests =====
    
    def test_high_risk_delete(self, router):
        """Test delete detection."""
        assert router.is_high_risk("帮我删除这个目录") is True
    
    def test_high_risk_push(self, router):
        """Test push detection."""
        assert router.is_high_risk("推送到远程仓库") is True
    
    def test_high_risk_restart(self, router):
        """Test restart detection."""
        assert router.is_high_risk("重启服务") is True
    
    def test_safe_operation(self, router):
        """Test safe operation detection."""
        assert router.is_high_risk("读取 README 文件") is False
    
    # ===== Task Content Extraction =====
    
    def test_extract_task_content(self, router):
        """Test task content extraction."""
        content = router.extract_task_content("帮我检查项目问题")
        assert "帮我" not in content
        assert "检查" in content
    
    # ===== Convenience Function =====
    
    def test_classify_message_function(self):
        """Test global classify_message function."""
        result = classify_message("你好")
        assert result.intent == SemanticIntent.CHAT
    
    def test_get_semantic_router_singleton(self):
        """Test router singleton."""
        router1 = get_semantic_router()
        router2 = get_semantic_router()
        assert router1 is router2


class TestIntentPriorities:
    """Test that intent classification priorities are correct."""
    
    @pytest.fixture
    def router(self):
        return SemanticRouter()
    
    def test_command_has_highest_priority(self, router):
        """Command should always have highest priority."""
        result = router.classify("/run")
        assert result.intent == SemanticIntent.COMMAND
    
    def test_chat_over_question(self, router):
        """Short greetings should be chat, not question."""
        result = router.classify("你好？")
        # This is chat because it matches chat pattern
        assert result.intent == SemanticIntent.CHAT
    
    def test_continue_vs_new_task(self, router):
        """Continue patterns should not create new tasks."""
        result = router.classify("继续上一个任务")
        assert result.intent == SemanticIntent.CONTINUE_TASK


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    @pytest.fixture
    def router(self):
        return SemanticRouter()
    
    def test_empty_message(self, router):
        """Empty message should still classify."""
        result = router.classify("")
        assert result.intent in [SemanticIntent.CHAT, SemanticIntent.NEW_TASK]
    
    def test_short_message_defaults_to_chat(self, router):
        """Very short messages default to chat."""
        result = router.classify("hi")
        assert result.intent == SemanticIntent.CHAT
    
    def test_long_ambiguous_message(self, router):
        """Long ambiguous messages default to new_task."""
        result = router.classify("这是一段很长的消息但没有明确的意图模式")
        assert result.intent == SemanticIntent.NEW_TASK
    
    def test_mixed_language(self, router):
        """Mixed language should still classify."""
        result = router.classify("help me 分析这个 code")
        assert result.intent == SemanticIntent.NEW_TASK
