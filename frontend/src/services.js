import { button, createElement, createFieldRow } from "./dom.js";
import { createSelectField, createTextField, createToggleField } from "./fields.js";
import {
  loadServiceConfig,
  refreshServiceLogs,
  saveServiceConfig,
  selectService,
  startService,
  startServiceLogsPolling,
  stopService,
  stopServiceLogsPolling,
} from "./actions.js";
import { t } from "./i18n.js";
import { state } from "./state.js";
import { registerStyles } from "./style-registry.js";
import { buildServiceLogRow } from "./utils.js";

registerStyles("app-services", `
  .services-view {
    display: grid;
    gap: 20px;
  }

  .services-split {
    display: grid;
    grid-template-columns: 260px minmax(0, 1fr);
    gap: 18px;
    align-items: start;
  }

  .service-list-pane {
    position: sticky;
    top: 28px;
    display: grid;
    gap: 14px;
    padding: 20px;
    border-radius: var(--radius);
    background: var(--panel);
    border: 1px solid var(--border);
    box-shadow: var(--shadow);
  }

  .service-list-header {
    display: grid;
    gap: 6px;
  }

  .service-list-title {
    margin: 0;
    font-size: 0.82rem;
    font-weight: 800;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: var(--primary);
  }

  .service-list-subtitle {
    margin: 0;
    color: var(--muted);
    font-size: 0.85rem;
    line-height: 1.5;
  }

  .service-list {
    display: grid;
    gap: 6px;
  }

  .service-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 14px;
    border-radius: 16px;
    border: 1px solid transparent;
    background: rgba(255, 255, 255, 0.6);
    cursor: pointer;
    transition: background 120ms ease, border-color 120ms ease;
  }

  .service-item:hover {
    background: rgba(255, 255, 255, 0.92);
    border-color: var(--border);
  }

  .service-item.active {
    background: linear-gradient(180deg, rgba(23, 104, 255, 0.12), rgba(255, 255, 255, 0.94));
    border-color: rgba(23, 104, 255, 0.28);
    cursor: default;
  }

  .service-status-dot {
    width: 10px;
    height: 10px;
    border-radius: 999px;
    background: var(--muted);
    box-shadow: 0 0 0 3px rgba(102, 116, 135, 0.14);
    flex-shrink: 0;
    transition: background 200ms ease, box-shadow 200ms ease;
  }

  .service-status-dot.is-running {
    background: var(--success);
    box-shadow: 0 0 0 3px rgba(15, 159, 107, 0.18);
  }

  .service-item-info {
    display: grid;
    gap: 0;
    min-width: 0;
    flex: 1;
  }

  .service-item-name {
    margin: 0;
    font-size: 0.95rem;
    font-weight: 700;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }

  .service-detail {
    display: grid;
    gap: 0;
    border-radius: var(--radius);
    background: var(--panel);
    border: 1px solid var(--border);
    box-shadow: var(--shadow);
    overflow: hidden;
  }

  .service-detail-empty {
    padding: 48px 26px;
    text-align: center;
    color: var(--muted);
  }

  .service-detail-header {
    display: grid;
    gap: 10px;
    padding: 24px 26px 0;
  }

  .service-detail-top {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
  }

  .service-detail-name {
    margin: 0;
    font-size: 1.6rem;
    letter-spacing: -0.02em;
    flex: 1;
  }

  .service-detail-desc {
    margin: 0 0 4px;
    color: var(--muted);
    font-size: 0.9rem;
  }

  .service-tabs {
    display: flex;
    gap: 4px;
    padding: 4px 26px 0;
    overflow-x: auto;
    border-bottom: 1px solid var(--border);
  }

  .service-tab {
    padding: 0.7rem 1.1rem;
    border: 0;
    border-bottom: 2px solid transparent;
    background: transparent;
    color: var(--muted);
    cursor: pointer;
    font-size: 0.95rem;
    font-weight: 700;
    transition: color 120ms ease, border-color 120ms ease;
  }

  .service-tab:hover {
    color: var(--text);
  }

  .service-tab.active {
    color: var(--primary);
    border-color: var(--primary);
  }

  .service-detail-body {
    padding: 22px 26px 26px;
  }

  .service-config-panel,
  .service-logs-panel {
    display: none;
  }

  .service-config-panel.active,
  .service-logs-panel.active {
    display: grid;
    gap: 14px;
    min-width: 0;
    padding: 18px;
    border-radius: 20px;
    background: rgba(255, 255, 255, 0.78);
    border: 1px solid var(--border);
    box-shadow: var(--shadow-soft);
  }

  .service-config-form {
    display: grid;
    gap: 14px;
  }

  .service-save-note {
    margin: 0;
    font-size: 0.85rem;
    color: var(--muted);
  }

  @media (max-width: 960px) {
    .services-split {
      grid-template-columns: 1fr;
    }

    .service-list-pane {
      position: static;
    }
  }

  @media (max-width: 640px) {
    .service-detail-header,
    .service-tabs,
    .service-detail-body {
      padding-left: 18px;
      padding-right: 18px;
    }
  }
`);

