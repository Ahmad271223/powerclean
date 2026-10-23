#!/usr/bin/env bash
# Sicherung von Stundenzettel Pro: MongoDB-Dump + Dateiordner als ein Archiv, Aufbewahrung 30 Tage.
# Aufruf: ./backup.sh /pfad/zum/sicherungsordner   (Umgebung: MONGO_URL, DB_NAME, DATA_DIR wie in der .env; optional DOCKER_MONGO=<Containername>)
set -euo pipefail
ZIEL="${1:-./sicherungen}"
MONGO_URL="${MONGO_URL:-mongodb://localhost:27017}"
DB_NAME="${DB_NAME:-stundenzettel_pro}"
DATA_DIR="${DATA_DIR:-./backend/daten}"
STEMPEL="$(date +%Y-%m-%d-%H%M)"
ARBEIT="$(mktemp -d)"
mkdir -p "$ZIEL"
if [ -n "${DOCKER_MONGO:-}" ]; then
  docker exec "$DOCKER_MONGO" mongodump --db "$DB_NAME" --archive --gzip > "$ARBEIT/db.archive"
else
  mongodump --uri "$MONGO_URL" --db "$DB_NAME" --archive="$ARBEIT/db.archive" --gzip
fi
if [ -d "$DATA_DIR/dateien" ]; then
  tar -czf "$ARBEIT/dateien.tar.gz" -C "$DATA_DIR" dateien
fi
tar -czf "$ZIEL/stundenzettel-pro-$STEMPEL.tar.gz" -C "$ARBEIT" .
rm -rf "$ARBEIT"
find "$ZIEL" -name 'stundenzettel-pro-*.tar.gz' -mtime +30 -delete
echo "Sicherung: $ZIEL/stundenzettel-pro-$STEMPEL.tar.gz"
