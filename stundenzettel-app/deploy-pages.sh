#!/usr/bin/env bash
# Baut die App und veröffentlicht sie auf GitHub Pages:
#   https://ahmad271223.github.io/stundenzettel/
# Voraussetzung: `gh auth login` (GitHub CLI) auf diesem Rechner.
set -e
cd "$(dirname "$0")"
npm run build
TMP="$(mktemp -d)"
cp -r dist/. "$TMP/"
touch "$TMP/.nojekyll"
cd "$TMP"
git init -q -b main
git add -A
git -c user.name="Ahmad" -c user.email="ahmad@powercleanservice.de" commit -q -m "Stundenzettel App – Update $(date +%Y-%m-%d)"
git push -f "https://github.com/Ahmad271223/stundenzettel.git" main
echo "Veröffentlicht: https://ahmad271223.github.io/stundenzettel/ (1–2 Minuten bis es live ist)"
