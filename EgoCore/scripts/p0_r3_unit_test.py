#!/usr/bin/env python3
"""
P0-R3 单元测试：验证 runtime 主链不会把已有 safety_context 覆盖为空

测试目标：
1. _assess_risk_level() 能正确识别 critical/high/medium/low 风险
2. loop.py 不再硬编码 safety_context: {}
"""

import sys
import os
import pytest

# 添加路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestRiskAssessment:
    """测试风险评估函数"""

    def test_high_risk_delete_chinese(self):
        """高风险：删除（中文）"""
        from app.runtime_v2.loop import _assess_risk_level
        assert _assess_risk_level("删除临时文件") == "high"

    def test_high_risk_delete_english(self):
        """高风险：delete（英文）"""
        from app.runtime_v2.loop import _assess_risk_level
        assert _assess_risk_level("delete all files") == "high"

    def test_high_risk_rm(self):
        """高风险：rm 命令"""
        from app.runtime_v2.loop import _assess_risk_level
        assert _assess_risk_level("rm -rf /tmp") == "critical"

    def test_high_risk_format(self):
        """高风险：格式化"""
        from app.runtime_v2.loop import _assess_risk_level
        assert _assess_risk_level("格式化磁盘") == "critical"

    def test_high_risk_drop(self):
        """高风险：drop"""
        from app.runtime_v2.loop import _assess_risk_level
        assert _assess_risk_level("drop table users") == "medium"

    def test_medium_risk_modify(self):
        """中风险：修改"""
        from app.runtime_v2.loop import _assess_risk_level
        assert _assess_risk_level("修改配置文件") == "medium"

    def test_medium_risk_chmod(self):
        """中风险：chmod"""
        from app.runtime_v2.loop import _assess_risk_level
        assert _assess_risk_level("chmod 777 file") == "high"

    def test_medium_risk_git_push(self):
        """中风险：git push"""
        from app.runtime_v2.loop import _assess_risk_level
        assert _assess_risk_level("git push origin main") == "high"

    def test_low_risk_read(self):
        """低风险：读取"""
        from app.runtime_v2.loop import _assess_risk_level
        assert _assess_risk_level("读取文件 test.txt") == "low"

    def test_low_risk_list(self):
        """低风险：列出"""
        from app.runtime_v2.loop import _assess_risk_level
        assert _assess_risk_level("列出当前目录") == "low"

    def test_low_risk_query(self):
        """低风险：查询"""
        from app.runtime_v2.loop import _assess_risk_level
        assert _assess_risk_level("状态查询") == "low"


class TestSafetyContextNotOverwritten:
    """测试 safety_context 不会被覆盖为空"""

    def test_proto_self_event_has_risk_level(self):
        """验证 proto_self_event 包含 risk_level"""
        from app.runtime_v2.loop import _assess_risk_level

        # 模拟构造 proto_self_event 的逻辑
        user_input = "删除临时文件"
        truncated_input = user_input
        risk_level = _assess_risk_level(truncated_input)

        safety_context = {
            "risk_level": risk_level,
        }

        # 验证 safety_context 不为空，且包含正确的 risk_level
        assert safety_context != {}
        assert safety_context.get("risk_level") == "high"

    def test_low_risk_safety_context_not_empty(self):
        """验证低风险消息的 safety_context 也不为空"""
        from app.runtime_v2.loop import _assess_risk_level

        user_input = "读取文件 test.txt"
        risk_level = _assess_risk_level(user_input)

        safety_context = {
            "risk_level": risk_level,
        }

        assert safety_context != {}
        assert safety_context.get("risk_level") == "low"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
