// Mirror of contracts/ids.py for proposals made in the browser (static mode).
// Pure-JS SHA-1, because crypto.subtle is missing on plain-http origins.

export const KG = "https://rai-hackathon.bbger.at/kg/";
export const ONT = "https://rai-hackathon.bbger.at/ont#";

export const nodeIri = (cls: string, localId: string) => `${KG}${cls.toLowerCase()}/${localId}`;
export const predIri = (name: string) => `${ONT}${name}`;

function sha1(msg: string): string {
  const bytes = new TextEncoder().encode(msg);
  const len = bytes.length;
  const words = new Uint32Array((((len + 8) >> 6) + 1) * 16);
  for (let i = 0; i < len; i++) words[i >> 2] |= bytes[i] << (24 - (i % 4) * 8);
  words[len >> 2] |= 0x80 << (24 - (len % 4) * 8);
  words[words.length - 1] = len * 8;
  let [a, b, c, d, e] = [0x67452301, 0xefcdab89, 0x98badcfe, 0x10325476, 0xc3d2e1f0];
  const w = new Uint32Array(80);
  const rol = (x: number, n: number) => (x << n) | (x >>> (32 - n));
  for (let i = 0; i < words.length; i += 16) {
    for (let t = 0; t < 80; t++) w[t] = t < 16 ? words[i + t] : rol(w[t - 3] ^ w[t - 8] ^ w[t - 14] ^ w[t - 16], 1);
    let [A, B, C, D, E] = [a, b, c, d, e];
    for (let t = 0; t < 80; t++) {
      const f = t < 20 ? (B & C) | (~B & D) : t < 40 ? B ^ C ^ D : t < 60 ? (B & C) | (B & D) | (C & D) : B ^ C ^ D;
      const k = t < 20 ? 0x5a827999 : t < 40 ? 0x6ed9eba1 : t < 60 ? 0x8f1bbcdc : 0xca62c1d6;
      const tmp = (rol(A, 5) + f + E + k + w[t]) >>> 0;
      [E, D, C, B, A] = [D, C, rol(B, 30) >>> 0, A, tmp];
    }
    [a, b, c, d, e] = [(a + A) >>> 0, (b + B) >>> 0, (c + C) >>> 0, (d + D) >>> 0, (e + E) >>> 0];
  }
  return [a, b, c, d, e].map((x) => x.toString(16).padStart(8, "0")).join("");
}

export const edgeId = (s: string, p: string, o: string) => sha1(`${s}|${p}|${o}`).slice(0, 12);

export function proposalId(kind: "edge" | "node" | "predicate", arg: { triple?: [string, string, string]; iri?: string }) {
  if (kind === "edge") return edgeId(...arg.triple!);
  return sha1(`${kind}|${arg.iri}`).slice(0, 12);
}
