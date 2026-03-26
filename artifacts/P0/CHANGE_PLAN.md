# P0 CHANGE_PLAN

## 任务
P0：真实状态审计与过度报喜清理

## 主执行链
1. 收集公开与半公开材料中的强口径表述
2. 为每条表述追溯对应 artifact / report / sample / failure 证据
3. 按 `E0~E6` 重标最高证据级别
4. 只对明确越级或已过时口径做最小修正
5. 产出状态矩阵、冲突清单、失败样本清单

## 本次最小改动
- 降级 `README.md` 中“稳态收口”“正常运行”等容易被读成稳定态的措辞
- 给 `artifacts/telegram_real_mainline_v1/reports/VALIDATION_REPORT_V1.md` 增加“历史快照”声明，并标记其旧 `6/6` 口径已过时
- 不改业务逻辑
- 不删除历史 artifacts
- 不提前处理 P1 及后续任务

## 不做什么
- 不重构 `RuntimeV2Loop`
- 不修改 OpenEmotion 本体
- 不补新的真实样本
- 不把 P0 扩大成 evidence/runtime 架构重写

## 本次结论不能证明什么
- 不能证明所有历史文档都已经完全同步
- 不能证明后续任务不再出现新的越级口径
- 不能证明系统已稳定运行
- 不能证明观察期已经开始执行或已经完成
