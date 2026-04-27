import {
  button,
  createDivider,
  createElement,
  createFieldRow,
  createSection,
  createSubsectionLabel,
  iconButton,
} from "./dom.js";
import { createIcon } from "./icons.js";
import { createSelectField, createTextField, createToggleField } from "./fields.js";
import {
  addRuleRow,
  clearHomeActivityLogs,
  createManagedConfig,
  deleteManagedConfig,
  duplicateManagedConfig,
  persistConfig,
  refreshHomeActivityView,
  refreshServiceList,
  scheduleConfigPersist,
  setHomeActivitySource,
  startService,
  startServiceLogsPolling,
  startServicesRefresh,
  stopService,
  stopServiceLogsPolling,
  stopServicesRefresh,
  switchConfig,
  toggleBackend,
  updateConfigManager,
} from "./actions.js";
import {
  renderCapturesSection,
  loadCaptures,
  startCapturesAutoRefresh,
  stopCapturesAutoRefresh,
} from "./captures.js";
import { refreshServiceLocalizedLabels } from "./services.js";
import { CONFIG_TABS, FORMAT_OPTIONS, LOG_LEVELS, SUPPORTED_PROVIDERS } from "./constants.js";
import { getLanguage, LANGUAGES, setLanguage, t, toggleLanguage } from "./i18n.js";
import { registerStyles } from "./style-registry.js";
import { displayConfigName, mapping, normalizeConfigName, normalizeViewId, text } from "./utils.js";
import { state } from "./state.js";

