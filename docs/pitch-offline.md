# Offline pitch bundle

The pitch must not depend on venue Wi-Fi. `web/pitch-offline.zip` is a static build (`VITE_DATA=static`)
with the real graph (`data/graph/kg.trig`), the 3 real runs, the chat canary run (`mock`) and the real
curation proposals. It loads nothing from the network.

## Build (on the server or any machine with the repo)

```bash
cd web
npm ci            # once
npm run pitch     # -> web/pitch-offline.zip (gitignored)
```

`npm run pitch` exports the graph and ontology from `kg.trig` (needs `uv`), copies `runs/*.jsonl` and
`data/proposals.json`, builds, zips, and fails if the bundle references any external host.

Copy to the pitch laptop: `scp hetzner-wikidata:/data/projects/ibm-rai-hackathon/web/pitch-offline.zip .`

## Run on the pitch laptop (no network)

```bash
python3 -m zipfile -e pitch-offline.zip .     # or: unzip pitch-offline.zip
cd pitch-offline
python3 -m http.server 8000
```

Open http://localhost:8000. The top right says **Offline replay**.

## What works offline

| Screen | Offline |
|---|---|
| Twin | real graph (235 entities, documents; chunks open in the inspector on click) |
| Ask | the 3 real runs plus the chat canary run (labelled Mock run); free-text questions are off |
| Contrast | real vector-RAG baseline per run |
| Curate | real proposals; approve/reject/flag, add, curation canary and audit log run in the browser (labelled Mock · in memory) |
| Roadmap | static |

Reload the page to reset curation and the canary state.

## Keys

`1`–`5` switch screens, `Space` play/pause, `←` `→` step, `Esc` closes panels.

## Pitch flow (canary moment)

Curate: approve 4 proposals quickly, then approve the planted one (e.g. "ST01_FILLING supplied by
Velora Foods AG") → alert, the 4 approvals go back to review, audit log.
