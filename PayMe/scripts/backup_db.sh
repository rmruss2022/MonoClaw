#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="$ROOT_DIR/backups"
mkdir -p "$BACKUP_DIR"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
FILE="$BACKUP_DIR/payme-${STAMP}.sql"

docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T db pg_dump -U payme payme > "$FILE"
echo "$FILE" > "$BACKUP_DIR/latest.txt"
shasum -a 256 "$FILE" > "$FILE.sha256"

echo "Created backup: $FILE"
