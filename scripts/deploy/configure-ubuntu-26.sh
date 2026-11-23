#!/usr/bin/env bash
set -Eeuo pipefail

# Configure a newly created Ubuntu 26.04 EC2 instance to run HoneyPhone API,
# PostgreSQL, and Caddy on one host. Run from the HoneyPhone-backend root.
# Before running: point DOMAIN to the instance's public IPv4; configure the EC2
# security group for TCP 22 from your admin CIDR, TCP 80 from anywhere (ACME),
# and TCP 443 only from TRUSTED_CIDR. Never open 5432 to the internet.

fail() { printf 'error: %s\n' "$*" >&2; exit 1; }
[[ ${EUID} -eq 0 ]] || fail "run with sudo: sudo ./scripts/deploy/configure-ubuntu-26.sh <domain> <trusted-ipv4-cidr>"
[[ $# -eq 2 ]] || fail "usage: sudo ./scripts/deploy/configure-ubuntu-26.sh <domain> <trusted-ipv4-cidr>"
DOMAIN=${1,,}
TRUSTED_CIDR=$2
[[ -f pyproject.toml && -d src/honeyphone ]] || fail "run this script from the HoneyPhone-backend repository root"
. /etc/os-release
[[ ${ID:-} == ubuntu && ${VERSION_ID:-} == 26.04 ]] || fail "this script targets Ubuntu 26.04 LTS"
[[ $DOMAIN =~ ^[a-z0-9]([a-z0-9.-]*[a-z0-9])?$ ]] || fail "invalid DNS name"
[[ $TRUSTED_CIDR =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}/([0-9]|[12][0-9]|3[0-2])$ ]] || fail "use a trusted IPv4 CIDR, for example 203.0.113.8/32"
[[ $TRUSTED_CIDR != 0.0.0.0/0 ]] || fail "provide a restricted trusted IPv4 CIDR for the API"

APP_DIR=/opt/honeyphone
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y docker.io docker-compose-v2 ufw openssl
systemctl enable --now docker
install -d -m 0750 "$APP_DIR"
if [[ -f "$APP_DIR/.env" ]]; then
    DB_PASSWORD=$(sed -n 's/^DB_PASSWORD=//p' "$APP_DIR/.env" | head -n1)
    AUTH_SECRET_KEY=$(sed -n 's/^AUTH_SECRET_KEY=//p' "$APP_DIR/.env" | head -n1)
    GOOGLE_CLIENT_IDS=$(sed -n 's/^GOOGLE_CLIENT_IDS=//p' "$APP_DIR/.env" | head -n1)
else
    DB_PASSWORD=$(openssl rand -hex 32)
    AUTH_SECRET_KEY=$(openssl rand -hex 32)
    GOOGLE_CLIENT_IDS=${GOOGLE_CLIENT_IDS:-}
fi
[[ -n ${AUTH_SECRET_KEY:-} ]] || AUTH_SECRET_KEY=$(openssl rand -hex 32)
[[ ${#DB_PASSWORD} -ge 24 && $DB_PASSWORD =~ ^[a-f0-9]+$ ]] || fail "invalid existing DB_PASSWORD in $APP_DIR/.env"
[[ ${#AUTH_SECRET_KEY} -ge 32 && $AUTH_SECRET_KEY =~ ^[a-f0-9]+$ ]] || fail "invalid existing AUTH_SECRET_KEY in $APP_DIR/.env"

cat > "$APP_DIR/Dockerfile" <<'DOCKERFILE'
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .
EXPOSE 8000
CMD ["sh", "-c", "alembic -c /app/alembic.ini upgrade head && uvicorn honeyphone.main:app --app-dir /app/src --host 0.0.0.0 --port 8000"]
DOCKERFILE

# Alembic config and migration files are needed inside the image.
install -m 0644 alembic.ini "$APP_DIR/alembic.ini"
rm -rf "$APP_DIR/src" "$APP_DIR/alembic"
cp -a src alembic "$APP_DIR/"
install -m 0644 pyproject.toml "$APP_DIR/pyproject.toml"

cat > "$APP_DIR/Caddyfile" <<CADDY
$DOMAIN {
    encode zstd gzip
    reverse_proxy api:8000
}
CADDY

cat > "$APP_DIR/compose.yaml" <<'COMPOSE'
services:
  db:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: honeyphone
      POSTGRES_USER: honeyphone
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      TZ: UTC
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U honeyphone -d honeyphone"]
      interval: 5s
      timeout: 3s
      retries: 12
    networks: [private]
  api:
    build: .
    restart: unless-stopped
    environment:
      APP_ENV: production
      DATABASE_URL: postgresql+psycopg://honeyphone:${DB_PASSWORD}@db:5432/honeyphone
      MAX_BODY_BYTES: 65536
      AUTH_SECRET_KEY: ${AUTH_SECRET_KEY}
      GOOGLE_CLIENT_IDS: ${GOOGLE_CLIENT_IDS}
    depends_on:
      db:
        condition: service_healthy
    networks: [private, edge]
  caddy:
    image: caddy:2-alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
      - "443:443/udp"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
    depends_on: [api]
    networks: [edge]
volumes:
  postgres_data:
  caddy_data:
  caddy_config:
networks:
  private:
    internal: true
  edge:
COMPOSE

umask 077
printf 'DB_PASSWORD=%s\n' "$DB_PASSWORD" > "$APP_DIR/.env"
printf 'AUTH_SECRET_KEY=%s\n' "$AUTH_SECRET_KEY" >> "$APP_DIR/.env"
printf 'GOOGLE_CLIENT_IDS=%s\n' "$GOOGLE_CLIENT_IDS" >> "$APP_DIR/.env"
unset DB_PASSWORD AUTH_SECRET_KEY GOOGLE_CLIENT_IDS
chmod 600 "$APP_DIR/.env"

# Host firewall: expose ACME HTTP validation and HTTPS only to the supplied CIDR.
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow from "$TRUSTED_CIDR" to any port 22 proto tcp
ufw allow 80/tcp
ufw allow from "$TRUSTED_CIDR" to any port 443 proto tcp
ufw allow from "$TRUSTED_CIDR" to any port 443 proto udp
ufw --force enable

cd "$APP_DIR"
docker compose up -d --build
printf '\nConfigured HoneyPhone at https://%s\n' "$DOMAIN"
printf 'API health: https://%s/healthz\n' "$DOMAIN"
printf 'PostgreSQL has no published host port. API ingress is restricted to %s.\n' "$TRUSTED_CIDR"
printf 'Set the matching inbound rules in the EC2 security group; keep port 5432 closed.\n'
printf 'Back up /opt/honeyphone postgres_data before updates.\n'