registerStyles("app-pages", `
  .app-toolbar-row {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 16px;
  }

  .app-toolbar-lead {
    position: relative;
    display: flex;
    align-items: flex-start;
    gap: 12px;
    min-width: 0;
  }

  .app-toolbar-row--home {
    justify-content: space-between;
  }

  .app-utility-bar {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 5px;
    background: #fff;
    border: 1px solid var(--border-strong);
    border-radius: 999px;
    box-shadow: 0 14px 34px rgba(17, 24, 39, 0.14);
  }

  .app-utility-bar .inline-button {
    width: 40px;
    height: 40px;
    min-width: 0;
    padding: 0;
    border-radius: 999px;
    background: transparent;
    border: 0;
    box-shadow: none;
    color: var(--muted);
    font-size: 0.78rem;
    font-weight: 800;
    letter-spacing: 0.06em;
  }

  .app-utility-bar .inline-button:hover:not(:disabled) {
    background: rgba(22, 32, 44, 0.06);
    color: var(--text);
    transform: none;
  }

  .app-utility-bar .inline-button.active,
  .app-utility-bar .gear-button.active {
    background: var(--primary);
    color: #fff;
    box-shadow: 0 8px 18px rgba(23, 104, 255, 0.24);
  }

  .app-utility-bar .inline-button svg {
    display: block;
  }

  .app-utility-bar .language-toggle {
    width: auto;
    min-width: 44px;
    padding: 0 10px;
    gap: 4px;
    font-size: 1.1rem;
    letter-spacing: 0;
  }

  .language-dropdown {
    position: relative;
  }

  .language-dropdown-panel {
    position: absolute;
    top: calc(100% + 8px);
    right: 0;
    background: #fff;
    border: 1px solid var(--border-strong);
    border-radius: 16px;
    box-shadow: 0 14px 34px rgba(17, 24, 39, 0.14);
    padding: 6px;
    min-width: 148px;
    z-index: 200;
  }

  .language-dropdown-panel[hidden] {
    display: none;
  }

  .language-option {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    padding: 8px 12px;
    border: none;
    background: transparent;
    border-radius: 10px;
    cursor: pointer;
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--text);
    text-align: left;
    transition: background 100ms ease;
  }

  .language-option:hover {
    background: rgba(22, 32, 44, 0.06);
  }

  .language-option.active {
    color: var(--primary);
    background: var(--primary-soft);
  }

  .language-option-flag {
    font-size: 1.2rem;
    line-height: 1;
  }

  .language-option-check {
    margin-left: auto;
    font-size: 0.8rem;
    opacity: 0.7;
  }

  .app-back-bar {
    display: flex;
    align-items: center;
    padding: 5px;
    background: #fff;
    border: 1px solid var(--border-strong);
    border-radius: 999px;
    box-shadow: 0 14px 34px rgba(17, 24, 39, 0.14);
  }

  .app-back-bar[hidden] {
    display: none;
  }

  .app-back-bar .back-button {
    height: 40px;
    width: auto;
    padding: 0 14px 0 10px;
    gap: 8px;
    background: transparent;
    border: 0;
    box-shadow: none;
    color: var(--muted);
    border-radius: 999px;
  }

  .app-back-bar .back-button:hover:not(:disabled) {
    background: rgba(22, 32, 44, 0.06);
    color: var(--text);
    transform: none;
  }

  .app-back-bar .back-button svg {
    display: block;
  }

  .dynamic-list {
    display: grid;
    gap: 14px;
  }

  .field--with-action {
    position: relative;
  }

  .field--with-action .field-control {
    padding-right: 3rem;
  }

  .inline-button.field-visibility-toggle {
    position: absolute;
    right: 10px;
    bottom: 10px;
    width: 36px;
    height: 36px;
    min-width: 0;
    padding: 0;
    border-radius: 12px;
    background: transparent;
    border: 1px solid transparent;
    box-shadow: none;
    color: var(--muted);
  }

  .inline-button.field-visibility-toggle:hover:not(:disabled) {
    background: rgba(22, 32, 44, 0.06);
    border-color: transparent;
    color: var(--text);
    transform: none;
  }

  .inline-button.field-visibility-toggle svg {
    display: block;
  }

  .dynamic-row {
    display: grid;
    align-items: end;
    gap: 12px;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1.4fr) auto;
    padding: 14px;
    border: 1px solid var(--border);
    border-radius: 18px;
    background: rgba(255, 255, 255, 0.65);
  }

  .dynamic-row.rule {
    grid-template-columns: minmax(0, 1fr) minmax(0, 1.2fr) minmax(0, 1.2fr) auto;
  }

  .home-view {
    display: grid;
    gap: 22px;
  }

  .home-overview {
    display: grid;
    gap: 18px;
    padding: 26px;
    border-radius: var(--radius);
    background: linear-gradient(180deg, rgba(23, 104, 255, 0.08), rgba(255, 255, 255, 0.94));
    border: 1px solid var(--border);
    box-shadow: var(--shadow);
  }

  .home-status {
    display: grid;
    grid-template-columns: minmax(220px, 280px) minmax(0, 1fr);
    gap: 18px;
    align-items: start;
  }

  .home-status-indicator {
    width: 12px;
    height: 12px;
    border-radius: 999px;
    background: var(--muted);
    box-shadow: 0 0 0 4px rgba(102, 116, 135, 0.14);
    flex-shrink: 0;
  }

  .home-status-indicator.is-running {
    background: var(--success);
    box-shadow: 0 0 0 4px rgba(15, 159, 107, 0.14);
  }

  .home-services-card {
    display: grid;
    gap: 14px;
    padding: 18px;
    border-radius: 20px;
    background: rgba(255, 255, 255, 0.78);
    border: 1px solid var(--border);
    box-shadow: var(--shadow-soft);
  }

  .home-services-head {
    display: grid;
    gap: 4px;
  }

  .home-services-title-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
  }

  .home-services-title {
    margin: 0;
    font-size: 1rem;
    font-weight: 700;
    letter-spacing: -0.01em;
  }

  .home-services-list {
    display: grid;
    gap: 8px;
  }

  .home-side-stack {
    display: grid;
    gap: 18px;
    min-width: 0;
  }

  .home-service-item {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 12px;
    align-items: center;
    padding: 12px 12px 12px 14px;
    border-radius: 18px;
    border: 1px solid transparent;
    background: rgba(255, 255, 255, 0.58);
    cursor: pointer;
    transition:
      background-color 120ms ease,
      border-color 120ms ease,
      transform 120ms ease;
  }

  .home-service-item:hover {
    background: rgba(255, 255, 255, 0.92);
    border-color: var(--border);
  }

  .home-service-item.is-selected {
    background: linear-gradient(180deg, rgba(23, 104, 255, 0.1), rgba(255, 255, 255, 0.94));
    border-color: rgba(23, 104, 255, 0.24);
  }

  .home-service-info {
    display: grid;
    gap: 4px;
    min-width: 0;
  }

  .home-service-name {
    margin: 0;
  }

  .home-service-name {
    font-size: 0.95rem;
    font-weight: 700;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }

  .home-service-status-row {
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
    flex-wrap: nowrap;
  }

  .home-service-toggle {
    min-width: 88px;
    justify-content: center;
    padding-left: 0.9rem;
    padding-right: 0.9rem;
  }

  .home-logs-card {
    display: grid;
    gap: 14px;
    min-width: 0;
    padding: 18px;
    border-radius: 20px;
    background: rgba(255, 255, 255, 0.78);
    border: 1px solid var(--border);
    box-shadow: var(--shadow-soft);
  }

  .home-logs-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 16px;
    flex-wrap: wrap;
  }

  .home-logs-head-copy {
    display: grid;
    gap: 4px;
    min-width: 0;
  }

  .home-logs-title {
    margin: 0;
    font-size: 1.2rem;
    font-weight: 700;
    letter-spacing: -0.01em;
  }

  .home-logs-actions {
    display: flex;
    gap: 8px;
  }

  .home-logs-list {
    display: grid;
    gap: 10px;
    min-height: 220px;
    max-height: min(42vh, 420px);
    padding: 6px;
    overflow: auto;
  }

  .home-logs-list::-webkit-scrollbar {
    width: 8px;
  }

  .home-logs-list::-webkit-scrollbar-thumb {
    border-radius: 999px;
    background: rgba(22, 32, 44, 0.16);
  }

  .home-logs-empty {
    margin: auto;
    padding: 18px;
    color: var(--muted);
    text-align: center;
  }

  .friendly-log-row {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    gap: 14px;
    padding: 14px 16px;
    border-radius: 18px;
    background: rgba(255, 255, 255, 0.7);
    border: 1px solid var(--border);
    box-shadow: var(--shadow-soft);
  }

  .friendly-log-row.severity-warning {
    background: var(--warning-soft);
    border-color: rgba(234, 179, 8, 0.3);
  }

  .friendly-log-row.severity-error {
    background: var(--danger-soft);
    border-color: rgba(219, 76, 66, 0.28);
    border-left: 4px solid var(--danger);
  }

  .friendly-log-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    border-radius: 12px;
    font-size: 1.1rem;
    background: rgba(255, 255, 255, 0.75);
    border: 1px solid var(--border);
  }

  .friendly-log-row.severity-error .friendly-log-icon {
    background: rgba(255, 255, 255, 0.9);
    border-color: rgba(219, 76, 66, 0.3);
  }

  .friendly-log-body {
    display: grid;
    gap: 4px;
    min-width: 0;
  }

  .friendly-log-meta {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }

  .friendly-log-pill {
    display: inline-flex;
    align-items: center;
    padding: 0.2rem 0.6rem;
    border-radius: 999px;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: var(--primary);
    background: var(--primary-soft);
  }

  .friendly-log-row.severity-warning .friendly-log-pill {
    color: var(--warning);
    background: rgba(234, 179, 8, 0.2);
  }

  .friendly-log-row.severity-error .friendly-log-pill {
    color: #fff;
    background: var(--danger);
  }

  .friendly-log-time {
    color: var(--muted);
    font-size: 0.78rem;
  }

  .friendly-log-message {
    margin: 0;
    font-size: 0.98rem;
    line-height: 1.45;
    word-break: break-word;
  }

  .configurations-view {
    display: grid;
    gap: 20px;
  }

  .configurations-split {
    display: grid;
    grid-template-columns: 300px minmax(0, 1fr);
    gap: 18px;
    align-items: start;
  }

  .preset-pane {
    position: sticky;
    top: 28px;
    display: grid;
    gap: 16px;
    padding: 20px;
    border-radius: var(--radius);
    background: var(--panel);
    border: 1px solid var(--border);
    box-shadow: var(--shadow);
  }

  .preset-pane-header {
    display: grid;
    gap: 10px;
  }

  .preset-pane-title {
    margin: 0;
    font-size: 0.82rem;
    font-weight: 800;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: var(--primary);
  }

  .preset-pane-subtitle {
    margin: 0;
    color: var(--muted);
    font-size: 0.88rem;
    line-height: 1.5;
  }

  .preset-list {
    display: grid;
    gap: 8px;
    max-height: 60vh;
    overflow: auto;
  }

  .preset-item {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
    gap: 10px;
    padding: 12px 14px;
    border-radius: 16px;
    border: 1px solid transparent;
    background: rgba(255, 255, 255, 0.6);
    cursor: pointer;
    transition:
      background-color 120ms ease,
      border-color 120ms ease,
      transform 120ms ease;
  }

  .preset-item:hover {
    background: rgba(255, 255, 255, 0.92);
    border-color: var(--border);
  }

  .preset-item.active {
    background: linear-gradient(180deg, rgba(23, 104, 255, 0.12), rgba(255, 255, 255, 0.94));
    border-color: rgba(23, 104, 255, 0.28);
    cursor: default;
  }

  .preset-info {
    display: grid;
    gap: 2px;
    min-width: 0;
  }

  .preset-name {
    margin: 0;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
    font-size: 0.98rem;
    font-weight: 700;
  }

  .config-editor-title-row {
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
  }

  .config-editor-title-row .config-editor-title {
    min-width: 0;
    flex: 1;
  }

  .config-editor-title-row {
    align-items: flex-start;
  }

  .config-rename-input {
    width: 100%;
    min-width: 0;
    padding: 0.55rem 0.75rem;
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 12px;
    background: #fff;
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.5);
    font: inherit;
  }

  .config-rename-input:focus-visible {
    outline: 3px solid var(--focus);
    outline-offset: 2px;
  }

  .preset-tag {
    margin: 0;
    color: var(--muted);
    font-size: 0.74rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .preset-item.active .preset-tag {
    color: var(--primary);
  }

  .preset-actions {
    display: flex;
    gap: 4px;
    opacity: 0;
    transition: opacity 120ms ease;
  }

  .preset-item:hover .preset-actions,
  .preset-item.active .preset-actions {
    opacity: 1;
  }

  .preset-empty {
    margin: 0;
    padding: 16px;
    color: var(--muted);
    text-align: center;
    font-size: 0.88rem;
  }

  .config-editor {
    display: grid;
    gap: 0;
    padding: 0;
    overflow: hidden;
    border-radius: var(--radius);
    background: var(--panel);
    border: 1px solid var(--border);
    box-shadow: var(--shadow);
  }

  .config-editor-header {
    display: grid;
    gap: 6px;
    padding: 24px 26px 0;
  }

  .config-editor-title {
    margin: 0;
    font-size: 1.6rem;
    letter-spacing: -0.02em;
  }

  .config-editor-subtitle {
    margin: 0 0 12px;
    color: var(--muted);
    line-height: 1.5;
  }

  .config-tabs {
    display: flex;
    gap: 4px;
    padding: 4px 26px 0;
    overflow-x: auto;
    border-bottom: 1px solid var(--border);
  }

  .config-tab {
    padding: 0.7rem 1.1rem;
    border: 0;
    border-bottom: 2px solid transparent;
    background: transparent;
    color: var(--muted);
    cursor: pointer;
    font-size: 0.95rem;
    font-weight: 700;
    transition:
      color 120ms ease,
      border-color 120ms ease;
  }

  .config-tab:hover {
    color: var(--text);
  }

  .config-tab.active {
    color: var(--primary);
    border-color: var(--primary);
  }

  .config-editor-body {
    padding: 22px 26px 26px;
  }

  .config-panel {
    display: none;
  }

  .config-panel.active {
    display: block;
  }

  .config-panel .section-card {
    padding: 0;
    background: transparent;
    border: 0;
    box-shadow: none;
    backdrop-filter: none;
  }

  .config-tab:focus-visible,
  .preset-item:focus-visible {
    outline: 3px solid var(--focus);
    outline-offset: 2px;
  }

  @media (max-width: 960px) {
    .app-toolbar-row,
    .configurations-split {
      grid-template-columns: 1fr;
    }

    .app-toolbar-row {
      align-items: stretch;
      display: grid;
    }

    .preset-pane {
      position: static;
    }

    .preset-list {
      max-height: none;
    }

    .home-status {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 640px) {
    .home-status,
    .home-logs-card,
    .preset-pane,
    .config-editor {
      border-radius: 20px;
    }

    .home-status {
      gap: 16px;
    }

    .home-overview {
      padding: 18px;
    }

    .home-logs-card,
    .preset-pane {
      padding: 18px;
    }

    .config-editor-header,
    .config-tabs,
    .config-editor-body {
      padding-left: 18px;
      padding-right: 18px;
    }

    .dynamic-row,
    .dynamic-row.rule {
      grid-template-columns: 1fr;
    }

    .app-toolbar-row {
      gap: 12px;
      align-items: stretch;
      flex-direction: column;
    }

    .app-toolbar-lead,
    .app-utility-bar {
      width: 100%;
    }

    .app-utility-bar .inline-button,
    .app-back-bar .back-button {
      width: auto;
    }

    .home-primary-action {
      width: 100%;
    }
  }
`);

