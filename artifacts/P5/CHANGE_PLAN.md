# P5 CHANGE_PLAN

## 本轮目标
- 去掉主链 runtime `sys.path` 注入
- 让 `EgoCore` / `OpenEmotion` 都有正式包配置
- 把 `modules/` 中主链真实依赖的包也纳入正式 package discovery
- 给出 monorepo / subtree / CI 的单一 bootstrap 规则

## 唯一主执行链
1. 盘点 import hack
2. 建立正式 package 配置
3. 删除主链 runtime path hack
4. 把主链启动脚本改成 package-based 验证
5. 增加最小守护测试与开发文档
6. 记录兼容保留与多环境验证结果

## 本轮不做
- 不全量清坟 `tools/`、`scripts/`、历史 `tests/` 中的所有 hack
- 不重命名全仓 `app.*` import
- 不改业务逻辑