const SERVICE_LABELS = {
  mac_asr: "mac ASR",
  mac_ocr: "mac OCR",
  faster_whisper: "Faster Whisper",
  llama_cpp: "Llama.cpp",
};

const LOCALES = ["auto", "es-ES", "en-US", "fr-FR", "de-DE", "it-IT", "pt-PT", "nl-NL", "ja-JP", "ko-KR", "zh-CN"];
const LOCALE_SHORT = ["es", "en", "fr", "de", "it", "pt", "nl", "ja", "ko", "zh"];
const LOG_LEVELS = ["debug", "info", "warning", "error"];
const LANGUAGES = ["auto", "en", "es", "fr", "de", "it", "pt", "nl", "ja", "ko", "zh"];
const SERVICE_PERSIST_DELAY = 300;
const servicePersistTimers = new Map();

function scheduleServiceConfigPersist(serviceName, fields) {
  const existing = servicePersistTimers.get(serviceName);
  if (existing !== undefined) {
    window.clearTimeout(existing);
  }
  const timer = window.setTimeout(() => {
    servicePersistTimers.delete(serviceName);
    void saveServiceConfig(serviceName, fields);
  }, SERVICE_PERSIST_DELAY);
  servicePersistTimers.set(serviceName, timer);
}

function getServiceFieldDefs(name, config) {
  const c = config || {};
  const common = [
    { labelKey: "services.host", key: "host", type: "text", value: c.host || "127.0.0.1" },
    { labelKey: "services.port", key: "port", type: "number", value: c.port != null ? String(c.port) : "" },
    { labelKey: "services.log_level", key: "log_level", type: "select", value: c.log_level || "info", options: LOG_LEVELS },
  ];

  if (name === "mac_asr") {
    return [
      { labelKey: "services.locale", key: "locale", type: "select", value: c.locale || "auto", options: LOCALES },
      { labelKey: "services.default_locale", key: "default_locale", type: "select", value: c.default_locale || "es", options: LOCALE_SHORT },
      {
        labelKey: "services.timeout_s",
        key: "transcription_timeout_s",
        type: "number",
        value: c.transcription_timeout_s != null ? String(c.transcription_timeout_s) : "30",
      },
      { labelKey: "services.detect_model", key: "detect_model", type: "select", value: c.detect_model || "tiny", options: ["tiny", "base", "small"] },
      { labelKey: "services.detect_device", key: "detect_device", type: "select", value: c.detect_device || "cpu", options: ["cpu", "cuda"] },
      {
        labelKey: "services.detect_compute_type",
        key: "detect_compute_type",
        type: "select",
        value: c.detect_compute_type || "int8",
        options: ["int8", "float16", "float32"],
      },
      ...common,
    ];
  }

  if (name === "faster_whisper") {
    return [
      {
        labelKey: "services.model_size",
        key: "model_size",
        type: "select",
        value: c.model_size || "medium",
        options: ["tiny", "base", "small", "medium", "large-v2", "large-v3"],
      },
      { labelKey: "services.model_path", key: "model_path", type: "text", value: c.model_path || "./models" },
      { labelKey: "services.device", key: "device", type: "select", value: c.device || "cpu", options: ["cpu", "cuda"] },
      {
        labelKey: "services.compute_type",
        key: "compute_type",
        type: "select",
        value: c.compute_type || "int8",
        options: ["int8", "float16", "float32"],
      },
      { labelKey: "services.language", key: "language", type: "select", value: c.language || "auto", options: LANGUAGES },
      { labelKey: "services.beam_size", key: "beam_size", type: "number", value: c.beam_size != null ? String(c.beam_size) : "5" },
      ...common,
    ];
  }

  if (name === "llama_cpp") {
    return [
      { labelKey: "services.model_id", key: "model_id", type: "text", value: c.model_id || "" },
      {
        labelKey: "services.quantization",
        key: "quantization",
        type: "select",
        value: c.quantization || "Q4_K_M",
        options: ["Q4_K_M", "Q8_0", "F16", "Q2_K", "Q5_K_M"],
      },
      { labelKey: "services.model_dir", key: "model_dir", type: "text", value: c.model_dir || "./llms" },
      {
        labelKey: "services.context_window",
        key: "n_ctx",
        type: "number",
        value: c.n_ctx != null ? String(c.n_ctx) : "4096",
      },
      { labelKey: "services.gpu_layers", key: "n_gpu_layers", type: "number", value: c.n_gpu_layers != null ? String(c.n_gpu_layers) : "0" },
      { labelKey: "services.cpu_threads", key: "n_threads", type: "number", value: c.n_threads != null ? String(c.n_threads) : "4" },
      { labelKey: "services.temperature", key: "temperature", type: "number", value: c.temperature != null ? String(c.temperature) : "0.5" },
      ...common,
    ];
  }

  // mac_ocr and fallback
  return common;
}

