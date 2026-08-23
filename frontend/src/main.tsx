import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles.css";
import { BRAND } from "./brand";

// Initialize theme before rendering
(function initializeTheme() {
  let theme = BRAND.theme;

  // DEV ONLY: Check for theme in URL first, then localStorage
  if (import.meta.env.DEV) {
    const fromUrl = new URLSearchParams(window.location.search).get("theme");
    if (fromUrl) {
      localStorage.setItem("preview_theme", fromUrl);
    }

    const previewTheme = localStorage.getItem("preview_theme");
    if (previewTheme) {
      theme = previewTheme;
    }
  }

  document.documentElement.dataset.theme = theme;
  document.title = BRAND.appName;
})();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
