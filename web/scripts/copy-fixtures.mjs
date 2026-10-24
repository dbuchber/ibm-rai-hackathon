// Copies data for VITE_DATA=static into public/data. Prefers real outputs, falls back to fixtures.
import { copyFileSync, existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";

const root = new URL("../../", import.meta.url).pathname;
const pub = new URL("../public/data/", import.meta.url).pathname;
mkdirSync(pub + "runs", { recursive: true });

// The real graph is exported by `npm run graph` (scripts/export_graph.py); fixtures only without kg.trig.
if (!existsSync(root + "data/graph/kg.trig")) copyFileSync(root + "contracts/fixtures/graph_export.json", pub + "graph_export.json");
const proposals = existsSync(root + "data/proposals.json") ? "data/proposals.json" : "contracts/fixtures/proposals.json";
copyFileSync(root + proposals, pub + "proposals.json");

const runFiles = existsSync(root + "runs") ? readdirSync(root + "runs").filter((f) => f.endsWith(".jsonl")) : [];
const sources = runFiles.length ? runFiles.map((f) => root + "runs/" + f) : [root + "contracts/fixtures/run_demo.jsonl"];
const index = [];
for (const src of sources) {
  const lines = readFileSync(src, "utf8").split("\n").filter(Boolean);
  const first = lines.map((l) => JSON.parse(l)).find((e) => e.type === "run.started"); // line 0 is its beat
  copyFileSync(src, pub + "runs/" + first.run_id + ".jsonl");
  index.push({ run_id: first.run_id, question: first.payload.question, mock: !!first.payload.mock });
}
writeFileSync(pub + "runs/index.json", JSON.stringify(index, null, 2));
console.log("graph, proposals (" + proposals + "), runs:", index.map((r) => r.run_id).join(", "));