const HOME_SERVICE_LABELS = {
  backend: "Exocort",
  mac_asr: "mac ASR",
  mac_ocr: "mac OCR",
  faster_whisper: "Faster Whisper",
  llama_cpp: "Llama.cpp",
};

function homeServiceLabel(name) {
  if (name === "backend") {
    return t("home.backend_label");
  }
  return HOME_SERVICE_LABELS[name] || name;
}

function buildEnvKeysFromDefaults(defaults) {
  const keys = [];
  const processor = mapping(defaults.processor);
  for (const sectionName of ["ocr", "asr", "notes"]) {
    const section = mapping(processor[sectionName]);
    const key = text(section.api_key_env, "").trim();
    if (key && !keys.includes(key)) {
      keys.push(key);
    }
  }
  return keys;
}

function buildEnvEntriesFromConfig(config) {
  const envMap = mapping(config?.env_overrides);
  const entries = [];
  const seen = new Set();

  for (const key of buildEnvKeysFromDefaults(config)) {
    entries.push({ key, value: text(envMap[key], "") });
    seen.add(key);
  }

  for (const [key, value] of Object.entries(envMap)) {
    const normalizedKey = String(key).trim();
    if (!normalizedKey || seen.has(normalizedKey)) {
      continue;
    }
    entries.push({ key: normalizedKey, value: text(value, "") });
  }

  return entries;
}

export function navigateToView(viewId) {
  const normalized = normalizeViewId(viewId);
  if (window.location.hash !== `#${normalized}`) {
    window.location.hash = normalized;
    return;
  }
  setActiveView(normalized);
}

export function setActiveView(viewId) {
  const normalized = normalizeViewId(viewId);
  state.activeView = normalized;
  if (state.appContent && state.views[normalized]) {
    state.appContent.replaceChildren(state.views[normalized]);
  }
  if (normalized === "home") {
    void loadCaptures();
    void refreshServiceList();
    startCapturesAutoRefresh();
    startServicesRefresh();
    const serviceName = state.homeActivitySource.startsWith("service:") ? state.homeActivitySource.slice(8) : "";
    if (serviceName) {
      void setHomeActivitySource(state.homeActivitySource);
    } else {
      stopServiceLogsPolling();
    }
  } else if (normalized === "services") {
    stopCapturesAutoRefresh();
    void refreshServiceList();
    startServicesRefresh();
    if (state.servicesActiveTab === "logs" && state.servicesSelectedName) {
      startServiceLogsPolling(state.servicesSelectedName);
    } else {
      stopServiceLogsPolling();
    }
  } else {
    stopCapturesAutoRefresh();
    stopServicesRefresh();
  }
  updateUtilityBarState();
  state.appContent?.parentElement?.querySelector(".app-toolbar-row")?.classList.toggle(
    "app-toolbar-row--home",
    normalized === "home",
  );
}

