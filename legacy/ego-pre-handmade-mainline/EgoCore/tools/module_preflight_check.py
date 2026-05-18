#!/usr/bin/env python3
"""
Module Preflight Check Tool
检查模块是否具备接入主链的基本条件

Usage:
    python module_preflight_check.py --module <module_name> [--path <module_path>]
    python module_preflight_check.py --validate-contract <contract_path>
"""

import argparse
import os
import sys
import yaml
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class CheckStatus(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    SKIP = "SKIP"


@dataclass
class CheckResult:
    name: str
    status: CheckStatus
    message: str
    details: List[str] = field(default_factory=list)


class ModulePreflightChecker:
    """模块预检工具"""
    
    REQUIRED_CONTRACT_FIELDS = [
        "metadata.name",
        "metadata.version",
        "responsibility.description",
        "input.schema",
        "output.schema",
        "error.schema",
        "fallback.behavior",
        "timeout.default_ms",
    ]
    
    def __init__(self, module_path: str):
        self.module_path = Path(module_path)
        self.results: List[CheckResult] = []
        self.contract_data: Optional[Dict] = None
    
    def run_all_checks(self) -> Tuple[bool, List[CheckResult]]:
        """运行所有检查"""
        checks = [
            self.check_contract_exists,
            self.check_contract_valid,
            self.check_core_exists,
            self.check_adapter_exists,
            self.check_tests_exist,
            self.check_fallback_defined,
            self.check_metrics_placeholder,
            self.check_integration_point,
        ]
        
        for check in checks:
            try:
                check()
            except Exception as e:
                self.results.append(CheckResult(
                    name=check.__name__,
                    status=CheckStatus.FAIL,
                    message=f"检查执行异常: {e}",
                ))
        
        all_pass = all(r.status in (CheckStatus.PASS, CheckStatus.SKIP) for r in self.results)
        return all_pass, self.results
    
    def check_contract_exists(self) -> None:
        """检查 contract 文件是否存在"""
        contract_files = list(self.module_path.glob("*contract*.yaml")) + \
                        list(self.module_path.glob("*contract*.yml"))
        
        if contract_files:
            self.results.append(CheckResult(
                name="Contract 文件存在",
                status=CheckStatus.PASS,
                message=f"找到 contract 文件: {contract_files[0].name}",
            ))
            # 加载 contract 数据
            try:
                with open(contract_files[0], 'r', encoding='utf-8') as f:
                    self.contract_data = yaml.safe_load(f)
            except Exception as e:
                self.results.append(CheckResult(
                    name="Contract 加载",
                    status=CheckStatus.FAIL,
                    message=f"无法加载 contract: {e}",
                ))
        else:
            self.results.append(CheckResult(
                name="Contract 文件存在",
                status=CheckStatus.FAIL,
                message="未找到 contract 文件 (应包含 'contract' 且为 yaml/yml 格式)",
            ))
    
    def check_contract_valid(self) -> None:
        """检查 contract 内容有效性"""
        if not self.contract_data:
            self.results.append(CheckResult(
                name="Contract 内容有效",
                status=CheckStatus.SKIP,
                message="Contract 未加载，跳过",
            ))
            return
        
        missing_fields = []
        for field_path in self.REQUIRED_CONTRACT_FIELDS:
            if not self._get_nested_value(self.contract_data, field_path):
                missing_fields.append(field_path)
        
        if missing_fields:
            self.results.append(CheckResult(
                name="Contract 内容有效",
                status=CheckStatus.FAIL,
                message=f"缺少必填字段: {', '.join(missing_fields)}",
            ))
        else:
            self.results.append(CheckResult(
                name="Contract 内容有效",
                status=CheckStatus.PASS,
                message="所有必填字段已定义",
            ))
    
    def check_core_exists(self) -> None:
        """检查 core 模块是否存在"""
        core_patterns = ["core.py", "*/core.py", "core/*.py"]
        found = self._find_any_pattern(core_patterns)
        
        if found:
            self.results.append(CheckResult(
                name="Core 模块存在",
                status=CheckStatus.PASS,
                message=f"找到 core 模块",
            ))
        else:
            self.results.append(CheckResult(
                name="Core 模块存在",
                status=CheckStatus.FAIL,
                message="未找到 core 模块 (应包含 core.py 或 core/ 目录)",
            ))
    
    def check_adapter_exists(self) -> None:
        """检查 adapter 模块是否存在"""
        adapter_patterns = ["adapter.py", "*/adapter.py", "adapter/*.py"]
        found = self._find_any_pattern(adapter_patterns)
        
        if found:
            self.results.append(CheckResult(
                name="Adapter 模块存在",
                status=CheckStatus.PASS,
                message=f"找到 adapter 模块",
            ))
        else:
            self.results.append(CheckResult(
                name="Adapter 模块存在",
                status=CheckStatus.WARN,
                message="未找到 adapter 模块 (建议分离 adapter 层)",
            ))
    
    def check_tests_exist(self) -> None:
        """检查测试文件是否存在"""
        test_patterns = [
            "test_*.py", "*_test.py",
            "tests/*.py", "tests/**/*.py",
        ]
        found = self._find_any_pattern(test_patterns)
        
        if found:
            test_files = list(self.module_path.rglob("test_*.py")) + \
                        list(self.module_path.rglob("*_test.py"))
            self.results.append(CheckResult(
                name="测试文件存在",
                status=CheckStatus.PASS,
                message=f"找到 {len(test_files)} 个测试文件",
            ))
        else:
            self.results.append(CheckResult(
                name="测试文件存在",
                status=CheckStatus.FAIL,
                message="未找到测试文件 (应包含 test_*.py 或 tests/ 目录)",
            ))
    
    def check_fallback_defined(self) -> None:
        """检查 fallback 是否定义"""
        if not self.contract_data:
            self.results.append(CheckResult(
                name="Fallback 定义",
                status=CheckStatus.SKIP,
                message="Contract 未加载，跳过",
            ))
            return
        
        fallback = self.contract_data.get('fallback', {})
        if fallback.get('enabled') and fallback.get('behavior'):
            self.results.append(CheckResult(
                name="Fallback 定义",
                status=CheckStatus.PASS,
                message=f"Fallback 已启用: {fallback.get('behavior')[:50]}...",
            ))
        else:
            self.results.append(CheckResult(
                name="Fallback 定义",
                status=CheckStatus.FAIL,
                message="Fallback 未定义或未启用",
            ))
    
    def check_metrics_placeholder(self) -> None:
        """检查 metrics/logging 占位"""
        obs_patterns = ["*metrics*.py", "*observability*.py", "*logging*.py"]
        found = self._find_any_pattern(obs_patterns)
        
        if found:
            self.results.append(CheckResult(
                name="Metrics/Logging 占位",
                status=CheckStatus.PASS,
                message="找到 observability 相关文件",
            ))
        else:
            # 检查 contract 中是否定义了 observability
            if self.contract_data and self.contract_data.get('observability'):
                self.results.append(CheckResult(
                    name="Metrics/Logging 占位",
                    status=CheckStatus.WARN,
                    message="Contract 定义了 observability，但未找到实现文件",
                ))
            else:
                self.results.append(CheckResult(
                    name="Metrics/Logging 占位",
                    status=CheckStatus.WARN,
                    message="建议添加 metrics/logging (contract 和实现)",
                ))
    
    def check_integration_point(self) -> None:
        """检查 integration point 声明"""
        if not self.contract_data:
            self.results.append(CheckResult(
                name="Integration Point 声明",
                status=CheckStatus.SKIP,
                message="Contract 未加载，跳过",
            ))
            return
        
        integration = self.contract_data.get('integration', {})
        point = integration.get('point')
        feature_flag = integration.get('feature_flag')
        
        if point and feature_flag:
            self.results.append(CheckResult(
                name="Integration Point 声明",
                status=CheckStatus.PASS,
                message=f"接入点: {point}, 开关: {feature_flag}",
            ))
        elif point:
            self.results.append(CheckResult(
                name="Integration Point 声明",
                status=CheckStatus.WARN,
                message=f"已声明接入点但未定义 feature flag",
            ))
        else:
            self.results.append(CheckResult(
                name="Integration Point 声明",
                status=CheckStatus.FAIL,
                message="未声明 integration point",
            ))
    
    def _get_nested_value(self, data: Dict, path: str) -> Optional[Any]:
        """获取嵌套字典值"""
        keys = path.split('.')
        current = data
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        return current
    
    def _find_any_pattern(self, patterns: List[str]) -> bool:
        """查找是否匹配任一模式"""
        for pattern in patterns:
            if list(self.module_path.rglob(pattern)):
                return True
        return False


def validate_contract_file(contract_path: str) -> Tuple[bool, List[str]]:
    """验证 contract 文件"""
    errors = []
    
    try:
        with open(contract_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
    except Exception as e:
        return False, [f"无法解析 YAML: {e}"]
    
    if not data:
        return False, ["Contract 文件为空"]
    
    # 检查必填字段
    required = ModulePreflightChecker.REQUIRED_CONTRACT_FIELDS
    for field_path in required:
        keys = field_path.split('.')
        current = data
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                errors.append(f"缺少必填字段: {field_path}")
                break
    
    return len(errors) == 0, errors


def print_results(results: List[CheckResult], module_name: str) -> None:
    """打印检查结果"""
    print(f"\n{'='*60}")
    print(f"模块预检报告: {module_name}")
    print(f"{'='*60}\n")
    
    status_icons = {
        CheckStatus.PASS: "✅",
        CheckStatus.FAIL: "❌",
        CheckStatus.WARN: "⚠️",
        CheckStatus.SKIP: "⏭️",
    }
    
    for result in results:
        icon = status_icons.get(result.status, "❓")
        print(f"{icon} [{result.status.value}] {result.name}")
        print(f"   {result.message}")
        if result.details:
            for detail in result.details:
                print(f"   - {detail}")
        print()
    
    # 统计
    total = len(results)
    passed = sum(1 for r in results if r.status == CheckStatus.PASS)
    failed = sum(1 for r in results if r.status == CheckStatus.FAIL)
    warnings = sum(1 for r in results if r.status == CheckStatus.WARN)
    
    print(f"{'='*60}")
    print(f"总计: {total} 项 | 通过: {passed} | 失败: {failed} | 警告: {warnings}")
    
    if failed == 0:
        print(f"\n✅ 预检通过，模块具备接入主链的基本条件")
    else:
        print(f"\n❌ 预检未通过，请修复失败项后再试")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description="模块预检工具 - 检查模块是否具备接入主链的基本条件"
    )
    parser.add_argument(
        "--module", "-m",
        help="模块名称"
    )
    parser.add_argument(
        "--path", "-p",
        help="模块路径 (默认: modules/{module_name})"
    )
    parser.add_argument(
        "--validate-contract", "-v",
        help="验证 contract 文件路径"
    )
    parser.add_argument(
        "--output", "-o",
        help="输出结果到文件 (JSON 格式)"
    )
    
    args = parser.parse_args()
    
    # 验证 contract 文件模式
    if args.validate_contract:
        valid, errors = validate_contract_file(args.validate_contract)
        if valid:
            print(f"✅ Contract 文件有效: {args.validate_contract}")
            return 0
        else:
            print(f"❌ Contract 文件无效: {args.validate_contract}")
            for error in errors:
                print(f"   - {error}")
            return 1
    
    # 模块检查模式
    if not args.module:
        parser.print_help()
        return 1
    
    module_name = args.module
    module_path = args.path or f"modules/{module_name}"
    
    if not os.path.exists(module_path):
        print(f"❌ 模块路径不存在: {module_path}")
        print(f"   请确认路径或使用 --path 指定")
        return 1
    
    checker = ModulePreflightChecker(module_path)
    all_pass, results = checker.run_all_checks()
    
    print_results(results, module_name)
    
    # 输出到文件
    if args.output:
        import json
        output_data = {
            "module": module_name,
            "path": str(module_path),
            "all_pass": all_pass,
            "results": [
                {
                    "name": r.name,
                    "status": r.status.value,
                    "message": r.message,
                    "details": r.details,
                }
                for r in results
            ]
        }
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        print(f"结果已保存到: {args.output}")
    
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
