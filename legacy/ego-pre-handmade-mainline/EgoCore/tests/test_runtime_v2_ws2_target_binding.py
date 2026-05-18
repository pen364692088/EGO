"""
WS-2: Pending Bundle / 目标绑定真相源测试

验证：
1. resolve_target() 按动作类型分流绑定
2. 执行优先绑定 task 类 artifact
3. 对比优先绑定 bundle
4. 硬规则：不回退到 SOUL/AGENTS/TOOLS
"""

import pytest
from app.runtime_v2.state import RuntimeV2State


class TestArtifactTypeClassification:
    """测试文件类型推断"""
    
    def test_classify_task_artifact(self):
        """验证 task 类文件推断"""
        state = RuntimeV2State(session_id="test")
        
        # 任务单类文件名
        assert state._classify_artifact_type("测试任务单.txt") == "task"
        assert state._classify_artifact_type("todo.md") == "task"
        assert state._classify_artifact_type("task_plan.txt") == "task"
        assert state._classify_artifact_type("fix_bug.txt") == "task"
    
    def test_classify_spec_artifact(self):
        """验证 spec 类文件推断"""
        state = RuntimeV2State(session_id="test")
        
        # 规范类文件名
        assert state._classify_artifact_type("SOUL.md") == "spec"
        assert state._classify_artifact_type("AGENTS.md") == "spec"
        assert state._classify_artifact_type("TOOLS.md") == "spec"
        assert state._classify_artifact_type("README.md") == "spec"
    
    def test_classify_unknown_artifact(self):
        """验证未知类型"""
        state = RuntimeV2State(session_id="test")
        
        assert state._classify_artifact_type("data.json") == "unknown"
        assert state._classify_artifact_type("image.png") == "unknown"


class TestResolveTargetForExecute:
    """测试 execute 动作的目标绑定"""
    
    def test_prioritize_task_artifact_over_spec(self):
        """
        WS-2 核心用例：SOUL.md + 测试任务单.txt + 执行
        
        预期：绑定到 测试任务单.txt
        """
        state = RuntimeV2State(session_id="test")
        
        # 先上传 SOUL.md
        state.add_pending_artifact("artifact_1", "SOUL.md", "ref_1")
        
        # 再上传 测试任务单.txt
        state.add_pending_artifact("artifact_2", "测试任务单.txt", "ref_2")
        
        # 执行动作应该绑定到 task 类文件
        target = state.resolve_target("execute")
        
        assert target is not None
        assert target.get("filename") == "测试任务单.txt"
        assert target.get("source") in ("latest_task_artifact", "last_uploaded_task")
    
    def test_last_explicit_target_highest_priority(self):
        """验证 last_explicit_target 最高优先级"""
        state = RuntimeV2State(session_id="test")
        
        # 上传多个文件
        state.add_pending_artifact("artifact_1", "SOUL.md", "ref_1")
        state.add_pending_artifact("artifact_2", "测试任务单.txt", "ref_2")
        
        # 设置 last_explicit_target
        state.last_explicit_target = "AGENTS.md"
        
        # 应该绑定到 last_explicit_target
        target = state.resolve_target("execute")
        assert target.get("filename") == "AGENTS.md"
    
    def test_no_fallback_to_spec(self):
        """
        硬规则：只有 spec 类文件时，execute 不应该回退到 SOUL/AGENTS/TOOLS
        """
        state = RuntimeV2State(session_id="test")
        
        # 只上传规范文件
        state.add_pending_artifact("artifact_1", "SOUL.md", "ref_1")
        state.add_pending_artifact("artifact_2", "AGENTS.md", "ref_2")
        
        # 执行动作应该返回 None 或 current_goal，不应该绑定到 spec 文件
        target = state.resolve_target("execute")
        
        if target:
            # 如果返回了 target，不应该是 spec 文件
            filename = target.get("filename")
            if filename:
                assert state._classify_artifact_type(filename) != "spec"