function updateUtilityBarState() {
  const onHome = state.activeView === "home";
  const onConfigurations = state.activeView === "configurations";
  const onServices = state.activeView === "services";
  const onSubpage = onConfigurations || onServices;
  if (state.backBarContainer) {
    state.backBarContainer.hidden = !onSubpage;
  }
  if (state.utilityGearButton) {
    state.utilityGearButton.classList.toggle("active", onConfigurations);
  }
  if (state.utilityServicesButton) {
    state.utilityServicesButton.classList.toggle("active", onServices);
  }
}

function renderLanguageDropdown() {
  const wrapper = createElement("div", "language-dropdown");
  const panel = createElement("div", "language-dropdown-panel");
  panel.hidden = true;

  const trigger = createElement("button", "inline-button icon-button language-toggle");
  trigger.type = "button";

  const currentLang = LANGUAGES.find((l) => l.code === getLanguage()) ?? LANGUAGES[0];
  const flagSpan = createElement("span", "language-flag", currentLang.flag);
  trigger.append(flagSpan, createIcon("chevronDown", 12));
  trigger.title = t("home.change_language");
  trigger.setAttribute("aria-label", t("home.change_language"));

  for (const lang of LANGUAGES) {
    const option = createElement("button", `language-option${getLanguage() === lang.code ? " active" : ""}`);
    option.type = "button";
    option.append(createElement("span", "language-option-flag", lang.flag), createElement("span", "", lang.label));
    if (getLanguage() === lang.code) {
      option.append(createElement("span", "language-option-check", "✓"));
    }
    option.addEventListener("click", () => {
      setLanguage(lang.code);
      window.location.reload();
    });
    panel.append(option);
  }

  let outsideHandler = null;

  function closePanel() {
    panel.hidden = true;
    if (outsideHandler) {
      document.removeEventListener("click", outsideHandler, true);
      outsideHandler = null;
    }
  }

  trigger.addEventListener("click", (e) => {
    e.stopPropagation();
    if (!panel.hidden) {
      closePanel();
      return;
    }
    panel.hidden = false;
    outsideHandler = (ev) => {
      if (!wrapper.contains(ev.target)) closePanel();
    };
    document.addEventListener("click", outsideHandler, true);
  });

  wrapper.append(trigger, panel);
  state.utilityLanguageButton = trigger;
  state.utilityLanguagePanel = panel;
  return wrapper;
}

function renderUtilityBar() {
  const bar = createElement("div", "app-utility-bar");

  const languageDropdown = renderLanguageDropdown();
  const servicesButton = iconButton(createIcon("layers", 18), t("services.sidebar_button"), "services-button", () => {
    navigateToView("services");
  });
  const gearButton = iconButton(createIcon("settings", 18), t("home.settings"), "gear-button", () => {
    navigateToView("configurations");
  });

  bar.append(languageDropdown, servicesButton, gearButton);
  state.utilityServicesButton = servicesButton;
  state.utilityGearButton = gearButton;
  return bar;
}

function renderToolbarLead() {
  const lead = createElement("div", "app-toolbar-lead");
  lead.append(renderBackBar());
  return lead;
}

function renderBackBar() {
  const bar = createElement("div", "app-back-bar");
  const backButton = iconButton(
    createIcon("arrowLeft", 18),
    t("config.back_home"),
    "secondary back-button",
    () => {
      navigateToView("home");
    },
  );
  const backLabel = createElement("span", "back-button-label", t("config.back_home"));
  backButton.append(backLabel);
  bar.append(backButton);
  state.utilityBackButton = backButton;
  state.backBarContainer = bar;
  return bar;
}

export function renderAppChrome() {
  const shell = createElement("div", "app-shell");
  const toolbarRow = createElement("div", "app-toolbar-row");
  const content = createElement("main", "app-content");
  content.setAttribute("aria-live", "polite");
  state.appContent = content;
  toolbarRow.append(renderToolbarLead(), renderUtilityBar());
  shell.append(toolbarRow, content);
  return shell;
}

function renderRuntimeSection(defaults) {
  const logLevel = createSelectField({
    name: "log_level",
    label: t("field.log_level"),
    value: text(defaults.log_level, "INFO").toUpperCase(),
    options: LOG_LEVELS,
    tooltip: t("field.log_level_tip"),
  });

  const helper = createSubsectionLabel(t("helper.temp_config"), t("helper.temp_config_tip"));

  return createSection(t("section.general"), t("section.general_desc"), [
    createFieldRow([logLevel.wrapper]),
    helper,
  ]);
}

export function addEnvRow(name = "", value = "") {
  const row = createElement("div", "dynamic-row env");
  const keyField = createTextField({
    label: t("field.variable"),
    value: name,
    tooltip: t("field.variable_tip"),
  });
  const valueField = createTextField({
    label: t("field.value"),
    value,
    tooltip: t("field.value_tip"),
  });
  valueField.control.type = "password";
  valueField.control.autocomplete = "off";
  valueField.control.spellcheck = false;
  valueField.wrapper.classList.add("field--with-action");
  keyField.control.addEventListener("input", scheduleConfigPersist);
  valueField.control.addEventListener("input", scheduleConfigPersist);
  keyField.control.addEventListener("change", () => {
    void persistConfig();
  });
  valueField.control.addEventListener("change", () => {
    void persistConfig();
  });

  const toggleButton = iconButton(createIcon("eye", 16), t("field.show_value"), "field-visibility-toggle", () => {
    const visible = valueField.control.type === "text";
    valueField.control.type = visible ? "password" : "text";
    toggleButton.replaceChildren(createIcon(visible ? "eye" : "eyeOff", 16));
    const label = visible ? t("field.show_value") : t("field.hide_value");
    toggleButton.title = label;
    toggleButton.setAttribute("aria-label", label);
  });
  valueField.wrapper.append(toggleButton);

  const removeButton = button(t("actions.remove"), "danger", () => {
    state.envRows = state.envRows.filter((entry) => entry.row !== row);
    row.remove();
    void persistConfig();
  });

  row.append(keyField.wrapper, valueField.wrapper, removeButton);
  state.envRows.push({
    row,
    key: keyField.control,
    value: valueField.control,
  });
  return row;
}

function renderEnvSection(defaults) {
  const envList = createElement("div", "dynamic-list");
  state.envList = envList;
  const addButton = button(t("actions.add_variable"), "", () => {
    const row = addEnvRow();
    envList.append(row);
    void persistConfig();
  });
  for (const entry of buildEnvEntriesFromConfig(defaults)) {
    envList.append(addEnvRow(entry.key, entry.value));
  }

  return createSection(t("section.environment"), t("section.environment_desc"), [
    addButton,
    envList,
  ]);
}

