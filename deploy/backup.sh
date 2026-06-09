#!/bin/bash
# TruthTrace 数据库备份脚本
# crontab: 0 4 * * * /opt/truthtrace/deploy/backup.sh

BACKUP_DIR="/opt/truthtrace/deploy/backup"
RETENTION_DAYS=30
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

# PostgreSQL 备份
docker compose -f /opt/truthtrace/docker-compose.yml \
    -f /opt/truthtrace/deploy/docker-compose.prod.yml \
    exec -T postgres pg_dump -U truthtrace truthtrace \
    | gzip > "$BACKUP_DIR/truthtrace_$TIMESTAMP.sql.gz"

echo "Backup created: truthtrace_$TIMESTAMP.sql.gz ($(du -h "$BACKUP_DIR/truthtrace_$TIMESTAMP.sql.gz" | cut -f1))"

# 清理旧备份
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +$RETENTION_DAYS -delete
echo "Cleaned backups older than $RETENTION_DAYS days"
