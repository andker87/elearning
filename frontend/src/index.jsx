import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { registraServiceWorker } from "./push";
import "./pwaInstall"; // registra il listener beforeinstallprompt prima del render
import { applicaTema, temaIniziale } from "./theme";
import "./styles.css";

applicaTema(temaIniziale());

createRoot(document.getElementById("root")).render(<App />);

if (import.meta.env.PROD) {
  registraServiceWorker().catch(() => {});
}
