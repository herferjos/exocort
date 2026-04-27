const mountedStyles = new Set();

export function registerStyles(key, cssText) {
  if (mountedStyles.has(key) || !cssText) {
    return;
  }

  const style = document.createElement("style");
  style.dataset.styleKey = key;
  style.textContent = cssText;
  (document.head || document.documentElement).append(style);
  mountedStyles.add(key);
}
