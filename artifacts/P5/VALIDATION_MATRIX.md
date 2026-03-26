# P5 VALIDATION_MATRIX

| env | command / method | result | notes |
|---|---|---|---|
| Current Windows dev env | `cmd.exe /c "py -3 -m pytest tests\\test_packaging_import_boundaries.py tests\\test_runtime_v2_proto_self_runtime.py -q"` | PASS | `10 passed` |
| Current mixed shell env | `python3 -m py_compile ...` | PASS | 主链与 P5 守护测试文件语法通过 |
| Windows editable install | 在临时 Windows venv 中执行 `pip install --no-deps -e OpenEmotion -e EgoCore` 后做 import smoke | PASS | 命令返回码 `0`；stdout 在当前执行桥中未回显 |
| Linux editable install | 计划用临时 venv 验证 | BLOCKED | 当前容器缺少 `ensurepip` / `python3-venv`，无法创建隔离 venv；这是环境限制，不是代码导入失败 |
| CI | 参考 [`EgoCore/docs/PACKAGING_IMPORT_BOUNDARY.md`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/docs/PACKAGING_IMPORT_BOUNDARY.md#L27) | DESIGNED | 本轮定义了 CI 安装与验证命令，未实际跑 CI |

## 当前可安全表述
- 已建立正式 package bootstrap 方案
- 已移除主链 runtime path hack
- 已有 Windows 本地最小验证

## 当前不可安全表述
- 不能报“全环境长期稳定”
- 不能报“所有历史脚本/tests 的 import hack 已清零”