function renderCapturerSection(defaults) {
  const capturer = mapping(defaults.capturer);
  const audio = mapping(capturer.audio);
  const vad = mapping(audio.vad);
  const screen = mapping(capturer.screen);

  const audioEnabled = createToggleField({
    name: "audio_enabled",
    label: t("field.audio_enabled"),
    checked: Boolean(audio.enabled),
    tooltip: t("field.audio_enabled_tip"),
  });
  const audioChunkSeconds = createTextField({
    name: "audio_chunk_seconds",
    label: t("field.chunk_seconds"),
    value: text(audio.chunk_seconds, 30),
    tooltip: t("field.chunk_seconds_tip"),
  });
  const audioSampleRate = createTextField({
    name: "audio_sample_rate",
    label: t("field.sample_rate"),
    value: text(audio.sample_rate, 16000),
    tooltip: t("field.sample_rate_tip"),
  });
  const audioChannels = createTextField({
    name: "audio_channels",
    label: t("field.channels"),
    value: text(audio.channels, 1),
    tooltip: t("field.channels_tip"),
  });
  const audioExpiredIn = createTextField({
    name: "audio_expired_in",
    label: t("field.expires_in"),
    value: text(audio.expired_in, 0),
    tooltip: t("field.expires_in_tip"),
  });

  const vadEnabled = createToggleField({
    name: "vad_enabled",
    label: t("field.vad_enabled"),
    checked: Boolean(vad.enabled),
    tooltip: t("field.vad_enabled_tip"),
  });
  const vadAggressiveness = createTextField({
    name: "vad_aggressiveness",
    label: t("field.aggressiveness"),
    value: text(vad.aggressiveness, 2),
    tooltip: t("field.aggressiveness_tip"),
  });
  const vadFrameMs = createTextField({
    name: "vad_frame_ms",
    label: t("field.frame_ms"),
    value: text(vad.frame_ms, 30),
    tooltip: t("field.frame_ms_tip"),
  });
  const vadPreRollSeconds = createTextField({
    name: "vad_pre_roll_seconds",
    label: t("field.pre_roll"),
    value: text(vad.pre_roll_seconds, 0.3),
    tooltip: t("field.pre_roll_tip"),
  });
  const vadMinSpeechSeconds = createTextField({
    name: "vad_min_speech_seconds",
    label: t("field.min_speech"),
    value: text(vad.min_speech_seconds, 0.2),
    tooltip: t("field.min_speech_tip"),
  });
  const vadMinSilenceSeconds = createTextField({
    name: "vad_min_silence_seconds",
    label: t("field.min_silence"),
    value: text(vad.min_silence_seconds, 0.8),
    tooltip: t("field.min_silence_tip"),
  });

  const screenEnabled = createToggleField({
    name: "screen_enabled",
    label: t("field.screen_enabled"),
    checked: Boolean(screen.enabled),
    tooltip: t("field.screen_enabled_tip"),
  });
  const screenIntervalSeconds = createTextField({
    name: "screen_interval_seconds",
    label: t("field.interval_seconds"),
    value: text(screen.interval_seconds, 5),
    tooltip: t("field.interval_seconds_tip"),
  });
  const screenExpiredIn = createTextField({
    name: "screen_expired_in",
    label: t("field.expires_in"),
    value: text(screen.expired_in, 0),
    tooltip: t("field.expires_in_tip"),
  });

  return createSection(t("section.capture"), t("section.capture_desc"), [
    createSubsectionLabel(t("subsection.audio"), t("subsection.audio_desc")),
    audioEnabled.wrapper,
    createFieldRow([audioChunkSeconds.wrapper, audioSampleRate.wrapper, audioChannels.wrapper]),
    audioExpiredIn.wrapper,
    createSubsectionLabel(t("subsection.vad"), t("subsection.vad_desc")),
    vadEnabled.wrapper,
    createFieldRow([vadAggressiveness.wrapper, vadFrameMs.wrapper, vadPreRollSeconds.wrapper]),
    createFieldRow([vadMinSpeechSeconds.wrapper, vadMinSilenceSeconds.wrapper]),
    createDivider(),
    createSubsectionLabel(t("subsection.screen"), t("subsection.screen_desc")),
    screenEnabled.wrapper,
    createFieldRow([screenIntervalSeconds.wrapper, screenExpiredIn.wrapper]),
  ]);
}

