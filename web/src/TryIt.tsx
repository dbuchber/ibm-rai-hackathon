// "Try it yourself": a QR code that opens the phone version (Mobile.tsx), with the invite code built in.
import qrcode from "qrcode-generator";
import { useMemo } from "react";

const PUBLIC_URL = import.meta.env.VITE_PUBLIC_URL ?? "https://rai-hackathon.bbger.at/";

// the invite typed into the chat is remembered, so the QR code can carry it to the phone
const INVITE_KEY = "graph-anchor.invite";
export const loadInvite = () => { try { return localStorage.getItem(INVITE_KEY) ?? ""; } catch { return ""; } };
export const saveInvite = (v: string) => { try { localStorage.setItem(INVITE_KEY, v); } catch { /* private window */ } };

/** The phone link. On localhost a phone cannot reach this machine, so point at the public deployment. */
export function mobileUrl(invite: string): string {
  const local = /^(localhost|127\.|0\.0\.0\.0|\[::1\])/.test(location.hostname);
  const base = local ? PUBLIC_URL : location.origin + location.pathname;
  return base + "?m" + (invite ? "&invite=" + encodeURIComponent(invite) : "");
}

/** Always dark on white, whatever the theme: phone scanners read that best. */
export function QrCode({ text, label }: { text: string; label: string }) {
  const { n, d } = useMemo(() => {
    const qr = qrcode(0, "M");
    qr.addData(text);
    qr.make();
    const n = qr.getModuleCount();
    let d = "";
    for (let r = 0; r < n; r++) for (let c = 0; c < n; c++) if (qr.isDark(r, c)) d += `M${c} ${r}h1v1h-1z`;
    return { n, d };
  }, [text]);
  return (
    <svg className="qr" viewBox={`-3 -3 ${n + 6} ${n + 6}`} shapeRendering="crispEdges" role="img" aria-label={label}>
      <rect x={-3} y={-3} width={n + 6} height={n + 6} fill="#fff" />
      <path d={d} fill="#000" />
    </svg>
  );
}

export default function TryIt({ invite, className = "" }: { invite?: string; className?: string }) {
  const url = mobileUrl((invite ?? loadInvite()).trim());
  return (
    <div className={"tryit " + className} onClick={(e) => e.stopPropagation()}>
      <div className="slide-eyebrow">Try it yourself</div>
      <a href={url} target="_blank" rel="noreferrer"><QrCode text={url} label="QR code for the phone version" /></a>
      <p>Scan with your phone. Ask your own question and check the sources.</p>
    </div>
  );
}
