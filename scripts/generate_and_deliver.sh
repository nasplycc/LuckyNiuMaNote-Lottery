#!/usr/bin/env bash
# 双色球发号：生成选号 + 网络故障自动重试推送
# cron 任务 payload 调用本脚本（替代直接跑 generate_ssq.py）
set -u
cd /vol1/1000/code/lottery-ssq

# 定位 openclaw：优先 nvm 稳定安装路径（真正的 openclaw CLI）。
# 不能用 command -v 的 PATH 结果：cron isolated 环境里 PATH 会命中
# /home/Jaben/.openclaw/tmp/agent-cli/openclaw（临时 wrapper），该路径在 cron 内
# 无法接入 gateway 会话上下文，导致推送静默失败（26130 实测 error×3）。
OPENCLAW_BIN=""
for c in /home/Jaben/.nvm/versions/node/v24.20.0/bin/openclaw \
         /usr/local/bin/openclaw \
         /usr/bin/openclaw; do
  if [ -x "$c" ]; then
    OPENCLAW_BIN="$c"
    break
  fi
done
if [ -z "$OPENCLAW_BIN" ]; then
  OPENCLAW_BIN="$(command -v openclaw 2>/dev/null || true)"
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
