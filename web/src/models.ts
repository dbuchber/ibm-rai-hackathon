// Display names for model ids, and run timing. Unknown ids fall back to their last path segment.
import type { Event } from "./contracts";

const KNOWN: Record<string, { name: string; via: string }> = {
  "openai/ibm/granite-4-h-small": { name: "Granite 4 H Small", via: "IBM ICA" },
  "openai/mistral-large-4-openrouter": { name: "Mistral Large 4", via: "OpenRouter" },
  "openai/watsonx/mistralai/mistral-medium-2505": { name: "Mistral Medium", via: "IBM ICA" },
  "openai/meta-llama/llama-3-3-70b-instruct": { name: "Llama 3.3 70B", via: "IBM ICA" },
  "openai/gemma-4-31b-it-openrouter": { name: "Gemma 4 31B", via: "OpenRouter" },
  "openrouter/google/gemma-4-31b-it": { name: "Gemma 4 31B", via: "OpenRouter" },
};

export function modelInfo(id: string) {
  return KNOWN[id] ?? { name: id.split("/").pop() ?? id, via: "" };
}

/** Wall-clock time of a run from its first to its last event. */
export function runSeconds(events: Event[]): number | null {
  if (events.length < 2) return null;
  const s = (Date.parse(events[events.length - 1].ts) - Date.parse(events[0].ts)) / 1000;
  return Number.isFinite(s) && s > 0 ? s : null;
}

export function fmtDuration(s: number | null) {
  if (s == null) return "";
  if (s < 90) return `${Math.round(s)} s`;
  return `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")} min`;
}
