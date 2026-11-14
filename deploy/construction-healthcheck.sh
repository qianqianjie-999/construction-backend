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
#   NOTIFY_WEBHOOK=<机器人 webhook 或 pushplus>
#     钉钉/企业微信: https://oapi.dingtalk.com/robot/send?access_token=xxx
#                    https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx
#     飞书:          https://open.feishu.cn/open-apis/bot/v2/hook/xxx
#     PushPlus(个人微信推送): 填 pushplus，token 放 NOTIFY_TOKEN
#   NOTIFY_SECRET=<钉钉机器人「加签」密钥，选关键词模式时留空>
#   NOTIFY_TOKEN=<PushPlus 的 token>
# 邮件告警（与上面互不影响，填了 NOTIFY_EMAIL_TO 就会发邮件）：
#   NOTIFY_EMAIL_TO=收件人（可逗号分隔多个）
#   NOTIFY_EMAIL_USER=发件邮箱，如 yanjie086@163.com
#   NOTIFY_EMAIL_PASS=邮箱「客户端授权码」（不是登录密码）
#   NOTIFY_EMAIL_HOST=smtp.163.com   NOTIFY_EMAIL_PORT=465（SSL）
# 报文格式按 webhook 域名自动适配。全部留空则只写 journald。
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

notify_webhook() {
    text="$1"
    url="$NOTIFY_WEBHOOK"
    case "$url" in
        *dingtalk*|*qyapi.weixin.qq.com*)
            # 钉钉 / 企业微信：msgtype -> text.content
            body='{"msgtype":"text","text":{"content":"'"$text"'"}}'
            if [ -n "${NOTIFY_SECRET:-}" ]; then
                ts="$(date +%s)000"
                sign="$(python3 -c '
import base64, hashlib, hmac, sys, urllib.parse
ts, sec = sys.argv[1], sys.argv[2]
digest = hmac.new(sec.encode(), ("%s\n%s" % (ts, sec)).encode(), hashlib.sha256).digest()
print(urllib.parse.quote_plus(base64.b64encode(digest)))
' "$ts" "$NOTIFY_SECRET" 2>/dev/null)"
                [ -n "$sign" ] && url="${url}&timestamp=${ts}&sign=${sign}"
            fi
            ;;
        *pushplus*)
            # PushPlus：推送到个人微信，token 放 NOTIFY_TOKEN
            if [ -z "${NOTIFY_TOKEN:-}" ]; then
                say "NOTIFY 未配置 NOTIFY_TOKEN，跳过"
                return 0
            fi
            url="https://www.pushplus.plus/send"
            body='{"token":"'"$NOTIFY_TOKEN"'","title":"C32 施工日志后端告警","content":"'"$text"'","template":"txt"}'
            ;;
        *)
            # 飞书：msg_type -> content.text
            body='{"msg_type":"text","content":{"text":"'"$text"'"}}'
            ;;
    esac
    resp="$(curl -sS --max-time 5 -H 'Content-Type: application/json' \
        -d "$body" "$url" 2>&1)" || { say "NOTIFY 请求失败"; return 0; }
    case "$resp" in
        *'"errcode":0'*|*'"code":0'*|*'"code":200'*|*'"StatusCode":0'*|*'"status_code":0'*) ;;
        *) say "NOTIFY 返回异常: $resp" ;;
    esac
}

notify_email() {
    text="$1"
    if [ -z "${NOTIFY_EMAIL_USER:-}" ] || [ -z "${NOTIFY_EMAIL_PASS:-}" ]; then
        say "NOTIFY 邮件未配置完整（缺发件邮箱或授权码），跳过"
        return 0
    fi
    if MAIL_TO="$NOTIFY_EMAIL_TO" \
    MAIL_USER="${NOTIFY_EMAIL_USER:-}" \
    MAIL_PASS="${NOTIFY_EMAIL_PASS:-}" \
    MAIL_HOST="${NOTIFY_EMAIL_HOST:-smtp.163.com}" \
    MAIL_PORT="${NOTIFY_EMAIL_PORT:-465}" \
    MAIL_BODY="$text" \
    python3 - <<'PY'
import os, smtplib, ssl
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr

host = os.environ["MAIL_HOST"]
port = int(os.environ["MAIL_PORT"])
user = os.environ["MAIL_USER"]
password = os.environ["MAIL_PASS"]
to = [a.strip() for a in os.environ["MAIL_TO"].split(",") if a.strip()]
body = os.environ["MAIL_BODY"]

msg = MIMEText(body, "plain", "utf-8")
msg["Subject"] = Header("[C32] 施工日志后端告警", "utf-8")
msg["From"] = formataddr((str(Header("C32 施工日志后端", "utf-8")), user))
msg["To"] = ", ".join(to)

ctx = ssl.create_default_context()
with smtplib.SMTP_SSL(host, port, timeout=15, context=ctx) as s:
    s.login(user, password)
    s.sendmail(user, to, msg.as_string())
PY
    then
        say "NOTIFY 邮件已发送 -> $NOTIFY_EMAIL_TO"
    else
        say "NOTIFY 邮件发送失败"
    fi
}

notify() {
    text="$1"
    if [ -n "${NOTIFY_WEBHOOK:-}" ]; then notify_webhook "$text"; fi
    if [ -n "${NOTIFY_EMAIL_TO:-}" ]; then notify_email "$text"; fi
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
