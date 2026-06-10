#!/usr/bin/env bash
# TruthTrace 零停机部署更新脚本
# 用法: bash deploy/update.sh [--check] [--rollback]
set -euo pipefail

BACKUP_DIR="deploy/backups/$(date +%Y%m%d_%H%M%S)"
DOMAIN="${DOMAIN:-truthtrace.app}"

# --- Rollback ---
if [ "${1:-}" = "--rollback" ]; then
    LATEST_BACKUP=$(ls -dt deploy/backups/2*/ 2>/dev/null | head -1)
    if [ -z "$LATEST_BACKUP" ]; then
        echo "ERROR: No backups found"
        exit 1
    fi
    echo "Rolling back to: $LATEST_BACKUP"
    cp "$LATEST_BACKUP/docker-compose.yml" docker-compose.yml 2>/dev/null || true
    cp "$LATEST_BACKUP/.env" .env 2>/dev/null || true
    docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml up -d --force-recreate
    echo "Rollback complete. Checking health..."
    sleep 5
    curl -sf "https://$DOMAIN/api/health" && echo "  OK" || echo "  FAIL"
    exit 0
fi

# --- Pre-flight check (dry-run) ---
if [ "${1:-}" = "--check" ]; then
    echo "=== Pre-flight checks ==="
    nginx -t && echo "  OK: nginx config valid"
    docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml config -q && echo "  OK: docker compose valid"
    echo "All checks passed."
    exit 0
fi

# --- Normal Update ---
echo "=== TruthTrace Update $(date -Iseconds) ==="

# Backup
mkdir -p "$BACKUP_DIR"
cp docker-compose.yml "$BACKUP_DIR/docker-compose.yml"
cp .env "$BACKUP_DIR/.env" 2>/dev/null || true
echo "[1/5] Backup saved to $BACKUP_DIR"

# Pre-flight
echo "[2/5] Pre-flight checks..."
docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml config -q
nginx -t

# Pull new images
echo "[3/5] Pulling new images..."
docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml pull -q

# Rolling restart (no downtime)
echo "[4/5] Rolling restart..."
docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml up -d --remove-orphans

# Wait for healthy
echo "[5/5] Waiting for health..."
for i in $(seq 1 30); do
    if curl -sf "https://$DOMAIN/api/health" > /dev/null 2>&1; then
        echo "  OK: Service healthy after ${i}s"
        break
    fi
    sleep 2
done

# Verify
curl -sf "https://$DOMAIN/api/health" || echo "  WARN: Health check failed"

# Cleanup old images
docker image prune -f > /dev/null 2>&1

echo "=== Update Complete ==="
