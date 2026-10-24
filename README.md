# Graph Anchor

A human-curated enterprise knowledge graph as the grounding anchor for LLM answers.
IBM Responsible AI Hackathon (WU & UNIVIE), 24 October 2026.

- Design: [docs/superpowers/specs/2026-10-24-graph-anchor-design.md](docs/superpowers/specs/2026-10-24-graph-anchor-design.md)
- Plan and work streams: [docs/superpowers/plans/2026-10-24-graph-anchor.md](docs/superpowers/plans/2026-10-24-graph-anchor.md)
- Interfaces: [contracts/](contracts/). Do not edit them inside a stream.

```bash
uv sync
uv run pytest -q
```

Data: iMAKS (Zenodo 20075430) plus a fictional company (Kelvara Packaging GmbH). All company data is synthetic.
