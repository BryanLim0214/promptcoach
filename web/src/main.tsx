import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

// Fonts are vendored rather than pulled from a CDN, so the build works with no
// network and a committee running this in three years is not depending on
// Google Fonts still serving the same files.
import "@fontsource-variable/newsreader";
import "@fontsource-variable/ibm-plex-sans";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";

import "./styles/tokens.css";
import "./styles/base.css";
import App from "./App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
