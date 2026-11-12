#!/usr/bin/env bash
# 双色球发号：生成选号 + 网络故障自动重试推送
# cron 任务 payload 调用本脚本（替代直接跑 generate_ssq.py）
set -u
cd /vol1/1000/code/lottery-ssq

# 定位 openclaw：优先绝对路径，回退 PATH
OPENCLAW_BIN="$(command -v openclaw 2>/dev/null || true)"
if [ -z "$OPENCLAW_BIN" ] && [ -x /home/Jaben/.nvm/versions/node/v24.20.0/bin/openclaw ]; then
  OPENCLAW_BIN=/home/Jaben/.nvm/versions/node/v24.20.0/bin/openclaw
fi
if [ -z "$OPENCLAW_BIN" ]; then
  echo "❌ openclaw 命令未找到（PATH=$PATH）"
  exit 1
fi
echo "🔧 使用 openclaw: $OPENCLAW_BIN" >&2

OUT="$(python3 scripts/generate_ssq.py 2>&1)"
RC=$?
if [ $RC -ne 0 ]; then
  echo "$OUT"
  exit $RC
fi

# 推送选号结果到 Telegram；网络抖动时自动重试（最多5次，退避 sleep）
MAX=5
try=0
period="$(date +%m.%d)"
LOG="logs/push_$(date +%Y%m%d_%H%M%S).log"
mkdir -p logs
until [ $try -ge $MAX ]; do
  try=$((try+1))
  if "$OPENCLAW_BIN" message send --channel telegram --account telegram-finnace --target 8594152561 \
      -m "🎯 双色球 ${period} 期选号（第 ${try} 次尝试）\n${OUT}" >"$LOG" 2>&1; then
    echo "✅ 选号已推送（第 ${try} 次尝试成功）"
    exit 0
  fi
  echo "⚠️ 第 ${try} 次推送失败：$(tail -3 "$LOG")"
  sleep $((try * 10))
done

echo "❌ 重试 ${MAX} 次仍失败，选号结果已存于 outputs/，请手动检查网络后补发（日志: $LOG）"
exit 1
