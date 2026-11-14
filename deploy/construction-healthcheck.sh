#!/usr/bin/env bash
# construction-healthcheck —— C32 施工日志后端「进程在、业务死」自愈
# 由 construction-healthcheck.timer 每 60s 触发；日志进 journald
set -u

URL="http://127.0.0.1:8082/admin/login"
UNIT="construction-backend"
STATE="/run/construction-healthcheck.state"
LOCK="/run/construction-healthcheck.lock"
MAXTIME=6
NEED_FAIL=2
COOLDOWN=600

exec 9>"$LOCK"
flock -n 9 || exit 0

say() { printf '%s %s\n' "$(date '+%F %T')" "$*"; }

code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time "$MAXTIME" "$URL" 2>/dev/null || true)"
[ -z "$code" ] && code=000
now="$(date +%s)"

fails=0
last=0
if [ -r "$STATE" ]; then
    read -r fails last < "$STATE" || true
fi
case "$fails" in ''|*[!0-9]*) fails=0 ;; esac
case "$last" in ''|*[!0-9]*) last=0 ;; esac

if [ "$code" = "200" ] || [ "$code" = "302" ]; then
    if [ "$fails" -ne 0 ]; then
        say "RECOVERED http=$code，失败计数归零"
    fi
    printf '0 %s\n' "$last" > "$STATE"
    exit 0
fi

fails=$((fails + 1))
say "FAIL http=$code 连续失败=$fails 阈值=$NEED_FAIL"

if [ $((now - last)) -lt "$COOLDOWN" ]; then
    say "冷却中(${COOLDOWN}s)，本轮不重启"
    printf '%s %s\n' "$fails" "$last" > "$STATE"
    exit 0
fi

if [ "$fails" -ge "$NEED_FAIL" ]; then
    say "ACTION systemctl restart $UNIT"
    systemctl restart "$UNIT"
    say "RESTART rc=$?"
    printf '0 %s\n' "$now" > "$STATE"
else
    printf '%s %s\n' "$fails" "$last" > "$STATE"
fi
