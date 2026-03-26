# P5 IMPORT_HACK_INVENTORY

## 盘点结论
- `EgoCore/app` 当前剩余 `sys.path` 注入：`0`
- `EgoCore/tests` 当前剩余 `sys.path` 注入：`15`
- `EgoCore/scripts` 当前剩余 `sys.path` 注入：`9`
- `EgoCore/tools` 当前剩余 `sys.path` 注入：`18`
- `OpenEmotion/tests` 当前剩余 `sys.path` 注入：`96`
- `OpenEmotion/tools` 当前剩余 `sys.path` 注入：`27`

## 已移除的主链 hack
| file | old problem | current state |
|---|---|---|
| [`EgoCore/app/main.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/main.py#L1) | 运行时插入 EgoCore / OpenEmotion 路径 | 已移除，改由 package bootstrap |
| [`EgoCore/app/runtime_v2/loop.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/runtime_v2/loop.py#L1) | 模块加载前手工塞 sibling `OpenEmotion` | 已移除 |
| [`EgoCore/app/telegram_bot.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/telegram_bot.py#L1) | 运行时塞 `OpenEmotion` 路径 | 已移除 |
| [`EgoCore/system_core/metrics_hook.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/system_core/metrics_hook.py#L1) | 为 `modules/` 注入顶层路径 | 已移除，改由 package discovery |
| [`EgoCore/app/handlers/social_chat_handler.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/handlers/social_chat_handler.py#L1) | 绝对 `/home/.../EgoCore` 注入 | 已移除 |
| [`EgoCore/app/interaction/event_normalizer.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/interaction/event_normalizer.py#L1) | 绝对 `/home/.../EgoCore` 注入 | 已移除 |
| [`EgoCore/app/openemotion/subject_adapter.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/openemotion/subject_adapter.py#L1) | 绝对 `/home/.../EgoCore` 注入 | 已移除 |
| [`EgoCore/app/response/verbalizer.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/response/verbalizer.py#L1) | 绝对 `/home/.../EgoCore` 注入 | 已移除 |
| [`EgoCore/app/response/verbalizer_v3.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/response/verbalizer_v3.py#L1) | 绝对 `/home/.../EgoCore` 注入 | 已移除 |

## 已收口的工程权威源
- `EgoCore/pyproject.toml`
- `OpenEmotion/pyproject.toml`
- [`EgoCore/docs/PACKAGING_IMPORT_BOUNDARY.md`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/docs/PACKAGING_IMPORT_BOUNDARY.md#L1)

## 仍保留的兼容 hack
- 历史 `EgoCore/tests`、`EgoCore/scripts`、`EgoCore/tools`
- 大量 `OpenEmotion/tests`、`OpenEmotion/tools`

## 保留理由
- 这些不再是正式主链入口
- 一轮全量清坟风险高，且会越界成 P6
- 当前要求是把正式导入边界权威源收回工程配置，而不是一次性清理所有历史工件