function renderProcessorSection(defaults) {
  const processor = mapping(defaults.processor);
  const ocr = mapping(processor.ocr);
  const asr = mapping(processor.asr);
  const contentFilter = mapping(processor.content_filter);
  const notes = mapping(processor.notes);

  const ocrEnabled = createToggleField({
    name: "ocr_enabled",
    label: t("field.ocr_enabled"),
    checked: Boolean(ocr.enabled),
    tooltip: t("field.ocr_enabled_tip"),
  });
  const ocrProvider = createSelectField({
    name: "ocr_provider",
    label: t("field.provider"),
    value: text(ocr.provider, "mistral"),
    options: SUPPORTED_PROVIDERS,
    tooltip: t("field.ocr_provider_tip"),
  });
  const ocrModel = createTextField({
    name: "ocr_model",
    label: t("field.model"),
    value: text(ocr.model, ""),
    tooltip: t("field.ocr_model_tip"),
  });
  const ocrApiBase = createTextField({
    name: "ocr_api_base",
    label: t("field.api_base"),
    value: text(ocr.api_base, ""),
    tooltip: t("field.ocr_api_base_tip"),
  });
  const ocrApiKeyEnv = createTextField({
    name: "ocr_api_key_env",
    label: t("field.api_key_env"),
    value: text(ocr.api_key_env, "test_key"),
    tooltip: t("field.ocr_api_key_env_tip"),
  });
  const ocrFormat = createSelectField({
    name: "ocr_format",
    label: t("field.format"),
    value: text(ocr.format, "ocr"),
    options: FORMAT_OPTIONS,
    tooltip: t("field.ocr_format_tip"),
  });
  const ocrTimeout = createTextField({
    name: "ocr_timeout_s",
    label: t("field.timeout_s"),
    value: text(ocr.timeout_s, 30.0),
    tooltip: t("field.ocr_timeout_tip"),
  });
  const ocrRetries = createTextField({
    name: "ocr_retries",
    label: t("field.retries"),
    value: text(ocr.retries, 2),
    tooltip: t("field.ocr_retries_tip"),
  });
  const ocrExpiredIn = createTextField({
    name: "ocr_expired_in",
    label: t("field.expires_in"),
    value: text(ocr.expired_in, 0),
    tooltip: t("field.ocr_expires_in_tip"),
  });
  const ocrLanguage = createTextField({
    name: "ocr_language",
    label: t("field.language"),
    value: text(ocr.language, ""),
    tooltip: t("field.ocr_language_tip"),
  });
  const ocrPrompt = createTextField({
    name: "ocr_prompt",
    label: t("field.prompt"),
    value: text(ocr.prompt, ""),
    multiline: true,
    rows: 4,
    tooltip: t("field.ocr_prompt_tip"),
  });

  const asrEnabled = createToggleField({
    name: "asr_enabled",
    label: t("field.asr_enabled"),
    checked: Boolean(asr.enabled),
    tooltip: t("field.asr_enabled_tip"),
  });
  const asrProvider = createSelectField({
    name: "asr_provider",
    label: t("field.provider"),
    value: text(asr.provider, "openai"),
    options: SUPPORTED_PROVIDERS,
    tooltip: t("field.asr_provider_tip"),
  });
  const asrModel = createTextField({
    name: "asr_model",
    label: t("field.model"),
    value: text(asr.model, ""),
    tooltip: t("field.asr_model_tip"),
  });
  const asrApiBase = createTextField({
    name: "asr_api_base",
    label: t("field.api_base"),
    value: text(asr.api_base, ""),
    tooltip: t("field.asr_api_base_tip"),
  });
  const asrApiKeyEnv = createTextField({
    name: "asr_api_key_env",
    label: t("field.api_key_env"),
    value: text(asr.api_key_env, "test_key"),
    tooltip: t("field.asr_api_key_env_tip"),
  });
  const asrFormat = createSelectField({
    name: "asr_format",
    label: t("field.format"),
    value: text(asr.format, "asr"),
    options: FORMAT_OPTIONS,
    tooltip: t("field.asr_format_tip"),
  });
  const asrTimeout = createTextField({
    name: "asr_timeout_s",
    label: t("field.timeout_s"),
    value: text(asr.timeout_s, 30.0),
    tooltip: t("field.asr_timeout_tip"),
  });
  const asrRetries = createTextField({
    name: "asr_retries",
    label: t("field.retries"),
    value: text(asr.retries, 2),
    tooltip: t("field.asr_retries_tip"),
  });
  const asrExpiredIn = createTextField({
    name: "asr_expired_in",
    label: t("field.expires_in"),
    value: text(asr.expired_in, 0),
    tooltip: t("field.asr_expires_in_tip"),
  });
  const asrLanguage = createTextField({
    name: "asr_language",
    label: t("field.language"),
    value: text(asr.language, ""),
    tooltip: t("field.asr_language_tip"),
  });
  const asrPrompt = createTextField({
    name: "asr_prompt",
    label: t("field.prompt"),
    value: text(asr.prompt, ""),
    multiline: true,
    rows: 4,
    tooltip: t("field.asr_prompt_tip"),
  });

  const contentFilterEnabled = createToggleField({
    name: "content_filter_enabled",
    label: t("field.content_filter_enabled"),
    checked: Boolean(contentFilter.enabled),
    tooltip: t("field.content_filter_enabled_tip"),
  });
  const ruleList = createElement("div", "dynamic-list");
  state.ruleList = ruleList;
  const addRuleButton = button(t("actions.add_rule"), "", () => {
    ruleList.append(addRuleRow());
  });
  const contentFilterRules = Array.isArray(contentFilter.rules) ? contentFilter.rules : [];
  contentFilterRules.forEach((rule, index) => {
    const ruleMapping = mapping(rule);
    ruleList.append(
      addRuleRow(
        text(ruleMapping.name, `rule_${index + 1}`),
        Array.isArray(ruleMapping.keywords) ? ruleMapping.keywords.map((item) => String(item).trim()).filter(Boolean) : [],
        Array.isArray(ruleMapping.regexes) ? ruleMapping.regexes.map((item) => String(item).trim()).filter(Boolean) : [],
      ),
    );
  });

  const notesEnabled = createToggleField({
    name: "notes_enabled",
    label: t("field.notes_enabled"),
    checked: Boolean(notes.enabled),
    tooltip: t("field.notes_enabled_tip"),
  });
  const notesIntervalSeconds = createTextField({
    name: "notes_interval_seconds",
    label: t("field.interval_seconds"),
    value: text(notes.interval_seconds, 60),
    tooltip: t("field.notes_interval_tip"),
  });
  const notesMaxInputTokens = createTextField({
    name: "notes_max_input_tokens",
    label: t("field.max_input_tokens"),
    value: text(notes.max_input_tokens, 10000),
    tooltip: t("field.max_input_tokens_tip"),
  });
  const notesMaxConcurrentBatch = createTextField({
    name: "notes_max_concurrent_batch",
    label: t("field.max_concurrent_batch"),
    value: text(notes.max_concurrent_batch, 4),
    tooltip: t("field.max_concurrent_batch_tip"),
  });
  const notesProvider = createTextField({
    name: "notes_provider",
    label: t("field.provider"),
    value: text(notes.provider, ""),
    tooltip: t("field.notes_provider_tip"),
  });
  const notesModel = createTextField({
    name: "notes_model",
    label: t("field.model"),
    value: text(notes.model, ""),
    tooltip: t("field.notes_model_tip"),
  });
  const notesApiBase = createTextField({
    name: "notes_api_base",
    label: t("field.api_base"),
    value: text(notes.api_base, ""),
    tooltip: t("field.notes_api_base_tip"),
  });
  const notesApiKeyEnv = createTextField({
    name: "notes_api_key_env",
    label: t("field.api_key_env"),
    value: text(notes.api_key_env, "test_key"),
    tooltip: t("field.notes_api_key_env_tip"),
  });
  const notesTimeout = createTextField({
    name: "notes_timeout_s",
    label: t("field.timeout_s"),
    value: text(notes.timeout_s, 30.0),
    tooltip: t("field.notes_timeout_tip"),
  });
  const notesRetries = createTextField({
    name: "notes_retries",
    label: t("field.retries"),
    value: text(notes.retries, 2),
    tooltip: t("field.notes_retries_tip"),
  });
  const notesTemperature = createTextField({
    name: "notes_temperature",
    label: t("field.temperature"),
    value: text(notes.temperature, 0.0),
    tooltip: t("field.notes_temperature_tip"),
  });
  const notesMaxToolIterations = createTextField({
    name: "notes_max_tool_iterations",
    label: t("field.max_tool_iterations"),
    value: text(notes.max_tool_iterations, 8),
    tooltip: t("field.max_tool_iterations_tip"),
  });
  const notesLanguage = createTextField({
    name: "notes_language",
    label: t("field.language"),
    value: text(notes.language, "English"),
    tooltip: t("field.notes_language_tip"),
  });
  const notesPrompt = createTextField({
    name: "notes_prompt",
    label: t("field.prompt"),
    value: text(notes.prompt, ""),
    multiline: true,
    rows: 4,
    tooltip: t("field.notes_prompt_tip"),
  });

  return createSection(t("section.processing"), t("section.processing_desc"), [
    createSubsectionLabel(t("subsection.ocr"), t("subsection.ocr_desc")),
    ocrEnabled.wrapper,
    createFieldRow([ocrProvider.wrapper, ocrFormat.wrapper, ocrApiKeyEnv.wrapper]),
    ocrModel.wrapper,
    ocrApiBase.wrapper,
    createFieldRow([ocrTimeout.wrapper, ocrRetries.wrapper, ocrExpiredIn.wrapper]),
    ocrLanguage.wrapper,
    ocrPrompt.wrapper,
    createDivider(),
    createSubsectionLabel(t("subsection.asr"), t("subsection.asr_desc")),
    asrEnabled.wrapper,
    createFieldRow([asrProvider.wrapper, asrFormat.wrapper, asrApiKeyEnv.wrapper]),
    asrModel.wrapper,
    asrApiBase.wrapper,
    createFieldRow([asrTimeout.wrapper, asrRetries.wrapper, asrExpiredIn.wrapper]),
    asrLanguage.wrapper,
    asrPrompt.wrapper,
    createDivider(),
    createSubsectionLabel(t("subsection.content_filter"), t("subsection.content_filter_desc")),
    contentFilterEnabled.wrapper,
    addRuleButton,
    ruleList,
    createDivider(),
    createSubsectionLabel(t("subsection.notes"), t("subsection.notes_desc")),
    notesEnabled.wrapper,
    createFieldRow([notesIntervalSeconds.wrapper, notesMaxInputTokens.wrapper, notesMaxConcurrentBatch.wrapper]),
    createFieldRow([notesProvider.wrapper, notesModel.wrapper]),
    createFieldRow([notesApiBase.wrapper, notesApiKeyEnv.wrapper]),
    createFieldRow([notesTimeout.wrapper, notesRetries.wrapper, notesTemperature.wrapper]),
    createFieldRow([notesMaxToolIterations.wrapper, notesLanguage.wrapper]),
    notesPrompt.wrapper,
  ]);
}

