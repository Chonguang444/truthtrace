#!/usr/bin/env bash
# TruthTrace 健康检查脚本 — 用于 cron 监控和告警
# 用法: bash health-check.sh [--alert]
# 加入 cron: */5 * * * * /opt/truthtrace/deploy/health-check.sh --alert
set -euo pipefail

ALERT=false
[ "${1:-}" = "--alert" ] && ALERT=true
DOMAIN="${DOMAIN:-truthtrace.app}"
TIMEOUT=10
FAILS=0

check_endpoint() {
    local url="$1" label="$2" expected="${3:-200}"
    local http_code
    http_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time "$TIMEOUT" "$url" 2>/dev/null || echo "000")
    if [ "$http_code" = "$expected" ]; then
        echo "  OK: $label ($url) -> $http_code"
    else
        echo "  FAIL: $label ($url) -> $http_code (expected $expected)"
        FAILS=$((FAILS + 1))
    fi
}

echo "=== TruthTrace Health Check $(date -Iseconds) ==="

# Backend API
check_endpoint "https://$DOMAIN/api/health" "API health"

# Frontend
check_endpoint "https://$DOMAIN/" "Frontend"

# Admin
check_endpoint "https://$DOMAIN/admin" "Admin page"

# API Docs
check_endpoint "https://$DOMAIN/api/docs" "API docs"

# Docker containers
echo "  -- Docker --"
total_containers=$(docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml ps -q 2>/dev/null | wc -l)
running=$(docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml ps --status running -q 2>/dev/null | wc -l)
echo "  Containers: $running/$total_containers running"
if [ "$total_containers" -gt 0 ] && [ "$running" -ne "$total_containers" ]; then
    FAILS=$((FAILS + 1))
fi

# Disk space
echo "  -- Disk --"
df -h / | tail -1 | awk '{print "  Usage: " $5 " (" $3 "/" $2 ")"}'
disk_pct=$(df / | tail -1 | awk '{print $5}' | tr -d '%')
if [ "$disk_pct" -gt 85 ]; then
    FAILS=$((FAILS + 1))
    echo "  WARN: Disk usage > 85%"
fi

# Memory
echo "  -- Memory --"
free -h | grep Mem | awk '{print "  Available: " $7 " / " $2}'

# Cert expiry
echo "  -- SSL --"
if [ -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
    expiry=$(openssl x509 -enddate -noout -in "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" | cut -d= -f2)
    echo "  Expires: $expiry"
else
    echo "  WARN: Certificate not found at expected path"
fi

echo ""
if [ "$FAILS" -eq 0 ]; then
    echo "RESULT: All checks passed"
    exit 0
else
    echo "RESULT: $FAILS check(s) failed"
    [ "$ALERT" = true ] && echo "ALERT: TruthTrace health check failed — $FAILS failures" >&2
    exit 1
fi
