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
  const first = JSON.parse(lines[0]);
  copyFileSync(src, pub + "runs/" + first.run_id + ".jsonl");
  index.push({ run_id: first.run_id, question: first.payload.question, mock: !!first.payload.mock });
}
// pitch order: runs/questions.yaml first, then the rest; mock runs last
const qy = existsSync(root + "runs/questions.yaml") ? readFileSync(root + "runs/questions.yaml", "utf8") : "";
const order = [...qy.matchAll(/^- id: *(\S+)/gm)].map((m) => m[1]);
const rank = (r) => (r.mock ? 1000 : 0) + (order.includes(r.run_id) ? order.indexOf(r.run_id) : 500);
index.sort((a, b) => rank(a) - rank(b));
writeFileSync(pub + "runs/index.json", JSON.stringify(index, null, 2));
console.log("graph, proposals (" + proposals + "), runs:", index.map((r) => r.run_id).join(", "));
