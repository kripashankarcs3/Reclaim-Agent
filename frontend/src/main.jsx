import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./tokens.css";
import "./index.css";
import App from "./App.jsx";
import { applyTheme, getInitialTheme } from "./theme.js";

// Render se PEHLE theme lagao, taaki galat theme ka flash na dikhe.
applyTheme(getInitialTheme());

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>
);
