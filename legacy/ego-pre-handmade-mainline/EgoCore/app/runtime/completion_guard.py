"""
CompletionGuard - 完成守卫

职责:
- 验证任务是否真正完成
- 文件/命令/git/测试类任务，必须有真实工具回执
- 没有 post_verify 不得宣称 completed

版本: v1.0.0
Created: 2026-03-19
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
import os
import logging

logger = logging.getLogger(__name__)


class CompletionStatus(Enum):
    """完成状态"""
    COMPLETED = "completed"
    INCOMPLETE = "incomplete"
    FAILED = "failed"
    UNVERIFIED = "unverified"


@dataclass
class VerificationResult:
    """验证结果"""
    status: CompletionStatus
    verified: bool
    evidence: List[str]
    missing: List[str]
    reason: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "verified": self.verified,
            "evidence": self.evidence,
            "missing": self.missing,
            "reason": self.reason,
        }


class CompletionGuard:
    """
    完成守卫
    
    强制规则:
    - 文件类任务必须有真实文件存在
    - 命令类任务必须有真实执行输出
    - git 类任务必须有真实提交/推送记录
    - 测试类任务必须有真实测试结果
    """
    
    # 任务类型关键词
    FILE_KEYWORDS = ["创建", "写入", "保存", "create", "write", "save", "file"]
    COMMAND_KEYWORDS = ["运行", "执行", "run", "execute", "command", "shell"]
    GIT_KEYWORDS = ["git", "commit", "push", "pull", "merge", "rebase"]
    TEST_KEYWORDS = ["测试", "test", "pytest", "unittest", "jest"]
    
    def __init__(self):
        self._verification_rules = {
            "file": self._verify_file_operation,
            "command": self._verify_command_operation,
            "git": self._verify_git_operation,
            "test": self._verify_test_operation,
        }
    
    def verify(
        self,
        task_type: str,
        task_goal: str,
        execution_result: Optional[Dict[str, Any]] = None,
        target_path: Optional[str] = None,
        expected_content: Optional[str] = None,
    ) -> VerificationResult:
        """
        验证任务完成状态
        
        Args:
            task_type: 任务类型 (file/command/git/test/general)
            task_goal: 任务目标
            execution_result: 执行结果
            target_path: 目标路径
            expected_content: 期望内容
        
        Returns:
            VerificationResult
        """
        evidence = []
        missing = []
        
        # 1. 检查执行结果存在性
        if not execution_result:
            return VerificationResult(
                status=CompletionStatus.UNVERIFIED,
                verified=False,
                evidence=[],
                missing=["execution_result"],
                reason="没有执行结果，无法验证完成",
            )
        
        # 2. 检查是否有工具回执
        tool_result = execution_result.get("tool_result")
        if not tool_result and task_type != "general":
            missing.append("tool_result")
        
        # 3. 根据任务类型验证
        if task_type in self._verification_rules:
            result = self._verification_rules[task_type](
                task_goal=task_goal,
                execution_result=execution_result,
                target_path=target_path,
                expected_content=expected_content,
            )
            evidence.extend(result.get("evidence", []))
            missing.extend(result.get("missing", []))
        
        # 4. 综合判断
        if missing:
            status = CompletionStatus.INCOMPLETE if evidence else CompletionStatus.UNVERIFIED
            verified = False
        else:
            status = CompletionStatus.COMPLETED
            verified = True
        
        return VerificationResult(
            status=status,
            verified=verified,
            evidence=evidence,
            missing=missing,
        )
    
    def _verify_file_operation(
        self,
        task_goal: str,
        execution_result: Dict[str, Any],
        target_path: Optional[str],
        expected_content: Optional[str],
    ) -> Dict[str, Any]:
        """验证文件操作"""
        evidence = []
        missing = []
        
        # 提取目标路径
        path = target_path or self._extract_path(task_goal, execution_result)
        
        if not path:
            missing.append("target_path")
            return {"evidence": evidence, "missing": missing}
        
        # 检查文件是否存在
        if os.path.exists(path):
            evidence.append(f"文件存在: {path}")
            
            # 检查文件内容
            if expected_content:
                try:
                    with open(path, 'r') as f:
                        content = f.read()
                    if expected_content in content:
                        evidence.append("文件内容验证通过")
                    else:
                        missing.append("文件内容不匹配")
                except Exception as e:
                    missing.append(f"读取文件失败: {e}")
            
            # 检查是否是创建操作
            if "创建" in task_goal or "create" in task_goal.lower():
                evidence.append("文件创建成功")
        else:
            missing.append(f"文件不存在: {path}")
        
        return {"evidence": evidence, "missing": missing}
    
    def _verify_command_operation(
        self,
        task_goal: str,
        execution_result: Dict[str, Any],
        target_path: Optional[str],
        expected_content: Optional[str],
    ) -> Dict[str, Any]:
        """验证命令操作"""
        evidence = []
        missing = []
        
        tool_result = execution_result.get("tool_result", {})
        
        # 检查是否有执行输出
        output = tool_result.get("output") or execution_result.get("output")
        if output:
            evidence.append("有命令执行输出")
        else:
            missing.append("没有命令执行输出")
        
        # 检查执行状态
        success = tool_result.get("success", execution_result.get("success"))
        if success:
            evidence.append("命令执行成功")
        else:
            error = tool_result.get("error") or execution_result.get("error")
            if error:
                missing.append(f"命令执行失败: {error}")
        
        # 检查是否有真实调用记录
        if execution_result.get("tool_used"):
            evidence.append(f"使用了工具: {execution_result.get('tool_used')}")
        
        return {"evidence": evidence, "missing": missing}
    
    def _verify_git_operation(
        self,
        task_goal: str,
        execution_result: Dict[str, Any],
        target_path: Optional[str],
        expected_content: Optional[str],
    ) -> Dict[str, Any]:
        """验证 git 操作"""
        evidence = []
        missing = []
        
        # 检查是否有 git 命令执行
        output = execution_result.get("output", "")
        tool_result = execution_result.get("tool_result", {})
        
        if tool_result.get("success"):
            evidence.append("git 命令执行成功")
        
        # 检查输出中是否有 git 相关信息
        git_indicators = ["commit", "push", "pull", "merge", "changed", "insertion", "deletion"]
        for indicator in git_indicators:
            if indicator in output.lower():
                evidence.append(f"检测到 git 指示: {indicator}")
        
        # 如果是 push 操作，检查是否有远程响应
        if "push" in task_goal.lower():
            if "remote" in output.lower() or "->" in output:
                evidence.append("远程推送确认")
            else:
                missing.append("没有远程推送确认")
        
        return {"evidence": evidence, "missing": missing}
    
    def _verify_test_operation(
        self,
        task_goal: str,
        execution_result: Dict[str, Any],
        target_path: Optional[str],
        expected_content: Optional[str],
    ) -> Dict[str, Any]:
        """验证测试操作"""
        evidence = []
        missing = []
        
        output = execution_result.get("output", "")
        tool_result = execution_result.get("tool_result", {})
        
        # 检查测试结果
        if "passed" in output.lower() or "✓" in output:
            evidence.append("测试通过")
        elif "failed" in output.lower() or "✗" in output:
            missing.append("测试失败")
        else:
            missing.append("没有明确的测试结果")
        
        # 检查测试覆盖率
        if "coverage" in output.lower():
            evidence.append("有覆盖率报告")
        
        return {"evidence": evidence, "missing": missing}
    
    def _extract_path(
        self,
        task_goal: str,
        execution_result: Dict[str, Any],
    ) -> Optional[str]:
        """从任务目标或执行结果中提取路径"""
        import re
        
        # 从执行结果提取
        tool_args = execution_result.get("tool_result", {}).get("args", {})
        if isinstance(tool_args, dict):
            path = tool_args.get("path") or tool_args.get("file")
            if path:
                return path
        
        # 从任务目标提取
        patterns = [
            r'["\']([/\w\-\.]+)["\']',
            r'在\s+([/\w\-\.]+)',
            r'(?:create|write|read)\s+([/\w\-\.]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, task_goal)
            if match:
                return match.group(1)
        
        return None
    
    def classify_task_type(self, task_goal: str) -> str:
        """分类任务类型"""
        goal_lower = task_goal.lower()
        
        for keyword in self.FILE_KEYWORDS:
            if keyword in goal_lower:
                return "file"
        
        for keyword in self.GIT_KEYWORDS:
            if keyword in goal_lower:
                return "git"
        
        for keyword in self.TEST_KEYWORDS:
            if keyword in goal_lower:
                return "test"
        
        for keyword in self.COMMAND_KEYWORDS:
            if keyword in goal_lower:
                return "command"
        
        return "general"


# 全局实例
_guard: Optional[CompletionGuard] = None


def get_completion_guard() -> CompletionGuard:
    """获取全局完成守卫"""
    global _guard
    if _guard is None:
        _guard = CompletionGuard()
    return _guard


def verify_completion(
    task_type: str,
    task_goal: str,
    execution_result: Optional[Dict[str, Any]] = None,
    target_path: Optional[str] = None,
    expected_content: Optional[str] = None,
) -> VerificationResult:
    """
    便捷函数：验证任务完成
    
    Args:
        task_type: 任务类型
        task_goal: 任务目标
        execution_result: 执行结果
        target_path: 目标路径
        expected_content: 期望内容
    
    Returns:
        VerificationResult
    """
    return get_completion_guard().verify(
        task_type=task_type,
        task_goal=task_goal,
        execution_result=execution_result,
        target_path=target_path,
        expected_content=expected_content,
    )
