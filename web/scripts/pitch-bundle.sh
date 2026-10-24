#!/usr/bin/env bash
# Builds web/pitch-offline.zip: static build (VITE_DATA=static) with the real graph, runs and proposals.
# Run from web/: npm run pitch
set -euo pipefail
cd "$(dirname "$0")/.."
npm run graph
npm run data
rm -rf dist pitch-offline pitch-offline.zip
VITE_DATA=static npm run build
cp -r dist pitch-offline
cat > pitch-offline/START.txt <<'TXT'
Graph Anchor, offline pitch build.
  cd pitch-offline && python3 -m http.server 8000
  open http://localhost:8000
No network needed. Data lives in data/ (graph, runs, proposals).
TXT
python3 -m zipfile -c pitch-offline.zip pitch-offline
rm -rf pitch-offline
# offline check: the bundle must not load anything from another host
if python3 -c 'import sys,zipfile; z=zipfile.ZipFile("pitch-offline.zip"); sys.stdout.write("".join(z.read(n).decode("utf8","ignore") for n in z.namelist() if n.endswith((".html",".js",".css"))))' \
   | grep -Eo '(src|href)="https?://[^"]+"|url\(https?://[^)]+\)|@import' ; then
  echo "external reference found" >&2; exit 1
fi
ls -lh pitch-offline.zip
