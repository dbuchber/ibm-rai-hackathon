# Orchestrator session summary (IBM RAI Hackathon, 24.10.2026)

Handover from the orchestrator session (Mac, VS Code). Written at about 12:55 server time. Feature freeze 15:30, pitch 16:00 (3 minutes). Submission language and UI are English; communication with the user is German, and questions go to the user via the AskUserQuestion tool.

## What we are building

**Graph Anchor**: a human-curated enterprise knowledge graph as the grounding anchor for LLM answers. It applies the user's bachelor thesis (hybrid KG traversal against hallucinations; proposal in `~/Desktop/tmp.nosync/vscode/BA_Thesis_Proposal/`, thesis code on Hetzner in `/data/projects/ba/`) to a simplified enterprise digital twin:
- Data: iMAKS (Zenodo 20075430: plant, sensors, SOPs, datasheets, rules) plus a fictional company, Kelvara Packaging GmbH.
- The LLM sets a traversal strategy per question (allowed predicates), evaluates **every** step, and answers with an **evidence subgraph** (the graph that led to the result).
- Curation: the LLM proposes edges, nodes and predicates; an analyst approves; users can add their own. The engine traverses only `urn:g:approved`.
- **Canaries** against automation bias: real in curation, a click mock in chat. Approving a canary raises an alarm, reverts approvals and notifies the supervisor (mock).
- The pitch is a click prototype over precomputed runs. Live mode also exists.
- Roadmap screen: local models of different sizes with intelligent routing, Granite/watsonx, guardrails (Granite Guardian), chat feedback into curation, forward navigation to the source system, RBAC on vector level (payload) and KG node level.

Authoritative docs (in the repo):
- Spec: `docs/superpowers/specs/2026-10-24-graph-anchor-design.md` (incl. contracts C1–C5, canaries, chunks one level down)
- Plan and streams: `docs/superpowers/plans/2026-10-24-graph-anchor.md`
- Submission README: `README.md`

## Where things are

| What | Where |
|---|---|
| Main repo (truth, deploy) | Hetzner `hetzner-wikidata:/data/projects/ibm-rai-hackathon` (branch `main`, `receive.denyCurrentBranch updateInstead`) |
| Mac clone | `~/Desktop/tmp.nosync/vscode/ibm-rai-hackathon`, remote `hetzner`. Push with `GIT_SSH_COMMAND="ssh -o ClearAllForwardings=yes" git push hetzner main` (the ssh config has port forwards that collide otherwise; use `-o ClearAllForwardings=yes` for every ssh) |
| Stream worktrees | `/data/projects/ibm-rai-hackathon-wt/{a-kg,b-engine,c-ui,d-api}`, branches `stream/<x>`. Kickoff prompts in `../_prompts/` |
| Live | https://rai-hackathon.bbger.at (container `rai-hackathon`, `127.0.0.1:17080`, Caddy route in `/data/projects/caddy/Caddyfile`, Cloudflare DNS is set) |
| Rebuild | `cd /data/projects/ibm-rai-hackathon && docker compose -f deploy/compose.yml up -d --build` |
| LLM | BA LiteLLM gateway (uni host, reverse-forwarded to Hetzner `localhost:14000/v1`), key in `.env` (gitignored). Model `openai/mistral-large-4-openrouter` (gemma returns 404). Stream B added this model to `ba_infra/docker/litellm/config.yaml` on the uni host; the user decided to keep it, and it is committed there as `1ebea1a`, **not pushed**. |
| Dev servers (stream C) | static `ssh -L 5180:localhost:5180 hetzner-wikidata`, API mode `-L 5181:localhost:5181` |

## Remote-control sessions (tmux on Hetzner, permission mode auto)

| Stream | tmux | claude.ai/code |
|---|---|---|
| A KG | `rai-A-kg` | session_01XJmbq1GpqSCG53VZtX6JGG |
| B Engine | `rai-B-engine` | session_01RWokucMzP1UkcRdBknxMHS |
| C UI | `rai-C-ui` | session_01YJ1cno7THn3z2wSGAeCqdj |
| D API/deploy | `rai-D-api` | session_013tLDjBr7eYEV7dqa1GgkYx |

Orchestration technique (from the Mac):
- **Read without interrupting:** `ssh … 'tmux capture-pane -p -t <name> -S -80'`, plus `git -C <wt> log --oneline main..HEAD`.
- **Send a task:** `tmux send-keys -t <name> -l "<text>"; sleep 0.3; tmux send-keys -t <name> Enter`. Never send `Escape` (it interrupts running work).
- ⚠ The text at an idle session's input prompt is usually a **Claude Code suggestion**, not a user message. Do not take it as an instruction.
- ⚠ If a session sits in a permission dialog, typed text goes into the dialog. Check the pane first.
- Merge flow: commit on `stream/<x>` → in the main repo `git merge --no-edit stream/<x>` → `uv run pytest -q` → rebuild → tell the sessions `git merge main`.
- Only the orchestrator changes `contracts/` and `ontology.ttl`: fixtures via `uv run python -m scripts.make_fixtures`, schemas via `uv run python -m scripts.export_schema`.

## Status at about 12:55

On `main`: A, B, C and D merged, 36 tests green. Live: 3 real runs (`demo-po1003` main run, `demo-contradiction`, `demo-maintenance`) and `mock-canary-chat`. Also live: curation with 3 proposal kinds, UI canaries, chunks hidden in an inspector, README.

Open tasks, dispatched at about 12:52; each session reports when committed:
- **D:** canary logic on the server (streak 4 / avg < 3 s, alert, revert, audit) + `GET /api/audit`. Today `flag` is treated as `reject`.
- **B:** pitch script in `docs/pitch.md` (3 minutes, click path, seconds per screen, honest about mocks, backup plan).
- **A:** Playwright QA of the live site → `docs/qa-live.md` (prioritised, no code changes).
- **C:** offline pitch bundle `web/pitch-offline.zip` + `docs/pitch-offline.md`, then work through A's QA list.

Then: merge everything, rebuild, ask the user to choose the main pitch run, copy the offline bundle to the Mac (fallback without Wi-Fi), feature freeze at 15:30.

## Decisions made (do not reopen)

- UI first; mocks are always visibly labelled.
- No tracing or logging. No parallel sub-agents.
- Granite only on the roadmap. Local models with routing: pitch/roadmap only.
- Vector-RAG contrast: real baseline, top-k = 3. Illustrative examples are labelled.
- Contradiction `SOP-002-s6 contradicts DS-ELEC-3300-s1` approved (coordinator as analyst). `SOP-001 vs DS-THERM-2200` stays `proposed` as the curation example.
- Seed search prefers IDs named verbatim (contracts fix `9080708`).
- Chat satellites (chunks unfolding around a node) dropped in favour of the inspector.
