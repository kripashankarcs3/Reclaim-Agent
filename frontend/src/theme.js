/*
theme.js — light/dark theme ka chhota helper.

Pehli baar: OS ki setting (prefers-color-scheme) follow karta hai.
Toggle dabane ke baad: user ki choice localStorage mein yaad rehti hai.
localStorage block ho (private window) to bhi crash nahi — bas yaad nahi rahega.
*/
const KEY = "reclaim-theme";

export function getInitialTheme() {
  try {
    const saved = localStorage.getItem(KEY);
    if (saved === "light" || saved === "dark") return saved;
  } catch { /* storage unavailable */ }
  return window.matchMedia?.("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

export function applyTheme(theme, persist = false) {
  document.documentElement.dataset.theme = theme;
  if (persist) {
    try { localStorage.setItem(KEY, theme); } catch { /* storage unavailable */ }
  }
}
