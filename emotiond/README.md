# emotiond/README.md

## 目录用途

OpenEmotion 的服务面 / 运行中处理面。

这里更偏：
- HTTP/API
- daemon
- 调度
- 服务化处理
- appraisal / reflection / state / memory 服务协同

## 主要入口

- `api.py`
- `daemon.py`
- `main.py`
- `config.py`
- `state.py`

## 上下游依赖

### 上游
- EgoCore adapter / contracts
- systemd/service/deploy

### 下游
- `openemotion/` 本体模块
- data/db/logs
- schemas / internal service processing

## 常改文件

- `api.py`
- `daemon.py`
- `state.py`
- `appraisal.py`
- `reflection.py`
- `self_model_*`
- `memory/*`

## 不该放什么

- Telegram/CLI 入口
- 工具执行层
- EgoCore 的最终审批和 runtime 主权

## 与另一核心如何衔接

emotiond 是 OpenEmotion 暴露给 EgoCore 的服务/处理面，不应越权成为对外渠道宿主。
