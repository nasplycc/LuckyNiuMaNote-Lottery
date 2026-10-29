#!/usr/bin/env bash
# 双色球发号：生成选号 + 网络故障自动重试推送
# cron 任务 payload 调用本脚本（替代直接跑 generate_ssq.py）
set -u
cd /vol1/1000/code/lottery-ssq

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
until [ $try -ge $MAX ]; do
  try=$((try+1))
  if openclaw message send --channel telegram --target 8594152561 \
      -m "🎯 双色球 ${period} 期选号（第 ${try} 次尝试）\n${OUT}" >/dev/null 2>&1; then
    echo "✅ 选号已推送（第 ${try} 次尝试成功）"
    exit 0
  fi
  echo "⚠️ 第 ${try} 次推送失败（网络异常）"
  sleep $((try * 10))
done

echo "❌ 重试 ${MAX} 次仍失败，选号结果已存于 outputs/，请手动检查网络后补发"
exit 1
