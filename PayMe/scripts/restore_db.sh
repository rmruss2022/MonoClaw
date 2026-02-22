#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="$ROOT_DIR/backups"

INPUT_FILE="${1:-}"
if [[ -z "$INPUT_FILE" ]]; then
  if [[ -f "$BACKUP_DIR/latest.txt" ]]; then
    INPUT_FILE="$(cat "$BACKUP_DIR/latest.txt")"
  else
    echo "Usage: scripts/restore_db.sh <backup.sql>"
    exit 1
  fi
fi

if [[ ! -f "$INPUT_FILE" ]]; then
  echo "Backup file not found: $INPUT_FILE"
  exit 1
fi

docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T db psql -U payme -d postgres -c "DROP DATABASE IF EXISTS payme;"
docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T db psql -U payme -d postgres -c "CREATE DATABASE payme;"
docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T db psql -U payme payme < "$INPUT_FILE"

echo "Restored backup: $INPUT_FILE"
