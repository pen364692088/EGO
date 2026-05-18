# MVP12 主链生效证据补全计划

> 目标：证明 DevelopmentalCycleDaemon 在 daemon 常态运行中生效
> 时间：2026-03-13

---

## 1. 所需证据类型

### A. 常态命中证据
- [ ] daemon 启动后 _developmental_cycle_loop 自动运行
- [ ] 满足条件时自动触发 cycle
- [ ] artifacts 中产生持续的 cycle 记录

### B. 非侵入证据
- [ ] 不影响现有 homeostasis_loop
- [ ] 不影响 consolidation_loop
- [ ] 错误不影响 daemon 稳定性

### C. Fallback/Feature Flag 验证
- [ ] 可通过配置禁用 developmental cycle
- [ ] 禁用后 daemon 仍正常运行
- [ ] 启用后恢复功能

---

## 2. 实现方案

### 2.1 添加 Feature Flag

```python
# emotiond/config.py
ENABLE_DEVELOPMENTAL_CYCLE = os.environ.get("ENABLE_DEVELOPMENTAL_CYCLE", "true").lower() == "true"
```

### 2.2 添加健康检查端点

```python
# DaemonManager
def get_developmental_status(self) -> Dict[str, Any]:
    return {
        "enabled": ENABLE_DEVELOPMENTAL_CYCLE,
        "running": "developmental_cycle" in self.loops,
        "metrics": self.get_developmental_metrics() if ENABLE_DEVELOPMENTAL_CYCLE else None
    }
```

### 2.3 验证脚本

```python
# tools/verify_mvp12_daemon.py
# 验证 daemon 运行时 developmental cycle 生效
```

---

## 3. Gate 通过标准

### Gate A: Contract
- [ ] Feature flag 可控制启用/禁用
- [ ] 配置项文档化

### Gate B: E2E
- [ ] daemon 运行 60 秒，产生至少 1 个 cycle
- [ ] 禁用后无 cycle 记录
- [ ] 启用后恢复记录

### Gate C: Preflight
- [ ] 现有测试不受影响
- [ ] 无错误日志污染

---

## 4. 回滚方案

```bash
# 禁用 developmental cycle
export ENABLE_DEVELOPMENTAL_CYCLE=false

# 或回滚代码
git checkout HEAD~1 -- emotiond/daemon.py
```

---

*创建时间: 2026-03-13*
