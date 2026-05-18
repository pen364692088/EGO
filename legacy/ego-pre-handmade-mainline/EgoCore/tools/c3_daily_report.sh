#!/bin/bash
# C3 每日观察报告脚本
# 运行观察脚本并生成报告

set -e

# 配置
EGOCORE_DIR="/home/moonlight/Project/Github/MyProject/EgoCore"
DATE=$(date +%Y-%m-%d)
REPORT_FILE="$EGOCORE_DIR/artifacts/verification/c3_shadow/daily/${DATE}.json"
LOG_FILE="$EGOCORE_DIR/logs/c3_daily_report.log"

# 日志函数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

log "Starting C3 daily report for $DATE"

# 切换到 EgoCore 目录
cd "$EGOCORE_DIR"

# 运行观察脚本
log "Running shadow observer..."
python3 tools/c3_shadow_observer.py --date "$DATE" > /tmp/c3_output.txt 2>&1

# 检查报告是否生成
if [ -f "$REPORT_FILE" ]; then
    log "Report generated: $REPORT_FILE"
    cat /tmp/c3_output.txt
    log "Report completed"
else
    log "ERROR: Report file not generated"
    echo "⚠️ C3 日报生成失败，请检查日志"
    exit 1
fi