function renderServiceConfigForm(service, config) {
  const fieldDefs = getServiceFieldDefs(service.name, config);
  const controls = {};
  const formEl = createElement("div", "service-config-form");

  const rows = [];
  let currentRow = [];

  for (const def of fieldDefs) {
    let field;
    if (def.type === "toggle") {
      field = createToggleField({ label: t(def.labelKey), checked: Boolean(def.value) });
    } else if (def.type === "select") {
      field = createSelectField({ label: t(def.labelKey), value: String(def.value), options: def.options });
    } else {
      field = createTextField({ label: t(def.labelKey), value: String(def.value ?? "") });
      if (def.type === "number") {
        field.control.dataset.isNumber = "1";
      }
    }
    field.wrapper.dataset.serviceLabelKey = def.labelKey;
    controls[def.key] = field.control;
    const persist = () => scheduleServiceConfigPersist(service.name, controls);
    field.control.addEventListener("input", persist);
    field.control.addEventListener("change", persist);

    if (def.type === "toggle") {
      if (currentRow.length) {
        rows.push(createFieldRow(currentRow));
        currentRow = [];
      }
      rows.push(field.wrapper);
    } else {
      currentRow.push(field.wrapper);
      if (currentRow.length === 3) {
        rows.push(createFieldRow(currentRow));
        currentRow = [];
      }
    }
  }
  if (currentRow.length) {
    rows.push(createFieldRow(currentRow));
  }

  formEl.append(...rows);
  state.servicesFields = controls;
  return formEl;
}

