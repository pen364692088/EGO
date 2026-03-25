#!/bin/bash
# OpenEmotion 每日检查汇报脚本
# 用途: 检查真源运行状态并生成汇报

set -e

CANONICAL_REPO="/home/moonlight/Project/Github/MyProject/Emotion/OpenEmotion"
QUARANTINE_DIR="/home/moonlight/Project/Quarantine/openemotion_workspace_20260315"
LOG_DIR="$CANONICAL_REPO/artifacts/daily_checks"
DATE=$(date +%Y-%m-%d)
DATETIME=$(date -Iseconds)

# 创建日志目录
mkdir -p "$LOG_DIR"

# 开始报告
REPORT="$LOG_DIR/daily_check_$DATE.md"

cat > "$REPORT" << EOF
# OpenEmotion 每日检查报告

**日期**: $DATE
**时间**: $DATETIME

---

## 1. 服务状态

EOF

# 检查服务状态
echo '```bash' >> "$REPORT"
systemctl --user status emotiond.service --no-pager | head -10 >> "$REPORT" 2>&1 || echo "服务检查失败" >> "$REPORT"
echo '```' >> "$REPORT"
echo "" >> "$REPORT"

# 服务判定
if systemctl --user is-active emotiond.service > /dev/null 2>&1; then
    echo "**状态**: ✅ 运行中" >> "$REPORT"
else
    echo "**状态**: ❌ 未运行" >> "$REPORT"
fi

cat >> "$REPORT" << EOF

---

## 2. API 功能验证

### /health
EOF

# 检查 /health
echo '```json' >> "$REPORT"
HEALTH=$(curl -s http://127.0.0.1:18080/health 2>/dev/null || echo '{"error": "无法连接"}')
echo "$HEALTH" >> "$REPORT"
echo '```' >> "$REPORT"

if echo "$HEALTH" | grep -q '"ok":true'; then
    echo "**状态**: ✅ 正常" >> "$REPORT"
else
    echo "**状态**: ❌ 异常" >> "$REPORT"
fi

cat >> "$REPORT" << EOF

### /decision
EOF

# 检查 /decision
echo '```json' >> "$REPORT"
DECISION=$(curl -s http://127.0.0.1:18080/decision 2>/dev/null || echo '{"error": "无法连接"}')
echo "$DECISION" >> "$REPORT"
echo '```' >> "$REPORT"

# 检查关键字段
if echo "$DECISION" | grep -q 'correlation_id'; then
    echo "- correlation_id: ✅" >> "$REPORT"
else
    echo "- correlation_id: ❌ 缺失" >> "$REPORT"
fi

if echo "$DECISION" | grep -q 'policy_version'; then
    echo "- policy_version: ✅" >> "$REPORT"
else
    echo "- policy_version: ❌ 缺失" >> "$REPORT"
fi

if echo "$DECISION" | grep -q 'schema_version'; then
    echo "- schema_version: ✅" >> "$REPORT"
else
    echo "- schema_version: ❌ 缺失" >> "$REPORT"
fi

cat >> "$REPORT" << EOF

---

## 3. drift_guard 检查

EOF

# 运行 drift_guard
echo '```' >> "$REPORT"
if "$CANONICAL_REPO/deploy/drift_guard" >> "$REPORT" 2>&1; then
    echo "" >> "$REPORT"
    echo "**状态**: ✅ 通过" >> "$REPORT"
else
    echo "" >> "$REPORT"
    echo "**状态**: ❌ 发现漂移" >> "$REPORT"
fi
echo '```' >> "$REPORT"

cat >> "$REPORT" << EOF

---

## 4. 隔离区状态

EOF

# 检查隔离区
if [ -d "$QUARANTINE_DIR" ]; then
    SIZE=$(du -sh "$QUARANTINE_DIR" 2>/dev/null | cut -f1)
    echo "**位置**: \`$QUARANTINE_DIR\`" >> "$REPORT"
    echo "**大小**: $SIZE" >> "$REPORT"
    echo "**状态**: 🟡 存在（待删除）" >> "$REPORT"
    
    # 计算距离封板天数
    SEALEDDATE="2026-03-15"
    DAYS=$(( ($(date -d "$DATE" +%s) - $(date -d "$SEALEDDATE" +%s)) / 86400 ))
    echo "**距封板**: $DAYS 天" >> "$REPORT"
    
    if [ $DAYS -ge 7 ]; then
        echo "" >> "$REPORT"
        echo "**⚠️ 注意**: 已达到 7 天，可执行删除决策" >> "$REPORT"
    fi
else
    echo "**状态**: ✅ 已删除" >> "$REPORT"
fi

cat >> "$REPORT" << EOF

---

## 5. 综合评估

EOF

# 综合判定
ISSUES=0

if ! systemctl --user is-active emotiond.service > /dev/null 2>&1; then
    ISSUES=$((ISSUES + 1))
fi

if ! echo "$HEALTH" | grep -q '"ok":true'; then
    ISSUES=$((ISSUES + 1))
fi

if ! "$CANONICAL_REPO/deploy/drift_guard" > /dev/null 2>&1; then
    ISSUES=$((ISSUES + 1))
fi

if [ $ISSUES -eq 0 ]; then
    echo "**整体状态**: ✅ 正常" >> "$REPORT"
    echo "**发现问题**: 0" >> "$REPORT"
else
    echo "**整体状态**: ⚠️ 有问题" >> "$REPORT"
    echo "**发现问题**: $ISSUES" >> "$REPORT"
fi

cat >> "$REPORT" << EOF

---

**报告生成**: $DATETIME
EOF

# 输出报告路径
echo "REPORT: $REPORT"
