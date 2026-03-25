#!/usr/bin/env python3
"""
OpenEmotion 文档盘点层生成器

生成 docs/generated/ 目录下的自动盘点文件：
- module_map.md
- repo_inventory.md
"""

import os
import sys
from pathlib import Path
from datetime import datetime


def get_repo_root():
    """获取仓库根目录"""
    script_dir = Path(__file__).parent
    return script_dir.parent


def scan_modules(repo_root: Path) -> dict:
    """扫描 openemotion/ 目录下的模块"""
    modules = {}
    openemotion_dir = repo_root / "openemotion"
    
    if not openemotion_dir.exists():
        return modules
    
    for item in sorted(openemotion_dir.iterdir()):
        if item.is_dir() and not item.name.startswith("_"):
            py_files = list(item.glob("*.py"))
            modules[item.name] = {
                "path": str(item.relative_to(repo_root)),
                "files": [f.name for f in py_files],
                "file_count": len(py_files)
            }
        elif item.is_file() and item.suffix == ".py":
            if item.name not in modules:
                modules[item.name] = {
                    "path": str(item.relative_to(repo_root)),
                    "files": [item.name],
                    "file_count": 1
                }
    
    return modules


def generate_module_map(repo_root: Path, modules: dict) -> str:
    """生成 module_map.md"""
    lines = [
        "# Module Map",
        "",
        f"Generated: {datetime.now().isoformat()}",
        "",
        "## openemotion/ 目录结构",
        "",
        "| 模块 | 文件数 | 说明 |",
        "|------|--------|------|",
    ]
    
    module_descriptions = {
        "proto_self": "Proto-Self Kernel v1（主体内核主链）",
        "identity": "身份不变量",
        "self_model": "自我模型",
        "memory": "三层记忆模型",
        "cycle_core": "Cycle 核心",
        "interaction": "交互层",
        "contracts": "契约定义",
    }
    
    for name, info in modules.items():
        if isinstance(info.get("files"), list) and len(info["files"]) > 1:
            desc = module_descriptions.get(name, "")
            lines.append(f"| [{name}]({info['path']}) | {info['file_count']} | {desc} |")
    
    lines.extend([
        "",
        "## 关键入口文件",
        "",
        "| 文件 | 职责 |",
        "|------|------|",
        "| `proto_self/kernel.py` | 主循环 process_event() |",
        "| `proto_self/schemas.py` | KernelEvent / KernelOutput |",
        "| `proto_self/state.py` | ProtoSelfState (4+1 状态) |",
        "| `proto_self/appraisal.py` | drive_field 更新 |",
        "| `proto_self/reflection.py` | 反思触发 |",
        "| `proto_self/cycles.py` | cycle 固化 |",
        "",
    ])
    
    return "\n".join(lines)


def generate_repo_inventory(repo_root: Path) -> str:
    """生成 repo_inventory.md"""
    lines = [
        "# Repository Inventory",
        "",
        f"Generated: {datetime.now().isoformat()}",
        "",
        "## 目录结构",
        "",
        "```",
    ]
    
    # 生成目录树
    for item in sorted(repo_root.iterdir()):
        if item.is_dir() and not item.name.startswith("."):
            lines.append(f"{item.name}/")
            if item.name == "openemotion":
                for subitem in sorted(item.iterdir()):
                    if subitem.is_dir():
                        lines.append(f"  {subitem.name}/")
                    elif subitem.is_file() and subitem.suffix == ".py":
                        lines.append(f"  {subitem.name}")
        elif item.is_file() and not item.name.startswith("."):
            lines.append(f"{item.name}")
    
    lines.extend([
        "```",
        "",
        "## 关键路径",
        "",
        "| 路径 | 说明 |",
        "|------|------|",
        "| `openemotion/proto_self/` | Proto-Self Kernel v1 |",
        "| `openemotion/identity/` | 身份不变量 |",
        "| `openemotion/self_model/` | 自我模型 |",
        "| `openemotion/memory/` | 三层记忆 |",
        "| `docs/` | 文档 |",
        "| `artifacts/` | 验证 artifact |",
        "",
    ])
    
    return "\n".join(lines)


def main():
    repo_root = get_repo_root()
    generated_dir = repo_root / "docs" / "generated"
    generated_dir.mkdir(parents=True, exist_ok=True)
    
    # 扫描模块
    modules = scan_modules(repo_root)
    
    # 生成 module_map.md
    module_map_content = generate_module_map(repo_root, modules)
    module_map_path = generated_dir / "module_map.md"
    module_map_path.write_text(module_map_content)
    print(f"Generated: {module_map_path}")
    
    # 生成 repo_inventory.md
    inventory_content = generate_repo_inventory(repo_root)
    inventory_path = generated_dir / "repo_inventory.md"
    inventory_path.write_text(inventory_content)
    print(f"Generated: {inventory_path}")
    
    print("\nDone!")


if __name__ == "__main__":
    main()
