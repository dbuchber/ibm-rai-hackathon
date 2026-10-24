import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import Presentation from "./Presentation";
import "./styles.css";
import { installScrollHints } from "./scrollHint";

createRoot(document.getElementById("root")!).render(<StrictMode><Presentation /></StrictMode>);

installScrollHints();
