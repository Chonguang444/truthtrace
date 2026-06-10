#!/usr/bin/env bash
# TruthTrace 生产环境一键部署脚本
# 用法: sudo bash deploy/setup.sh [--staging] [--domain=truthtrace.app]
set -euo pipefail

STAGING=false
DOMAIN="truthtrace.app"
EMAIL="admin@truthtrace.app"

for arg in "$@"; do
    case $arg in
        --staging) STAGING=true ;;
        --domain=*) DOMAIN="${arg#*=}" ;;
        *) echo "Unknown arg: $arg"; exit 1 ;;
    esac
done

echo "=== TruthTrace Production Setup ==="
echo "Domain: $DOMAIN | Staging: $STAGING"
echo ""

# ---- 1. System Dependencies ----
echo "[1/7] Installing system packages..."
apt-get update -qq
apt-get install -y -qq nginx certbot python3-certbot-nginx docker.io docker-compose-plugin curl jq > /dev/null 2>&1

# ---- 2. Firewall ----
echo "[2/7] Configuring firewall..."
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 22/tcp
ufw --force enable

# ---- 3. SSL Certificate ----
echo "[3/7] Obtaining SSL certificate..."
mkdir -p /var/www/certbot
if [ "$STAGING" = true ]; then
    certbot certonly --webroot -w /var/www/certbot \
        -d "$DOMAIN" -d "www.$DOMAIN" \
        --email "$EMAIL" --agree-tos --no-eff-email --staging
else
    certbot certonly --webroot -w /var/www/certbot \
        -d "$DOMAIN" -d "www.$DOMAIN" \
        --email "$EMAIL" --agree-tos --no-eff-email
fi

# ---- 4. Nginx ----
echo "[4/7] Deploying Nginx config..."
cp deploy/nginx-prod.conf /etc/nginx/sites-available/truthtrace
# Replace domain placeholder
sed -i "s/truthtrace\.app/$DOMAIN/g" /etc/nginx/sites-available/truthtrace

ln -sf /etc/nginx/sites-available/truthtrace /etc/nginx/sites-enabled/truthtrace
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

# ---- 5. Environment Variables ----
echo "[5/7] Setting up environment..."
if [ ! -f .env ]; then
    JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")
    DB_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    cat > .env << ENVEOF
# TruthTrace Production Environment
JWT_SECRET_KEY=${JWT_SECRET}
DATABASE_URL=postgresql+asyncpg://truthtrace:${DB_PASSWORD}@postgres:5432/truthtrace
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2
CORS_ORIGINS=https://${DOMAIN}
DEBUG=false
LOG_LEVEL=INFO
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SENTRY_DSN=
ANTHROPIC_API_KEY=
ENVEOF
    echo "  .env created with random secrets"
else
    echo "  .env already exists, skipping"
fi

# ---- 6. Docker Compose ----
echo "[6/7] Starting Docker containers..."
docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml build --pull
docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml up -d --wait

# ---- 7. Verification ----
echo "[7/7] Verifying deployment..."
sleep 5
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" https://${DOMAIN}/api/health || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
    echo "  OK: Health check passed (HTTP $HTTP_CODE)"
else
    echo "  WARN: Health check returned HTTP $HTTP_CODE — check logs"
fi

echo ""
echo "=== Setup Complete ==="
echo "  Frontend:  https://${DOMAIN}"
echo "  API Docs:  https://${DOMAIN}/api/docs"
echo "  Admin:     https://${DOMAIN}/admin"
echo ""
echo "=== Post-Setup Checklist ==="
echo "  [ ] Configure SMTP in .env (for email notifications)"
echo "  [ ] Set ANTHROPIC_API_KEY in .env (for LLM analysis)"
echo "  [ ] Register admin user: docker compose exec backend python -c \"from app.seed_data import create_admin; import asyncio; asyncio.run(create_admin())\""
echo "  [ ] Enable certbot auto-renewal: systemctl enable certbot.timer"
echo "  [ ] Setup monitoring: copy deploy/health-check.sh to /etc/cron.d/"
