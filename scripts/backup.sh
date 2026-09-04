#!/usr/bin/env bash
# ============================================================
# construction-backend 每日备份脚本
#   - mysqldump 数据库 → BACKUP_ROOT/db/
#   - tar.gz 打包 uploads 上传目录 → BACKUP_ROOT/uploads/
#   - 只保留最近 KEEP_DAYS 天的备份
#
# 用法:
#   先按需修改下方变量，然后手动试跑一次：
#     bash scripts/backup.sh
#   确认输出正常后加入 crontab（建议凌晨低峰执行）：
#     0 2 * * * cd /srv/construction-backend && bash scripts/backup.sh >> logs/backup.log 2>&1
# ============================================================

set -euo pipefail

# ---------- 按环境修改 ----------
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB_NAME="construction"
DB_USER="construction_user"
DB_PASS="${DB_PASS:-construction123}"          # 推荐用环境变量传入，勿写死在 crontab
UPLOADS_DIR="${UPLOADS_DIR:-$APP_DIR/uploads}" # 与 config.py 的 UPLOAD_FOLDER 保持一致
BACKUP_ROOT="${BACKUP_ROOT:-/var/backups/construction}"
KEEP_DAYS=7
MYSQL_BIN="$(command -v mysqldump || echo /usr/bin/mysqldump)"
# ---------------------------------

STAMP="$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_ROOT/db" "$BACKUP_ROOT/uploads"

echo "[$(date '+%F %T')] 备份开始 → $BACKUP_ROOT"

# 1) 数据库（--single-transaction 不锁表）
DB_FILE="$BACKUP_ROOT/db/${DB_NAME}_${STAMP}.sql.gz"
MYSQL_PWD="$DB_PASS" "$MYSQL_BIN" --single-transaction --quick \
    -u "$DB_USER" "$DB_NAME" | gzip > "$DB_FILE"
echo "  数据库: $DB_FILE ($(du -h "$DB_FILE" | cut -f1))"

# 2) 上传文件目录
UPLOADS_FILE="$BACKUP_ROOT/uploads/uploads_${STAMP}.tar.gz"
if [ -d "$UPLOADS_DIR" ]; then
    tar -czf "$UPLOADS_FILE" -C "$(dirname "$UPLOADS_DIR")" "$(basename "$UPLOADS_DIR")"
    echo "  上传目录: $UPLOADS_FILE ($(du -h "$UPLOADS_FILE" | cut -f1))"
else
    echo "  [警告] 上传目录不存在: $UPLOADS_DIR，跳过"
fi

# 3) 轮转：删除 KEEP_DAYS 天前的备份
find "$BACKUP_ROOT/db"      -name "${DB_NAME}_*.sql.gz" -mtime +"$KEEP_DAYS" -delete
find "$BACKUP_ROOT/uploads" -name "uploads_*.tar.gz"    -mtime +"$KEEP_DAYS" -delete

echo "[$(date '+%F %T')] 备份完成（保留最近 ${KEEP_DAYS} 天）"