class TestResolveTargetForCompare:
    """测试 compare 动作的目标绑定"""
    
    def test_bind_to_bundle(self):
        """
        WS-2 核心用例：多文件 + 对比一下
        
        预期：绑定到整个 bundle
        """
        state = RuntimeV2State(session_id="test")
        
        # 上传多个规范文件
        state.add_pending_artifact("artifact_1", "SOUL.md", "ref_1")
        state.add_pending_artifact("artifact_2", "TOOLS.md", "ref_2")
        state.add_pending_artifact("artifact_3", "AGENTS.md", "ref_3")
        
        # 对比动作应该绑定到 bundle
        target = state.resolve_target("compare")
        
        assert target is not None
        assert target.get("source") == "pending_bundle"
        assert target.get("count") == 3
        assert "bundle" in target
    
    def test_compare_two_spec_files(self):
        """对比两个 spec 文件"""
        state = RuntimeV2State(session_id="test")
        
        state.add_pending_artifact("artifact_1", "SOUL.md", "ref_1")
        state.add_pending_artifact("artifact_2", "AGENTS.md", "ref_2")
        
        target = state.resolve_target("compare")
        
        assert target is not None
        assert target.get("count") == 2


class TestResolveTargetForAnalyze:
    """测试 analyze 动作的目标绑定"""
    
    def test_bind_to_last_uploaded(self):
        """分析动作优先绑定 last_uploaded_artifact"""
        state = RuntimeV2State(session_id="test")
        
        state.add_pending_artifact("artifact_1", "SOUL.md", "ref_1")
        state.add_pending_artifact("artifact_2", "test.py", "ref_2")
        
        target = state.resolve_target("analyze")
        
        assert target is not None
        assert target.get("filename") == "test.py"
        assert target.get("source") == "last_uploaded"


class TestPendingArtifactsMaintenance:
    """测试 pending_artifacts 维护"""
    
    def test_add_pending_artifact_updates_last_uploaded(self):
        """验证 add_pending_artifact 更新 last_uploaded_artifact"""
        state = RuntimeV2State(session_id="test")
        
        state.add_pending_artifact("artifact_1", "file1.txt", "ref_1")
        assert state.last_uploaded_artifact.get("filename") == "file1.txt"
        
        state.add_pending_artifact("artifact_2", "file2.txt", "ref_2")
        assert state.last_uploaded_artifact.get("filename") == "file2.txt"
    
    def test_pending_bundle_summary_updated(self):
        """验证 pending_bundle_summary 正确更新"""
        state = RuntimeV2State(session_id="test")
        
        state.add_pending_artifact("artifact_1", "file1.txt", "ref_1")
        state.add_pending_artifact("artifact_2", "file2.txt", "ref_2")
        
        assert state.pending_bundle_summary is not None
        assert state.pending_bundle_summary.get("count") == 2
        assert len(state.pending_bundle_summary.get("files", [])) == 2
    
    def test_get_task_artifacts(self):
        """验证 get_task_artifacts 只返回 task 类文件"""
        state = RuntimeV2State(session_id="test")
        
        state.add_pending_artifact("artifact_1", "SOUL.md", "ref_1")
        state.add_pending_artifact("artifact_2", "测试任务单.txt", "ref_2")
        state.add_pending_artifact("artifact_3", "AGENTS.md", "ref_3")
        
        task_artifacts = state.get_task_artifacts()
        
        assert len(task_artifacts) == 1
        assert task_artifacts[0].get("filename") == "测试任务单.txt"
    
    def test_get_spec_artifacts(self):
        """验证 get_spec_artifacts 只返回 spec 类文件"""
        state = RuntimeV2State(session_id="test")
        
        state.add_pending_artifact("artifact_1", "SOUL.md", "ref_1")
        state.add_pending_artifact("artifact_2", "测试任务单.txt", "ref_2")
        state.add_pending_artifact("artifact_3", "AGENTS.md", "ref_3")
        
        spec_artifacts = state.get_spec_artifacts()
        
        assert len(spec_artifacts) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
