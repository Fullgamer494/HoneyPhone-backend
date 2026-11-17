#!/usr/bin/env bash
set -euo pipefail
base="${API_BASE_URL:-http://127.0.0.1:8000}"
curl --fail --show-error --silent --max-time 5 "$base/healthz"
echo
curl --fail --show-error --silent --max-time 5 "$base/api/v1/network-checks?limit=20&source=DEMO"
echo
echo 'Lecturas completadas. Para POST usa una fixture sintética y comprueba PostgreSQL.'
