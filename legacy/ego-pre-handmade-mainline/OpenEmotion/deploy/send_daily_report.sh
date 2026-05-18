#!/bin/bash
# 发送 OpenEmotion 每日检查报告通知

set -e

CANONICAL_REPO="/home/moonlight/Project/Github/MyProject/Emotion/OpenEmotion"
LOG_DIR="$CANONICAL_REPO/artifacts/daily_checks"
DATE=$(date +%Y-%m-%d)

# 运行检查
REPORT=$("$CANONICAL_REPO/deploy/daily_check.sh" | grep "REPORT:" | cut -d: -f2- | tr -d ' ')

if [ -z "$REPORT" ]; then
    echo "ERROR: 检查报告生成失败"
    exit 1
fi

# 提取关键信息
SERVICE_STATUS=$(systemctl --user is-active emotiond.service 2>/dev/null || echo "unknown")
HEALTH_STATUS=$(curl -s http://127.0.0.1:18080/health 2>/dev/null | grep -o '"ok":[^,}]*' | cut -d: -f2 || echo "false")
DRIFT_STATUS=$("$CANONICAL_REPO/deploy/drift_guard" 2>&1 | head -1 || echo "ALERT")

# 计算天数
SEALEDDATE="2026-03-15"
TODAY=$(date +%Y-%m-%d)
DAYS=$(( ($(date -d "$TODAY" +%s) - $(date -d "$SEALEDDATE" +%s)) / 86400 ))

# 检查隔离区
QUARANTINE_DIR="/home/moonlight/Project/Quarantine/openemotion_workspace_20260315"
if [ -d "$QUARANTINE_DIR" ]; then
    QUARANTINE_SIZE=$(du -sh "$QUARANTINE_DIR" 2>/dev/null | cut -f1)
    QUARANTINE_STATUS="存在 ($QUARANTINE_SIZE)"
else
    QUARANTINE_STATUS="已删除"
fi

# 构建通知消息
if [ "$SERVICE_STATUS" = "active" ] && [ "$HEALTH_STATUS" = "true" ] && [ "$DRIFT_STATUS" = "DRIFT_GUARD_OK" ]; then
    OVERALL="✅ 正常"
    EMOJI="🟢"
else
    OVERALL="⚠️ 有问题"
    EMOJI="🔴"
fi

# 发送到 Telegram (通过 OpenClaw)
MESSAGE="$EMOJI **OpenEmotion 每日检查报告**

**日期**: $DATE (Day $DAYS)

**服务**: $SERVICE_STATUS
**API**: $HEALTH_STATUS
**漂移**: $DRIFT_STATUS
**隔离区**: $QUARANTINE_STATUS

**整体**: $OVERALL

详细报告: \`$REPORT\`"

# 输出到日志
echo "=== OpenEmotion Daily Check ===" 
echo "Date: $DATE (Day $DAYS)"
echo "Service: $SERVICE_STATUS"
echo "API: $HEALTH_STATUS"
echo "Drift: $DRIFT_STATUS"
echo "Quarantine: $QUARANTINE_STATUS"
echo "Overall: $OVERALL"
echo ""
echo "Report: $REPORT"

# 如果需要发送 Telegram 通知，取消下面的注释
# curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
#   -d chat_id="${TELEGRAM_CHAT_ID}" \
#   -d text="$MESSAGE" \
#   -d parse_mode="Markdown"
