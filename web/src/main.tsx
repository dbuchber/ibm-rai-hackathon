import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import Presentation from "./Presentation";
import Mobile from "./Mobile";
import "./styles.css";
import { installScrollHints } from "./scrollHint";

// ?m (the "Try it yourself" QR code) or a phone-sized screen gets the phone version; ?full forces the presentation
const q = new URLSearchParams(location.search);
const mobile = q.has("m") || (!q.has("full") && window.matchMedia("(max-width: 640px)").matches);
createRoot(document.getElementById("root")!).render(<StrictMode>{mobile ? <Mobile /> : <Presentation />}</StrictMode>);

installScrollHints();
