# EgoCore 运维操作手册

> 版本: 2.0
> 更新日期: 2026-03-24
> 变更: 新增脚本化启停流程，解决锁冲突问题，确保日志持久化

---

## 目录

1. [快速开始](#快速开始)
2. [启动/停止/重启](#启动停止重启)
3. [状态检查](#状态检查)
4. [日志管理](#日志管理)
5. [故障排查](#故障排查)

---

## 快速开始

### 环境要求

- Python 3.10+
- Windows/Git Bash 环境
- Telegram Bot Token 已配置 (.env)

### 目录结构

```
EgoCore/
├── scripts/
│   ├── start_egocore.sh     # 启动脚本
│   ├── stop_egocore.sh      # 停止脚本
│   ├── restart_egocore.sh   # 重启脚本
│   └── status_egocore.sh    # 状态检查脚本
├── logs/                     # 日志目录
│   ├── egocore_YYYYMMDD_HHMMSS.log  # 主日志（按启动时间）
│   ├── proto_self_trace.jsonl       # Proto-Self trace（持续追加）
│   ├── egocore.pid                  # 当前 PID 文件
│   └── archive/                     # 历史日志归档
├── artifacts/
│   └── proto_self_mirror/
│       └── state.json        # Proto-Self 状态镜像（实时更新）
└── docs/
    └── OPERATIONS.md         # 本文件
```

---

## 启动/停止/重启

### 推荐方式：使用脚本

```bash
# 进入 EgoCore 目录
cd EgoCore

# 启动（推荐）
./scripts/start_egocore.sh

# 停止
./scripts/stop_egocore.sh

# 重启
./scripts/restart_egocore.sh

# 查看状态
./scripts/status_egocore.sh
```

### 启动 EgoCore

```bash
./scripts/start_egocore.sh [--telegram] [--status]
```

**启动流程：**
1. 检查是否已运行（避免重复启动）
2. 清理陈旧锁文件（自动识别僵尸进程）
3. 归档旧 trace 日志（保留历史）
4. 验证环境（PYTHONPATH 检查）
5. 启动进程并记录 PID

**输出示例：**
```
========================================
EgoCore Startup
========================================
Time: Mon Mar 24 20:40:30 CST 2026
Log Dir: D:/Project/.../EgoCore/logs
Lock File: .../egocore-telegram-poller.lock

[1/4] Cleaning stale locks...
  ✓ Locks cleaned
[2/4] Ensuring log directory...
  ✓ Archived old trace to logs/archive/proto_self_trace_20260324_204030.jsonl
  ✓ Log directory ready
[3/4] Verifying environment...
  ✓ Environment verified (PYTHONPATH: ...)
[4/4] Starting EgoCore...
  Log file: logs/egocore_20260324_204030.log
  Mode: --telegram
  Started with PID: 1234

========================================
✓ EgoCore started successfully
========================================
```

### 停止 EgoCore

```bash
./scripts/stop_egocore.sh [--force]
```

**停止流程：**
1. 读取 PID 文件
2. 发送 SIGTERM 信号（优雅停止）
3. 等待 2 秒
4. 如仍在运行，可选 `--force` 强制 kill
5. 清理锁文件和 PID 文件

### 重启 EgoCore

```bash
./scripts/restart_egocore.sh
```

**重启流程：**
1. 执行强制停止（确保干净状态）
2. 等待 2 秒
3. 执行启动
4. 显示当前状态

---

## 状态检查

### 查看完整状态

```bash
./scripts/status_egocore.sh
```

**输出示例：**
```
========================================
EgoCore Status
========================================
Time: Mon Mar 24 20:45:00 CST 2026

[Process Status]
  Status: RUNNING
  PID: 1234
  Uptime: 00:05:23
  CPU: 2.3%
  Memory: 1.5%

[Lock Status]
  Lock File: EXISTS
  Path: .../egocore-telegram-poller.lock

[Log Files]
  Latest Log: logs/egocore_20260324_204030.log
  Size: 12345 bytes
  Modified: 2026-03-24 20:40:30

[Proto-Self Trace]
  File: logs/proto_self_trace.jsonl
  Entries: 42
  Size: 6838 bytes
  Latest: {"event_id": "telegram:dm:...", ...}

[Proto-Self State]
  File: artifacts/proto_self_mirror/state.json
  Size: 13442 bytes

========================================
✓ EgoCore is running
```

---

## 日志管理

### 日志文件说明

| 类型 | 路径 | 说明 | 保留策略 |
|------|------|------|----------|
| 主日志 | `logs/egocore_YYYYMMDD_HHMMSS.log` | 每次启动新建 | 自动轮转，10MB×5 |
| Proto-Self Trace | `logs/proto_self_trace.jsonl` | 持续追加 | 启动时归档 |
| 状态镜像 | `artifacts/proto_self_mirror/state.json` | 每次消息更新 | 实时覆盖 |
| 归档日志 | `logs/archive/proto_self_trace_*.jsonl` | 历史备份 | 手动清理 |
| PID 文件 | `logs/egocore.pid` | 当前进程ID | 停止时删除 |

### 查看日志

```bash
# 实时查看当前主日志
tail -f logs/egocore_$(date +%Y%m%d)*.log

# 查看最新 trace
tail -f logs/proto_self_trace.jsonl

# 查看 Proto-Self 初始化标记
grep "Proto-Self Kernel Status" logs/egocore_*.log

# 查看 PSK trace 标记
grep "PSK-" logs/egocore_*.log

# 查看错误
grep -i error logs/egocore_*.log
```

### 日志持久化保证

1. **启动时自动归档**: `start_egocore.sh` 启动前自动备份旧 trace
2. **文件轮转**: 使用 `RotatingFileHandler`，单文件最大 10MB，保留 5 个备份
3. **PID 文件**: 记录进程 ID，便于管理和监控
4. **实时写入**: 使用 `-u` 参数启动 Python，确保无缓冲输出

### 清理历史日志

```bash
# 查看归档目录大小
du -sh logs/archive/

# 清理 30 天前的归档
find logs/archive/ -name "proto_self_trace_*.jsonl" -mtime +30 -delete

# 清理旧的主日志（保留最近 10 个）
ls -t logs/egocore_*.log | tail -n +11 | xargs rm -f
```

---

## 故障排查

### 问题：锁文件冲突

**症状：**
```
❌ Telegram poller lock already held: ...egocore-telegram-poller.lock
```

**原因：**
- 上一次停止未清理锁文件
- 进程崩溃后残留锁

**解决（使用脚本）：**
```bash
# 自动处理
./scripts/stop_egocore.sh --force
./scripts/start_egocore.sh
```

**解决（手动）：**
```bash
# 查找 Python 进程
ps aux | grep python

# 终止进程
kill -9 <PID>

# 删除锁文件
rm /c/Users/LEO/AppData/Local/Temp/egocore-telegram-poller.lock

# 重新启动
./scripts/start_egocore.sh
```

### 问题：端口/进程冲突

**症状：**
```
ERROR: EgoCore is already running (PID: xxxx)
```

**解决：**
```bash
# 检查实际状态
./scripts/status_egocore.sh

# 如进程不存在但 PID 文件残留
rm -f logs/egocore.pid
./scripts/start_egocore.sh
```

### 问题：Proto-Self 未加载

**症状：**
```
[PSK-INIT] Proto-Self NOT available
PROTO_SELF_ADAPTER_LOADED=false
```

**排查步骤：**
```bash
# 1. 检查配置
grep "enabled" config/app.yaml
# 应显示: enabled: true

# 2. 检查 PYTHONPATH
export PYTHONPATH="D:\Project\AIProject\MyProject\Ego\OpenEmotion"
python -c "from app.openemotion_adapter import ProtoSelfAdapter; print('OK')"

# 3. 重启
./scripts/restart_egocore.sh
```

### 问题：日志不写入

**检查：**
```bash
# 1. 检查日志目录权限
ls -la logs/

# 2. 检查磁盘空间
df -h

# 3. 检查进程是否存活
./scripts/status_egocore.sh
```

### 问题：Telegram 消息无响应

**排查：**
```bash
# 1. 检查 Bot 是否运行
./scripts/status_egocore.sh

# 2. 查看最新日志
tail -50 logs/egocore_$(date +%Y%m%d)*.log

# 3. 检查 Proto-Self 是否处理
tail -20 logs/proto_self_trace.jsonl

# 4. 检查是否有错误
grep -i error logs/egocore_*.log | tail -10
```

---

## 常用命令速查

| 操作 | 命令 |
|------|------|
| 启动 | `./scripts/start_egocore.sh` |
| 停止 | `./scripts/stop_egocore.sh` |
| 强制停止 | `./scripts/stop_egocore.sh --force` |
| 重启 | `./scripts/restart_egocore.sh` |
| 状态 | `./scripts/status_egocore.sh` |
| 看日志 | `tail -f logs/egocore_*.log` |
| 看 trace | `tail -f logs/proto_self_trace.jsonl` |
| 查进程 | `ps aux \| grep python` |

---

## 环境变量

| 变量 | 说明 | 示例 |
|------|------|------|
| `PYTHONPATH` | OpenEmotion 库路径 | `D:\Project\AIProject\MyProject\Ego\OpenEmotion` |
| `TEMP` | 临时文件目录 | Windows: `%TEMP%` |

---

## 关键文件

| 文件 | 用途 | 清理策略 |
|------|------|----------|
| `logs/egocore.pid` | 进程 PID 记录 | 停止时自动删除 |
| `$TEMP/egocore-telegram-poller.lock` | Telegram 轮询锁 | 启动时自动清理 |
| `logs/proto_self_trace.jsonl` | Proto-Self 事件追踪 | 启动时自动归档 |
| `artifacts/proto_self_mirror/state.json` | Proto-Self 状态 | 实时更新，勿删 |
| `logs/archive/proto_self_trace_*.jsonl` | 历史 trace 归档 | 手动清理（>30天） |

---

## 最佳实践

1. **始终使用脚本**: 避免手动管理锁文件和 PID
2. **定期归档清理**: 每月清理一次 `logs/archive/`
3. **监控状态**: 使用 `./scripts/status_egocore.sh` 定期检查
4. **保留历史**: 重要测试前手动备份 trace 文件

---

*文档版本: 2.0*
*更新: 2026-03-24 - 新增脚本化运维流程*