export function renderServiceDetail(service, config) {
  const container = state.servicesDetailContainer;
  if (!container) {
    return;
  }

  const detail = createElement("section", "service-detail");

  const header = createElement("div", "service-detail-header");
  const top = createElement("div", "service-detail-top");
  const name = createElement("h2", "service-detail-name", SERVICE_LABELS[service.name] || service.name);
  const statusIndicator = createElement("span", "service-status-dot");
  statusIndicator.classList.toggle("is-running", service.running);
  top.append(statusIndicator, name);

  const desc = createElement("p", "service-detail-desc", service.description);

  const statusBtn = button(
    service.running ? t("services.stop") : t("services.start"),
    service.running ? "danger" : "primary",
    async () => {
      const currentService = state.servicesList.find((s) => s.name === service.name);
      if (currentService?.running) {
        await stopService(service.name);
      } else {
        await startService(service.name);
      }
    },
  );
  state.servicesStatusButton = statusBtn;
  top.append(statusBtn);

  header.append(top, desc);

  const tabBar = createElement("nav", "service-tabs");
  tabBar.setAttribute("role", "tablist");
  state.servicesTabButtons = [];

  const configTab = createElement("button", "service-tab active", t("services.config_tab"));
  configTab.type = "button";
  configTab.dataset.tab = "config";
  configTab.addEventListener("click", () => switchServiceTab("config"));
  state.servicesTabButtons.push(configTab);

  const logsTab = createElement("button", "service-tab", t("services.logs_tab"));
  logsTab.type = "button";
  logsTab.dataset.tab = "logs";
  logsTab.addEventListener("click", () => switchServiceTab("logs"));
  state.servicesTabButtons.push(logsTab);

  tabBar.append(configTab, logsTab);

  const body = createElement("div", "service-detail-body");

  const configPanel = createElement("div", "service-config-panel active");
  const formEl = renderServiceConfigForm(service, config);

  configPanel.append(formEl);
  state.servicesConfigPanel = configPanel;

  const logsPanel = createElement("div", "service-logs-panel");
  const logsHeader = createElement("div", "home-logs-header");
  const logsHeadCopy = createElement("div", "home-logs-head-copy");
  const logsTitle = createElement("p", "home-logs-title", t("home.activity"));
  logsHeadCopy.append(logsTitle);
  const logsActions = createElement("div", "home-logs-actions");
  const clearLogsBtn = button(t("home.clear"), "secondary", () => {
    state.servicesLogEntries[service.name] = [];
    state.servicesLogCursors[service.name] = 0;
    logList.replaceChildren(createElement("p", "home-logs-empty", t("home.service_logs_cleared")));
  });
  logsActions.append(clearLogsBtn);
  logsHeader.append(logsHeadCopy, logsActions);

  const logList = createElement("div", "home-logs-list");
  logList.setAttribute("role", "log");
  const emptyLog = createElement("p", "home-logs-empty", t("home.empty_logs"));
  logList.append(emptyLog);
  const existing = state.servicesLogEntries[service.name] || [];
  if (existing.length) {
    emptyLog.remove();
    for (const entry of existing) {
      const row = buildServiceLogRow(entry);
      logList.append(row);
    }
  }
  logsPanel.append(logsHeader, logList);
  state.servicesLogsPanel = logsPanel;

  body.append(configPanel, logsPanel);
  detail.append(header, tabBar, body);

  container.replaceChildren(detail);

  if (state.servicesActiveTab === "logs") {
    switchServiceTab("logs");
  }
}

export function refreshServiceLocalizedLabels() {
  const listTitle = state.servicesListContainer?.parentElement?.querySelector(".service-list-title");
  if (listTitle) {
    listTitle.textContent = t("services.list_title");
  }
  const listSubtitle = state.servicesListContainer?.parentElement?.querySelector(".service-list-subtitle");
  if (listSubtitle) {
    listSubtitle.textContent = t("services.list_subtitle");
  }

  const selected = state.servicesList.find((s) => s.name === state.servicesSelectedName);
  if (state.servicesStatusButton && selected) {
    state.servicesStatusButton.textContent = selected.running ? t("services.stop") : t("services.start");
  }

  for (const btn of state.servicesTabButtons) {
    if (btn.dataset.tab === "config") {
      btn.textContent = t("services.config_tab");
    } else if (btn.dataset.tab === "logs") {
      btn.textContent = t("services.logs_tab");
    }
  }

  const configPanel = state.servicesConfigPanel;
  if (configPanel) {
    const fieldWrappers = configPanel.querySelectorAll("[data-service-label-key]");
    for (const wrapper of fieldWrappers) {
      const key = wrapper.dataset.serviceLabelKey;
      if (!key) {
        continue;
      }
      const labelText = t(key);
      const label = wrapper.classList.contains("toggle-field") ? wrapper.querySelector("span:last-child") : wrapper.querySelector(".field-label");
      if (label) {
        label.textContent = labelText;
        label.title = labelText;
      }
      wrapper.title = labelText;
      const control = wrapper.querySelector("input, select, textarea");
      if (control) {
        control.title = labelText;
        control.dataset.label = labelText;
      }
    }
  }

  const logsPanel = state.servicesLogsPanel;
  if (logsPanel) {
    const logsTitle = logsPanel.querySelector(".home-logs-title");
    if (logsTitle) {
      logsTitle.textContent = t("home.activity");
    }
    const clearButton = logsPanel.querySelector(".home-logs-actions .inline-button");
    if (clearButton) {
      clearButton.textContent = t("home.clear");
    }
    const empty = logsPanel.querySelector(".home-logs-empty");
    if (empty) {
      empty.textContent = t("home.empty_logs");
    }
  }

  const detailEmpty = state.servicesDetailContainer?.querySelector(".service-detail-empty");
  if (detailEmpty) {
    detailEmpty.textContent = selected ? t("services.loading_config") : t("services.select_service");
  }
}