function renderPresetList(catalog) {
  const aside = createElement("aside", "preset-pane");
  const header = createElement("div", "preset-pane-header");
  const title = createElement("p", "preset-pane-title", t("config.profiles_title"));
  const subtitle = createElement("p", "preset-pane-subtitle", t("config.profiles_subtitle"));
  const newButton = button(t("config.new_profile"), "primary", async () => {
    const configs = Array.isArray(state.configCatalogData?.configs) ? state.configCatalogData.configs : [];
    const existing = new Set(configs.map((name) => normalizeConfigName(name)).filter(Boolean));
    let name = normalizeConfigName("custom");
    if (existing.has(name)) {
      let index = 2;
      while (existing.has(normalizeConfigName(`custom-${index}`))) {
        index += 1;
      }
      name = normalizeConfigName(`custom-${index}`);
    }
    if (!name) {
      return;
    }
    await createManagedConfig(name);
  });
  header.append(title, subtitle, newButton);
  state.configListTitle = title;
  state.configListSubtitle = subtitle;
  state.configNewButton = newButton;

  const list = createElement("div", "preset-list");
  state.presetListContainer = list;

  aside.append(header, list);
  updateConfigManager(catalog);
  return aside;
}

function renderConfigEditor(defaults) {
  const editor = createElement("section", "config-editor");

  const header = createElement("div", "config-editor-header");
  const eyebrow = createElement("p", "mini-label", t("config.editing_profile"));
  const nameHeading = createElement("div", "config-editor-title-row");
  const subtitle = createElement("p", "config-editor-subtitle", t("config.auto_save"));
  header.append(eyebrow, nameHeading, subtitle);
  state.configEditorHeader = nameHeading;
  state.configEditorEyebrow = eyebrow;
  state.configEditorSubtitle = subtitle;

  const tabBar = createElement("nav", "config-tabs");
  tabBar.setAttribute("role", "tablist");
  state.configTabButtons = [];

  const body = createElement("div", "config-editor-body");
  state.configEditorBody = body;

  const panels = {
    general: createElement("div", "config-panel"),
    capture: createElement("div", "config-panel"),
    processing: createElement("div", "config-panel"),
    environment: createElement("div", "config-panel"),
  };
  panels.general.append(renderRuntimeSection(defaults));
  panels.capture.append(renderCapturerSection(defaults));
  panels.processing.append(renderProcessorSection(defaults));
  panels.environment.append(renderEnvSection(defaults));

  for (const tab of CONFIG_TABS) {
    const tabButton = createElement("button", "config-tab", t(`tabs.${tab.id}`));
    tabButton.type = "button";
    tabButton.dataset.tab = tab.id;
    tabButton.setAttribute("role", "tab");
    tabButton.addEventListener("click", () => {
      setActiveConfigTab(tab.id);
    });
    state.configTabButtons.push(tabButton);
    tabBar.append(tabButton);
    body.append(panels[tab.id]);
  }

  editor.append(header, tabBar, body);
  setActiveConfigTab(state.activeConfigTab);
  return editor;
}

export function setActiveConfigTab(tabId) {
  const valid = CONFIG_TABS.some((tab) => tab.id === tabId) ? tabId : CONFIG_TABS[0].id;
  state.activeConfigTab = valid;
  for (const tabButton of state.configTabButtons) {
    tabButton.classList.toggle("active", tabButton.dataset.tab === valid);
  }
  if (state.configEditorBody) {
    const panels = state.configEditorBody.querySelectorAll(".config-panel");
    panels.forEach((panel, index) => {
      const id = CONFIG_TABS[index]?.id;
      panel.classList.toggle("active", id === valid);
    });
  }
}

