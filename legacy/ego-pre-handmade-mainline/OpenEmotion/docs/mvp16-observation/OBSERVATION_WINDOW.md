# MVP16 Observation Window

> 长期维护观测期 - 证据驱动、治理优先

## 1. Purpose

MVP16 完成后，不立即推进 MVP17，而是进入受治理的观测期。

目标：证明"开放发展能力 + 身份连续性 + 可审计因果证据"在真实运行中稳定。

**不是**什么都不做，**而是**带着明确目标观测。

## 2. Duration

- **Start**: 2026-03-12
- **Duration**: 7–14 天
- **End Criteria**: 所有观测指标稳定，无 critical anomaly

## 3. Four Daily Checks

每天只做四件事：

### Check 1: Long-Horizon Continuity
- Developmental trajectory 是否连贯
- Episode history 是否有断层
- Continuity score 是否稳定

### Check 2: Identity Drift Detection
- Identity invariants 是否被违反
- Protected values 是否变化
- Branch fragmentation 是否出现

### Check 3: Replay Consistency
- Major transitions 是否可 replay
- Hash stability 是否达标
- Audit log 是否完整

### Check 4: Governance Integrity
- Governor 是否在线
- Gate chain 是否完整
- Kill switch 是否可用

## 4. Metrics to Track

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| developmental_state_load_success | ≥ 99% | < 95% |
| major_transition_replay_consistency | ≥ 99% | < 95% |
| invariant_violation_count | 0 | > 0 |
| branch_fragmentation_rate | < 5% | > 10% |
| continuity_score | ≥ 0.8 | < 0.6 |
| governance_compliance | 100% | < 100% |

## 5. Daily Routine

```bash
# Run daily observation check
cd ~/Project/Github/MyProject/Emotion/OpenEmotion
python tools/mvp16_daily_check.py

# Or manually:
pytest tests/mvp16/ -v
python -c "from emotiond.developmental import get_developmental_manager; m = get_developmental_manager(); print(m.get_summary())"
```

## 6. Evidence Collection

每天生成一份观测日志：

```
artifacts/mvp16-observation/day_N.md
```

包含：
- 四项检查结果
- 异常记录（如有）
- 趋势分析
- 下一步行动

## 7. Alert Conditions

以下情况触发 **ALERT** 并暂停观测：

- invariant_violation_count > 0
- governance_compliance < 100%
- replay_consistency < 95%
- continuity_score < 0.6
- 无法恢复的 identity drift

## 8. Exit Criteria

观测期结束时，回答五个核心问题：

1. **Identity Stability**: 身份是否在跨环境/跨任务中保持稳定？
2. **Governance Integrity**: 治理壳是否始终在线？
3. **Developmental Coherence**: 发展轨迹是否连贯？
4. **Evidence Quality**: 证据包是否完整可审计？
5. **Ready for Next Phase**: 是否有证据支撑进入下一阶段？

## 9. Forbidden During Observation

- ❌ 新功能开发
- ❌ 架构大改
- ❌ 绕过 Governor
- ❌ 跳过证据收集
- ❌ 意识声明

## 10. Allowed During Observation

- ✅ 监控指标
- ✅ 修复 critical bug
- ✅ 文档完善
- ✅ 测试补充
- ✅ 证据整理