function switchServiceTab(tab) {
  state.servicesActiveTab = tab;
  for (const btn of state.servicesTabButtons) {
    btn.classList.toggle("active", btn.dataset.tab === tab);
  }
  if (state.servicesConfigPanel) {
    state.servicesConfigPanel.classList.toggle("active", tab === "config");
  }
  if (state.servicesLogsPanel) {
    state.servicesLogsPanel.classList.toggle("active", tab === "logs");
  }
  if (tab === "logs" && state.servicesSelectedName) {
    startServiceLogsPolling(state.servicesSelectedName);
    void refreshServiceLogs(state.servicesSelectedName);
  } else {
    stopServiceLogsPolling();
  }
}

function renderServiceListPane(services) {
  const pane = createElement("aside", "service-list-pane");
  const header = createElement("div", "service-list-header");
  const title = createElement("p", "service-list-title", t("services.list_title"));
  const subtitle = createElement("p", "service-list-subtitle", t("services.list_subtitle"));
  header.append(title, subtitle);

  const list = createElement("div", "service-list");
  state.servicesListContainer = list;

  for (const service of services) {
    const item = createElement("article", `service-item${service.name === state.servicesSelectedName ? " active" : ""}`);
    item.dataset.serviceName = service.name;

    const dot = createElement("span", "service-status-dot");
    dot.classList.toggle("is-running", service.running);

    const info = createElement("div", "service-item-info");
    const label = createElement("p", "service-item-name", SERVICE_LABELS[service.name] || service.name);
    info.append(label);

    item.append(dot, info);
    item.addEventListener("click", () => {
      void selectService(service.name);
    });
    list.append(item);
  }

  pane.append(header, list);
  return pane;
}

export function renderServicesPage(services) {
  const view = createElement("section", "services-view");
  const split = createElement("div", "services-split");

  const listPane = renderServiceListPane(services);

  const detailWrapper = createElement("div", "");
  state.servicesDetailContainer = detailWrapper;

  if (!state.servicesSelectedName && services.length) {
    state.servicesSelectedName = services[0].name;
  }

  const selected = services.find((s) => s.name === state.servicesSelectedName);
  if (selected) {
    if (state.servicesConfigs[selected.name]) {
      renderServiceDetail(selected, state.servicesConfigs[selected.name]);
    } else {
      const placeholder = createElement("div", "service-detail");
      const empty = createElement("p", "service-detail-empty", t("services.loading_config"));
      placeholder.append(empty);
      detailWrapper.replaceChildren(placeholder);
      void loadServiceConfig(selected.name).then(() => {
        renderServiceDetail(selected, state.servicesConfigs[selected.name] || {});
      });
    }
    const items = listPane.querySelectorAll(".service-item");
    for (const item of items) {
      item.classList.toggle("active", item.dataset.serviceName === selected.name);
    }
  } else {
    const placeholder = createElement("div", "service-detail");
    const empty = createElement("p", "service-detail-empty", t("services.select_service"));
    placeholder.append(empty);
    detailWrapper.replaceChildren(placeholder);
  }

  split.append(listPane, detailWrapper);
  view.append(split);
  return view;
}
