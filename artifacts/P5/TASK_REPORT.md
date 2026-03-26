# P5 TASK_REPORT

## 任务名称
P5：Packaging / Import 边界治理

## 任务类型
工程化 / 环境一致性 / 导入治理

## 目标与成功判据
- 去掉主链运行时 `sys.path` 注入等 import hack
- 建立适用于 monorepo + subtree + CI 的正式包导入方式
- 保证 packaging 收口不打断当前主链最小行为

## 当前层级
工程化层 / 导入边界治理层

## 当前确定项
- `OpenEmotion` 原本已有 `pyproject.toml`，但 package discovery 只包含 `emotiond*`，遗漏了主链真实依赖的 `openemotion*`
- `EgoCore` 原本没有正式 `pyproject.toml`
- P4 已经收住账本主权，当前最关键的问题就是环境与导入边界主权

## 关键未知
- 历史 `tools/`、`scripts/`、旧 `tests/` 里的 path hack 仍很多，本轮不全量清扫
- Linux 隔离 editable-install 验证受当前容器缺 `ensurepip` 阻塞
- CI 只完成命令定义，未在真实 pipeline 执行

## 唯一主执行链
1. 盘点 import hack
2. 让 `EgoCore` / `OpenEmotion` 都有正式 package 配置
3. 把主链 runtime path hack 移除
4. 把 `modules/` 中主链真实依赖变成正式可发现包
5. 更新启动脚本与开发文档
6. 用最小测试和多环境验证表收口

## 本次改动
- 新增 [`EgoCore/pyproject.toml`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/pyproject.toml#L1)
  - 正式声明 `app / egocore / system_core / runtime_metrics_aggregator / emotion_context_formatter`
- 修改 [`OpenEmotion/pyproject.toml`](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/pyproject.toml#L24)
  - 正式把 `openemotion*` 也纳入 package discovery
- 移除主链 runtime path hack：
  - [`EgoCore/app/main.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/main.py#L1)
  - [`EgoCore/app/runtime_v2/loop.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/runtime_v2/loop.py#L1)
  - [`EgoCore/app/telegram_bot.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/telegram_bot.py#L1)
  - [`EgoCore/system_core/metrics_hook.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/system_core/metrics_hook.py#L1)
  - 以及若干 `EgoCore/app` 内部旧绝对路径注入点
- 把 [`EgoCore/app/__init__.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/__init__.py#L1) 改成 lazy export，避免 `import app` 时过早触发 Telegram/runtime 副作用
- 为 `runtime_metrics_aggregator` 与 `emotion_context_formatter` 增加包入口 `__init__.py`
- 更新启动脚本：
  - [`EgoCore/start_egocore.sh`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/start_egocore.sh#L1)
  - [`EgoCore/scripts/start_egocore.sh`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/scripts/start_egocore.sh#L1)
  - 都改成验证“包已安装”而不是设置 `PYTHONPATH`
- 新增开发文档：
  - [`EgoCore/docs/PACKAGING_IMPORT_BOUNDARY.md`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/docs/PACKAGING_IMPORT_BOUNDARY.md#L1)
- 新增守护测试：
  - [`EgoCore/tests/test_packaging_import_boundaries.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/tests/test_packaging_import_boundaries.py#L1)

## 主结论
- 正式导入方式的权威源现在回到工程配置，而不是 runtime 代码
- 主链已经不再默认依赖 `sys.path` 注入来找到 `OpenEmotion` 或 `modules`
- `monorepo / subtree / CI` 的正式 bootstrap 规则已经被明确成“先安装包，再启动主链”

## 多环境验证结果
- Windows 本地 pytest：通过，`10 passed`
- 当前 shell 语法校验：通过
- Windows editable install smoke：命令返回码 `0`
- Linux editable install smoke：被当前容器 `ensurepip` 缺失阻塞
- CI：已给出标准命令，但未在真实 CI 执行

## 当前兼容保留
- `EgoCore/tests` 仍有 `15` 个 path hack 文件
- `EgoCore/scripts` 仍有 `9` 个 path hack 文件
- `EgoCore/tools` 仍有 `18` 个 path hack 文件
- `OpenEmotion/tests` 仍有 `96` 个 path hack 文件
- `OpenEmotion/tools` 仍有 `27` 个 path hack 文件

## 为什么这些保留没越界
- 它们不再是正式主链权威入口
- 一次性全量删除会越界成 P6“历史 shim / 垃圾代码清坟”
- P5 的目标是先把正式导入边界收口，而不是一轮扫光全仓历史工件

## 本次结论能证明什么
- 能证明主链入口已不再靠 runtime `sys.path` 注入
- 能证明 `EgoCore` 与 `OpenEmotion` 的正式 package 边界已被工程配置声明
- 能证明 `modules/` 中主链真实依赖已经进入正式 package discovery
- 能证明当前主链最小验证未因 packaging 收口而被打断

## 本次结论不能证明什么
- 不能证明所有历史脚本/tests 的 import hack 已经清零
- 不能证明 Linux / CI 都已完成真实 editable-install 实跑
- 不能证明发布态打包、发版、锁依赖策略已经全部成熟
- 不能证明跨环境长期稳定

## 离 P6 还差什么
- P6 需要系统清理历史脚本、旧 tests、绝对路径和兼容 shim
- P5 只把正式导入边界权威源收回来了，没有做全仓历史清坟