export function renderHomePage(catalog) {
  const view = createElement("section", "home-view");
  const overview = createElement("div", "home-overview");

  const statusCard = createElement("section", "home-status");
  const sideStack = createElement("div", "home-side-stack");
  const servicesCard = createElement("section", "home-services-card");
  const servicesHead = createElement("div", "home-services-head");
  const servicesTitleRow = createElement("div", "home-services-title-row");
  const servicesTitle = createElement("p", "home-services-title", t("home.services_title"));
  servicesTitleRow.append(servicesTitle);
  servicesHead.append(servicesTitleRow);

  const servicesList = createElement("div", "home-services-list");
  const sources = [
    {
      source: "backend",
      name: "backend",
      running: state.backend.running,
    },
    ...state.servicesList.map((service) => ({
      source: `service:${service.name}`,
      name: service.name,
      running: service.running,
    })),
  ];

  for (const itemData of sources) {
    const item = createElement(
      "article",
      `home-service-item${state.homeActivitySource === itemData.source ? " is-selected" : ""}`,
    );
    item.dataset.source = itemData.source;
    item.tabIndex = 0;

    const dot = createElement("span", "service-status-dot");
    dot.classList.toggle("is-running", itemData.running);

    const info = createElement("div", "home-service-info");
    const name = createElement("p", "home-service-name", homeServiceLabel(itemData.name));
    const statusRow = createElement("div", "home-service-status-row");
    const badge = createElement("span", "status-pill", itemData.running ? t("home.status_active") : t("home.status_stopped"));
    badge.classList.toggle("is-running", itemData.running);
    statusRow.append(dot, badge);
    info.append(name, statusRow);

    const toggle = button(
      itemData.running ? t("home.stop") : t("home.start"),
      itemData.running ? "danger" : "primary",
      async (event) => {
        event.stopPropagation();
        if (itemData.name === "backend") {
          await toggleBackend();
          return;
        }
        const currentService = state.servicesList.find((service) => service.name === itemData.name);
        if (currentService?.running) {
          await stopService(itemData.name);
        } else {
          await startService(itemData.name);
        }
      },
    );
    toggle.classList.add("home-service-toggle");

    if (itemData.name === "backend") {
      state.homeStatusBadge = badge;
      state.homeStatusIndicator = dot;
      state.homeStatusText = name;
      state.homeStatusMeta = null;
      state.homeActionButton = toggle;
    }

    item.append(info, toggle);
    item.addEventListener("click", () => {
      setHomeActivitySource(itemData.source);
    });
    item.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        setHomeActivitySource(itemData.source);
      }
    });
    servicesList.append(item);
  }

  servicesCard.append(servicesHead, servicesList);
  state.homeServicesQuickList = servicesList;
  state.homeServicesSummary = null;

  const logsCard = createElement("section", "home-logs-card");
  const logsHeader = createElement("div", "home-logs-header");
  const logsTitle = createElement("p", "home-logs-title", t("home.activity"));
  const logsHeadCopy = createElement("div", "home-logs-head-copy");
  logsHeadCopy.append(logsTitle);
  const logsActions = createElement("div", "home-logs-actions");
  logsActions.append(button(t("home.clear"), "secondary", clearHomeActivityLogs));
  logsHeader.append(logsHeadCopy, logsActions);

  const logList = createElement("div", "home-logs-list");
  logList.setAttribute("role", "log");
  const emptyState = createElement("p", "home-logs-empty", t("home.empty_logs"));
  logList.append(emptyState);

  logsCard.append(logsHeader, logList);

  state.homeLogList = logList;
  state.homeLogSourceMeta = null;

  sideStack.append(servicesCard);
  statusCard.append(sideStack, logsCard);
  overview.append(statusCard);
  view.append(overview, renderCapturesSection(catalog));
  refreshHomeActivityView();
  return view;
}

export function renderConfigurationsPage(catalog, defaults) {
  const view = createElement("section", "configurations-view");
  const split = createElement("div", "configurations-split");
  split.append(renderPresetList(catalog), renderConfigEditor(defaults));
  view.append(split);
  updateConfigManager(catalog);
  return view;
}

function updateLanguageButton() {
  const trigger = state.utilityLanguageButton;
  const panel = state.utilityLanguagePanel;
  if (!trigger) return;

  const flagSpan = trigger.querySelector(".language-flag");
  const currentLang = LANGUAGES.find((l) => l.code === getLanguage()) ?? LANGUAGES[0];
  if (flagSpan) flagSpan.textContent = currentLang.flag;
  trigger.title = t("home.change_language");
  trigger.setAttribute("aria-label", t("home.change_language"));

  if (panel) {
    const options = panel.querySelectorAll(".language-option");
    options.forEach((opt, i) => {
      const lang = LANGUAGES[i];
      if (!lang) return;
      const isActive = getLanguage() === lang.code;
      opt.className = `language-option${isActive ? " active" : ""}`;
      const existingCheck = opt.querySelector(".language-option-check");
      if (isActive && !existingCheck) {
        opt.append(createElement("span", "language-option-check", "✓"));
      } else if (!isActive && existingCheck) {
        existingCheck.remove();
      }
    });
  }
}

export function refreshLocalizedLabels() {
  updateLanguageButton();

  if (state.utilityGearButton) {
    state.utilityGearButton.title = t("home.settings");
    state.utilityGearButton.setAttribute("aria-label", t("home.settings"));
  }
  if (state.utilityBackButton) {
    state.utilityBackButton.title = t("config.back_home");
    state.utilityBackButton.setAttribute("aria-label", t("config.back_home"));
    const label = state.utilityBackButton.querySelector(".back-button-label");
    if (label) {
      label.textContent = t("config.back_home");
    }
  }
  if (state.utilityServicesButton) {
    state.utilityServicesButton.title = t("services.sidebar_button");
    state.utilityServicesButton.setAttribute("aria-label", t("services.sidebar_button"));
  }

  if (state.homeStatusBadge) {
    state.homeStatusBadge.textContent = state.backend.running ? t("home.status_active") : t("home.status_stopped");
    state.homeStatusBadge.classList.toggle("is-running", state.backend.running);
  }
  if (state.homeStatusIndicator) {
    state.homeStatusIndicator.classList.toggle("is-running", state.backend.running);
  }
  if (state.homeStatusText) {
    state.homeStatusText.textContent = t("home.backend_label");
  }
  if (state.homeStatusMeta) {
    state.homeStatusMeta.textContent = "";
  }
  if (state.homeActionButton) {
    state.homeActionButton.textContent = state.backend.running ? t("home.stop") : t("home.start");
  }
  const servicesTitle = state.homeServicesQuickList?.previousElementSibling?.querySelector(".home-services-title");
  if (servicesTitle) {
    servicesTitle.textContent = t("home.services_title");
  }
  if (state.configListTitle) {
    state.configListTitle.textContent = t("config.profiles_title");
  }
  if (state.configListSubtitle) {
    state.configListSubtitle.textContent = t("config.profiles_subtitle");
  }
  if (state.configNewButton) {
    state.configNewButton.textContent = t("config.new_profile");
    state.configNewButton.setAttribute("aria-label", t("config.new_profile"));
  }
  if (state.configEditorEyebrow) {
    state.configEditorEyebrow.textContent = t("config.editing_profile");
  }
  if (state.configEditorSubtitle) {
    state.configEditorSubtitle.textContent = t("config.auto_save");
  }
  for (const tabButton of state.configTabButtons) {
    const tabId = tabButton?.dataset?.tab;
    if (tabId) {
      tabButton.textContent = t(`tabs.${tabId}`);
    }
  }
  refreshServiceLocalizedLabels();

  if (state.configCatalogData) {
    updateConfigManager(state.configCatalogData);
  }
  refreshHomeActivityView();
}

export async function toggleLanguageView() {
  toggleLanguage();
  window.location.reload();
}
