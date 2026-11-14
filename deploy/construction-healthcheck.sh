#!/usr/bin/env bash
# construction-healthcheck —— C32 施工日志后端「进程在、业务死」自愈
# 由 construction-healthcheck.timer 每 60s 触发；日志进 journald
#
# 探针说明：
#   /healthz 会真正执行一次 SELECT 1
#   200 -> 健康
#   503 -> 应用活着但数据库不可用：重启应用没有意义，只告警、不重启
#   其它/超时 -> 应用层卡死（worker 假活等）：连续失败 2 次后重启
#
# 通知：可选。在 /etc/construction-healthcheck.env 里配置
#   NOTIFY_WEBHOOK=<飞书自定义机器人 webhook>
# 留空则只写 journald。
set -u

URL="http://127.0.0.1:8082/healthz"
UNIT="construction-backend"
STATE="/run/construction-healthcheck.state"
LOCK="/run/construction-healthcheck.lock"
ENVFILE="/etc/construction-healthcheck.env"
MAXTIME=6
NEED_FAIL=2
COOLDOWN=600            # 重启冷却
DB_NOTIFY_COOLDOWN=1800 # 数据库告警冷却

[ -r "$ENVFILE" ] && . "$ENVFILE"

exec 9>"$LOCK"
flock -n 9 || exit 0

say() { printf '%s %s\n' "$(date '+%F %T')" "$*"; }

notify() {
    text="$1"
    [ -n "${NOTIFY_WEBHOOK:-}" ] || return 0
    body='{"msg_type":"text","content":{"text":"'"$text"'"}}'
    if ! curl -sS --max-time 5 -H 'Content-Type: application/json' \
        -d "$body" "$NOTIFY_WEBHOOK" >/dev/null 2>&1; then
        say "NOTIFY 发送失败"
    fi
}

code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time "$MAXTIME" "$URL" 2>/dev/null || true)"
[ -z "$code" ] && code=000
now="$(date +%s)"
host="$(hostname -s 2>/dev/null || echo C32)"

fails=0
last=0
dblast=0
if [ -r "$STATE" ]; then
    read -r fails last dblast < "$STATE" || true
fi
case "$fails" in ''|*[!0-9]*) fails=0 ;; esac
case "$last" in ''|*[!0-9]*) last=0 ;; esac
case "$dblast" in ''|*[!0-9]*) dblast=0 ;; esac

# ---- 健康 ----
if [ "$code" = "200" ]; then
    if [ "$fails" -ne 0 ]; then
        say "RECOVERED http=200，失败计数归零"
        notify "[$host] construction-backend 已恢复（http=200）"
    fi
    printf '0 %s %s\n' "$last" "$dblast" > "$STATE"
    exit 0
fi

# ---- 应用活着但数据库不可用：重启无用，只告警 ----
if [ "$code" = "503" ]; then
    say "DB-DOWN http=503，应用在线但数据库不可用，不重启"
    if [ $((now - dblast)) -ge "$DB_NOTIFY_COOLDOWN" ]; then
        notify "[$host] construction-backend 数据库不可用（/healthz=503），应用未重启，请查 MySQL"
        dblast=$now
    fi
    printf '0 %s %s\n' "$last" "$dblast" > "$STATE"
    exit 0
fi

# ---- 应用层卡死：连续失败即重启 ----
fails=$((fails + 1))
say "FAIL http=$code 连续失败=$fails 阈值=$NEED_FAIL"

if [ $((now - last)) -lt "$COOLDOWN" ]; then
    say "冷却中(${COOLDOWN}s)，本轮不重启"
    printf '%s %s %s\n' "$fails" "$last" "$dblast" > "$STATE"
    exit 0
fi

if [ "$fails" -ge "$NEED_FAIL" ]; then
    say "ACTION systemctl restart $UNIT"
    systemctl restart "$UNIT"
    rc=$?
    say "RESTART rc=$rc"
    if [ "$rc" -eq 0 ]; then
        notify "[$host] construction-backend 探活连续失败，已自动重启（rc=0）"
    else
        notify "[$host] construction-backend 自动重启失败（rc=$rc），需人工介入"
    fi
    printf '0 %s %s\n' "$now" "$dblast" > "$STATE"
else
    printf '%s %s %s\n' "$fails" "$last" "$dblast" > "$STATE"
fi
