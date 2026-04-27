import { invoke, isTauri } from "@tauri-apps/api/core";

import { appRoot, state } from "./state.js";
import {
  refreshBackendLogs,
  refreshServiceList,
  refreshStatus,
  resetFriendlyLogs,
  showError,
} from "./actions.js";
import { registerStyles } from "./style-registry.js";
import {
  refreshLocalizedLabels,
  renderAppChrome,
  renderConfigurationsPage,
  renderHomePage,
  setActiveView,
} from "./pages.js";
import { renderServicesPage } from "./services.js";
import { getLanguage, setLanguage } from "./i18n.js";
import { readViewFromHash } from "./utils.js";

registerStyles("app-global", `
  :root {
    color-scheme: light;
    --bg: #eff3f8;
    --bg-strong: #dfe8f2;
    --panel: rgba(255, 255, 255, 0.82);
    --panel-strong: rgba(255, 255, 255, 0.94);
    --panel-muted: rgba(244, 247, 251, 0.9);
    --text: #16202c;
    --muted: #667487;
    --border: rgba(22, 32, 44, 0.1);
    --border-strong: rgba(22, 32, 44, 0.16);
    --shadow: 0 24px 60px rgba(17, 24, 39, 0.1);
    --shadow-soft: 0 14px 34px rgba(17, 24, 39, 0.08);
    --primary: #1768ff;
    --primary-hover: #0f55d5;
    --primary-soft: rgba(23, 104, 255, 0.1);
    --success: #0f9f6b;
    --success-soft: rgba(15, 159, 107, 0.12);
    --danger: #db4c42;
    --danger-hover: #c53a31;
    --danger-soft: rgba(219, 76, 66, 0.12);
    --warning-soft: rgba(234, 179, 8, 0.16);
    --warning: #b45309;
    --focus: rgba(23, 104, 255, 0.22);
    --radius: 24px;
    --radius-md: 18px;
    --radius-sm: 14px;
  }

  * {
    box-sizing: border-box;
  }

  body {
    margin: 0;
    min-height: 100vh;
    color: var(--text);
    font-family:
      "SF Pro Display",
      "Avenir Next",
      "Segoe UI",
      system-ui,
      sans-serif;
    background:
      radial-gradient(circle at top left, rgba(23, 104, 255, 0.14), transparent 30%),
      radial-gradient(circle at top right, rgba(0, 163, 122, 0.08), transparent 24%),
      linear-gradient(180deg, #f8fbff 0%, var(--bg) 46%, var(--bg-strong) 100%);
  }

  button,
  input,
  select,
  textarea {
    font: inherit;
  }

  button {
    border: 0;
  }

  code {
    padding: 0.1rem 0.35rem;
    border-radius: 999px;
    background: rgba(17, 24, 39, 0.08);
  }

  .app-frame {
    width: min(1180px, calc(100vw - 32px));
    margin: 28px auto 48px;
  }

  .app-main,
  .app-content {
    min-width: 0;
  }

  .app-shell {
    display: grid;
    gap: 18px;
  }

  .error-text {
    margin: 0 0 16px;
    padding: 12px 14px;
    color: var(--danger);
    background: var(--danger-soft);
    border: 1px solid rgba(157, 51, 44, 0.14);
    border-radius: var(--radius-sm);
    white-space: pre-wrap;
  }

  @media (max-width: 640px) {
    .app-frame {
      width: min(100vw - 20px, 1180px);
      margin: 14px auto 30px;
    }
  }
`);

async function boot() {
  if (!isTauri()) {
    appRoot.replaceChildren();
    showError("Tauri is not available in this tab.");
    return;
  }

  let catalog = { configs: [], activeConfig: "config.yaml" };
  try {
    catalog = (await invoke("load_config_catalog")) ?? catalog;
  } catch (error) {
    showError(error instanceof Error ? error.message : String(error));
  }

  try {
    const defaults = await invoke("load_defaults");
    state.defaults = defaults ?? {};
  } catch (error) {
    state.defaults = {};
    showError(error instanceof Error ? error.message : String(error));
  }

  let servicesList = [];
  try {
    servicesList = (await invoke("list_services")) ?? [];
    state.servicesList = servicesList;
  } catch {
    state.servicesList = [];
  }

  setLanguage(getLanguage());
  state.activeView = readViewFromHash();
  state.configCatalogData = catalog;
  state.views = {
    home: renderHomePage(catalog),
    configurations: renderConfigurationsPage(catalog, state.defaults),
    services: renderServicesPage(servicesList),
  };

  const chrome = renderAppChrome();
  appRoot.replaceChildren(chrome);
  setActiveView(state.activeView);
  refreshLocalizedLabels();
  resetFriendlyLogs();
  window.addEventListener("hashchange", () => {
    setActiveView(readViewFromHash());
  });

  await refreshStatus();
  setInterval(() => {
    void refreshStatus();
  }, 2500);
  setInterval(() => {
    void refreshBackendLogs();
  }, 1000);
}

void boot();
