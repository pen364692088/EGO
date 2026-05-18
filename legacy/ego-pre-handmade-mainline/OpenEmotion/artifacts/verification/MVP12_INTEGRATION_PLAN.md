# MVP12 Integration Plan

> 目标：将 `DevelopmentalCycleDaemon` 接线到 `daemon.py`
> 时间：2026-03-13

---

## 1. 接线点清单

### 源模块
- `emotiond/developmental_core/daemon_integration.py`
- 类：`DevelopmentalCycleDaemon`
- 关键方法：
  - `get_cycle_callback()` - 获取可集成到 DMN tick 的回调
  - `update_activity()` - 更新活动时间
  - `run_developmental_cycle()` - 执行发育周期
  - `get_metrics()` - 获取指标

### 目标模块
- `emotiond/daemon.py`
- 类：`DaemonManager`
- 需要添加：
  - `developmental_cycle_loop()` - 新的后台循环
  - `_dev_daemon` - DevelopmentalCycleDaemon 实例

---

## 2. 接线方案

### Step 1: 导入

```python
# emotiond/daemon.py
from emotiond.developmental_core import create_dev_daemon, DaemonCycleConfig
```

### Step 2: 初始化

```python
class DaemonManager:
    def __init__(self):
        self.loops: Dict[str, asyncio.Task] = {}
        self.running = False
        self.logger = logging.getLogger("emotiond.daemon")
        
        # MVP12: Initialize developmental cycle daemon
        self._dev_daemon = create_dev_daemon(
            idle_threshold=60.0,
            min_cycle_interval=30.0,
            max_candidates_per_cycle=5,
        )
```

### Step 3: 创建循环

```python
async def developmental_cycle_loop(self):
    """MVP12: Background loop for developmental cycles"""
    while self.running:
        try:
            # Check if conditions are met for a developmental cycle
            if self._dev_daemon.should_run_cycle():
                result = self._dev_daemon.run_developmental_cycle()
                if result.success:
                    self.logger.info(
                        f"Developmental cycle {result.cycle_id} completed: "
                        f"{result.candidates_generated} candidates, "
                        f"{result.candidates_approved} approved"
                    )
            
            # Sleep before next check
            await asyncio.sleep(10)  # Check every 10 seconds
            
        except asyncio.CancelledError:
            self.logger.info("Developmental cycle loop cancelled")
            break
        except Exception as e:
            self.logger.error(f"Developmental cycle loop error: {e}")
            await asyncio.sleep(30)  # Back off on error
```

### Step 4: 启动循环

```python
async def start(self) -> None:
    # ... existing code ...
    
    # Start background loops
    self.loops["homeostasis"] = asyncio.create_task(homeostasis_loop())
    self.loops["consolidation"] = asyncio.create_task(consolidation_loop())
    
    # MVP12: Start developmental cycle loop
    self.loops["developmental_cycle"] = asyncio.create_task(
        self.developmental_cycle_loop()
    )
```

### Step 5: 活动更新集成

需要在 `core.py` 中调用 `update_activity()` 来跟踪用户活动。

---

## 3. 验证计划

### Gate A: Contract
- [ ] DevelopmentalCycleDaemon 正确初始化
- [ ] 配置参数符合预期
- [ ] 日志输出正确

### Gate B: E2E
- [ ] daemon.py 启动成功
- [ ] developmental_cycle_loop 运行
- [ ] 候选生成并存储到 artifacts

### Gate C: Preflight
- [ ] 现有测试不受影响
- [ ] 无导入错误
- [ ] 无循环依赖

---

## 4. 回滚方案

如果集成失败：
1. 移除 `developmental_cycle_loop` 相关代码
2. 移除 `_dev_daemon` 初始化
3. 恢复 `daemon.py` 到原始状态

```bash
git checkout HEAD -- emotiond/daemon.py
```

---

## 5. 预期产物

- `artifacts/mvp12/cycle_traces/` - 新的 cycle traces
- `artifacts/mvp12/candidate_pool.json` - 更新的候选池
- 日志中显示 developmental cycle 完成

---

*创建时间: 2026-03-13*
