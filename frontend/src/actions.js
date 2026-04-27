import { invoke, isTauri } from "@tauri-apps/api/core";

import { INTERNAL_PATHS } from "./constants.js";
import { createElement, button, iconButton } from "./dom.js";
import { createIcon } from "./icons.js";
import { t } from "./i18n.js";
import { addEnvRow } from "./pages.js";
import {
  buildServiceLogRow,
  classifyLog,
  displayConfigName,
  fieldValue,
  formatRelativeTime,
  mapping,
  normalizeConfigName,
  parseExpiredIn,
  parseFloatField,
  parseIntField,
  setCheckboxValue,
  setInputValue,
  setSelectValue,
  splitLines,
  text,
} from "./utils.js";
import { errorText, state } from "./state.js";

const MAX_LOG_ENTRIES = 500;

const HOME_BACKEND_SOURCE = "backend";

const HOME_SERVICE_LABELS = {
  backend: "Exocort",
  mac_asr: "mac ASR",
  mac_ocr: "mac OCR",
  faster_whisper: "Faster Whisper",
  llama_cpp: "Llama.cpp",
};

export function showError(message) {
  console.error(message);
  errorText.hidden = false;
  errorText.textContent = `Error: ${message}`;
}

export function clearError() {
  errorText.textContent = "";
  errorText.hidden = true;
}

export function confirmAction(message) {
  if (isTauri()) {
    return true;
  }
  return window.confirm(message);
}

function buildEnvOverrides() {
  const overrides = {};
  for (const row of state.envRows) {
    const key = fieldValue(row.key, "");
    const value = fieldValue(row.value, "");
    if (key && value) {
      overrides[key] = value;
    }
  }
  return overrides;
}

export function addRuleRow(name = "", keywords = [], regexes = []) {
  const row = createElement("div", "dynamic-row rule");
  const nameField = createElement("label", "field");
  const keywordField = createElement("label", "field");
  const regexField = createElement("label", "field");
  const nameInput = document.createElement("input");
  const keywordInput = document.createElement("textarea");
  const regexInput = document.createElement("textarea");

  const buildField = (wrapper, labelText, input, value, multiline = false) => {
    const caption = createElement("span", "field-label", labelText);
    input.className = multiline ? "textarea-control" : "field-control";
    if (!multiline) {
      input.type = "text";
    } else {
      input.rows = 3;
    }
    input.value = value;
    input.dataset.label = labelText;
    wrapper.append(caption, input);
  };

  buildField(nameField, t("field.rule_name"), nameInput, name);
  buildField(keywordField, t("field.rule_keywords"), keywordInput, keywords.join("\n"), true);
  buildField(regexField, t("field.rule_regexes"), regexInput, regexes.join("\n"), true);

  const removeButton = button(t("actions.remove"), "danger", () => {
    state.ruleRows = state.ruleRows.filter((entry) => entry.row !== row);
    row.remove();
    void persistConfig();
  });

  row.append(nameField, keywordField, regexField, removeButton);
  nameInput.addEventListener("input", scheduleConfigPersist);
  nameInput.addEventListener("change", () => {
    void persistConfig();
  });
  keywordInput.addEventListener("input", scheduleConfigPersist);
  keywordInput.addEventListener("change", () => {
    void persistConfig();
  });
  regexInput.addEventListener("input", scheduleConfigPersist);
  regexInput.addEventListener("change", () => {
    void persistConfig();
  });
  state.ruleRows.push({
    row,
    name: nameInput,
    keywords: keywordInput,
    regexes: regexInput,
  });
  return row;
}

export function buildConfig() {
  const defaults = state.defaults;
  const capturerDefaults = mapping(defaults.capturer);
  const audioDefaults = mapping(capturerDefaults.audio);
  const vadDefaults = mapping(audioDefaults.vad);
  const screenDefaults = mapping(capturerDefaults.screen);
  const processorDefaults = mapping(defaults.processor);
  const ocrDefaults = mapping(processorDefaults.ocr);
  const asrDefaults = mapping(processorDefaults.asr);
  const notesDefaults = mapping(processorDefaults.notes);

  const rules = [];
  for (const [index, row] of state.ruleRows.entries()) {
    const name = fieldValue(row.name, "");
    const keywords = splitLines(row.keywords);
    const regexes = splitLines(row.regexes);
    if (!name && !keywords.length && !regexes.length) {
      continue;
    }
    rules.push({
      name: name || `rule_${index + 1}`,
      keywords,
      regexes,
    });
  }

  return {
    log_level: fieldValue(state.fields.log_level, "INFO").toUpperCase(),
    capturer: {
      audio: {
        enabled: Boolean(state.fields.audio_enabled.checked),
        chunk_seconds: parseIntField(state.fields.audio_chunk_seconds, Number(audioDefaults.chunk_seconds ?? 30)),
        sample_rate: parseIntField(state.fields.audio_sample_rate, Number(audioDefaults.sample_rate ?? 16000)),
        channels: parseIntField(state.fields.audio_channels, Number(audioDefaults.channels ?? 1)),
        output_dir: INTERNAL_PATHS.audio_output_dir,
        expired_in: parseExpiredIn(state.fields.audio_expired_in, audioDefaults.expired_in ?? 0),
        vad: {
          enabled: Boolean(state.fields.vad_enabled.checked),
          aggressiveness: parseIntField(state.fields.vad_aggressiveness, Number(vadDefaults.aggressiveness ?? 2)),
          frame_ms: parseIntField(state.fields.vad_frame_ms, Number(vadDefaults.frame_ms ?? 30)),
          pre_roll_seconds: parseFloatField(
            state.fields.vad_pre_roll_seconds,
            Number(vadDefaults.pre_roll_seconds ?? 0.3),
          ),
          min_speech_seconds: parseFloatField(
            state.fields.vad_min_speech_seconds,
            Number(vadDefaults.min_speech_seconds ?? 0.2),
          ),
          min_silence_seconds: parseFloatField(
            state.fields.vad_min_silence_seconds,
            Number(vadDefaults.min_silence_seconds ?? 0.8),
          ),
        },
      },
      screen: {
        enabled: Boolean(state.fields.screen_enabled.checked),
        interval_seconds: parseIntField(
          state.fields.screen_interval_seconds,
          Number(screenDefaults.interval_seconds ?? 5),
        ),
        output_dir: INTERNAL_PATHS.screen_output_dir,
        expired_in: parseExpiredIn(state.fields.screen_expired_in, screenDefaults.expired_in ?? 0),
      },
    },
    processor: {
      watch_dir: INTERNAL_PATHS.watch_dir,
      output_dir: INTERNAL_PATHS.processor_output_dir,
      ocr: {
        enabled: Boolean(state.fields.ocr_enabled.checked),
        provider: fieldValue(state.fields.ocr_provider, text(ocrDefaults.provider, "mistral")),
        model: fieldValue(state.fields.ocr_model, text(ocrDefaults.model, "")),
        api_base: fieldValue(state.fields.ocr_api_base, text(ocrDefaults.api_base, "")),
        api_key_env: fieldValue(state.fields.ocr_api_key_env, text(ocrDefaults.api_key_env, "test_key")),
        format: fieldValue(state.fields.ocr_format, text(ocrDefaults.format, "ocr")),
        timeout_s: parseFloatField(state.fields.ocr_timeout_s, Number(ocrDefaults.timeout_s ?? 30.0)),
        retries: parseIntField(state.fields.ocr_retries, Number(ocrDefaults.retries ?? 2)),
        expired_in: parseExpiredIn(state.fields.ocr_expired_in, ocrDefaults.expired_in ?? 0),
        language: fieldValue(state.fields.ocr_language, text(ocrDefaults.language, "")),
        prompt: fieldValue(state.fields.ocr_prompt, text(ocrDefaults.prompt, "")),
      },
      asr: {
        enabled: Boolean(state.fields.asr_enabled.checked),
        provider: fieldValue(state.fields.asr_provider, text(asrDefaults.provider, "openai")),
        model: fieldValue(state.fields.asr_model, text(asrDefaults.model, "")),
        api_base: fieldValue(state.fields.asr_api_base, text(asrDefaults.api_base, "")),
        api_key_env: fieldValue(state.fields.asr_api_key_env, text(asrDefaults.api_key_env, "test_key")),
        format: fieldValue(state.fields.asr_format, text(asrDefaults.format, "asr")),
        timeout_s: parseFloatField(state.fields.asr_timeout_s, Number(asrDefaults.timeout_s ?? 30.0)),
        retries: parseIntField(state.fields.asr_retries, Number(asrDefaults.retries ?? 2)),
        expired_in: parseExpiredIn(state.fields.asr_expired_in, asrDefaults.expired_in ?? 0),
        language: fieldValue(state.fields.asr_language, text(asrDefaults.language, "")),
        prompt: fieldValue(state.fields.asr_prompt, text(asrDefaults.prompt, "")),
      },
      content_filter: {
        enabled: Boolean(state.fields.content_filter_enabled.checked),
        rules,
      },
      notes: {
        enabled: Boolean(state.fields.notes_enabled.checked),
        interval_seconds: parseIntField(
          state.fields.notes_interval_seconds,
          Number(notesDefaults.interval_seconds ?? 60),
        ),
        max_input_tokens: parseIntField(
          state.fields.notes_max_input_tokens,
          Number(notesDefaults.max_input_tokens ?? 10000),
        ),
        max_concurrent_batch: parseIntField(
          state.fields.notes_max_concurrent_batch,
          Number(notesDefaults.max_concurrent_batch ?? 4),
        ),
        vault_dir: INTERNAL_PATHS.notes_vault_dir,
        state_dir: INTERNAL_PATHS.notes_state_dir,
        provider: fieldValue(state.fields.notes_provider, text(notesDefaults.provider, "")),
        model: fieldValue(state.fields.notes_model, text(notesDefaults.model, "")),
        api_base: fieldValue(state.fields.notes_api_base, text(notesDefaults.api_base, "")),
        api_key_env: fieldValue(state.fields.notes_api_key_env, text(notesDefaults.api_key_env, "test_key")),
        timeout_s: parseFloatField(state.fields.notes_timeout_s, Number(notesDefaults.timeout_s ?? 30.0)),
        retries: parseIntField(state.fields.notes_retries, Number(notesDefaults.retries ?? 2)),
        temperature: parseFloatField(
          state.fields.notes_temperature,
          Number(notesDefaults.temperature ?? 0.0),
        ),
        max_tool_iterations: parseIntField(
          state.fields.notes_max_tool_iterations,
          Number(notesDefaults.max_tool_iterations ?? 8),
        ),
        language: fieldValue(state.fields.notes_language, text(notesDefaults.language, "English")),
        prompt: fieldValue(state.fields.notes_prompt, text(notesDefaults.prompt, "")),
      },
    },
  };
}

export function scheduleConfigPersist() {
  if (!isTauri() || state.configLoading) {
    return;
  }

  if (state.persistTimer !== null) {
    window.clearTimeout(state.persistTimer);
  }

  state.persistTimer = window.setTimeout(() => {
    state.persistTimer = null;
    void persistConfig();
  }, 300);
}

export async function persistConfig() {
  if (!isTauri() || state.configLoading || !state.activeConfigName) {
    return;
  }

  let config;
  try {
    config = buildConfig();
  } catch {
    return;
  }

  try {
    await invoke("save_backend_config", {
      activeConfig: state.activeConfigName,
      config,
      envOverrides: buildEnvOverrides(),
    });
  } catch (error) {
    showError(error instanceof Error ? error.message : String(error));
  }
}

function setActiveConfigMeta(catalog) {
  const configs = Array.isArray(catalog?.configs) ? catalog.configs : [];
  const activeConfig = text(catalog?.activeConfig, state.activeConfigName || "config.yaml");
  state.configCatalog = configs;
  state.activeConfigName = activeConfig;
  renderConfigEditorHeader();
}

function focusRenameInput() {
  if (!state.editingConfigName) {
    return;
  }
  const input = state.configEditorHeader?.querySelector(".config-rename-input");
  if (!input) {
    return;
  }
  input.focus();
  input.select();
}

function exitRenameMode() {
  state.editingConfigName = "";
  state.editingConfigDraft = "";
  if (state.configCatalogData) {
    updateConfigManager(state.configCatalogData);
  } else {
    renderConfigEditorHeader();
  }
}

function startRenameMode(configName) {
  state.editingConfigName = configName;
  state.editingConfigDraft = displayConfigName(configName);
  if (state.configCatalogData) {
    updateConfigManager(state.configCatalogData);
  } else {
    renderConfigEditorHeader();
  }
  window.requestAnimationFrame(() => {
    focusRenameInput();
  });
}

async function submitRenameMode(sourceConfig) {
  const target = normalizeConfigName(state.editingConfigDraft);
  if (!target) {
    return;
  }
  if (target === sourceConfig) {
    exitRenameMode();
    return;
  }
  exitRenameMode();
  await renameManagedConfig(sourceConfig, target);
}

function createRenameEditor(configName) {
  const wrapper = createElement("div", "config-editor-title-row");
  const isEditing = state.editingConfigName === configName;

  if (isEditing) {
    const input = document.createElement("input");
    input.type = "text";
    input.className = "config-rename-input";
    input.value = state.editingConfigDraft;
    input.dataset.configName = configName;
    input.setAttribute("aria-label", t("config.rename"));
    input.addEventListener("click", (event) => {
      event.stopPropagation();
    });
    input.addEventListener("input", () => {
      state.editingConfigDraft = input.value;
    });
    input.addEventListener("keydown", async (event) => {
      event.stopPropagation();
      if (event.key === "Enter") {
        event.preventDefault();
        await submitRenameMode(configName);
      }
      if (event.key === "Escape") {
        event.preventDefault();
        exitRenameMode();
      }
    });

    const saveButton = iconButton(createIcon("check", 16), t("config.save_name"), "preset-action", async (event) => {
      event.stopPropagation();
      await submitRenameMode(configName);
    });
    const cancelButton = iconButton(
      createIcon("close", 16),
      t("config.cancel_rename"),
      "preset-action",
      (event) => {
        event.stopPropagation();
        exitRenameMode();
      },
    );
    wrapper.append(input, saveButton, cancelButton);
    return wrapper;
  }

  const title = createElement("h2", "config-editor-title", displayConfigName(configName));
  const renameButton = iconButton(createIcon("edit", 16), t("config.rename"), "preset-action", (event) => {
    event.stopPropagation();
    startRenameMode(configName);
  });
  wrapper.append(title, renameButton);
  return wrapper;
}

function renderConfigEditorHeader() {
  if (!state.configEditorHeader) {
    return;
  }
  const activeConfig = state.activeConfigName || "config.yaml";
  state.configEditorHeader.replaceChildren(createRenameEditor(activeConfig));
}

function buildUniqueConfigName(baseName, existingConfigs) {
  const normalizedBase = normalizeConfigName(baseName);
  if (!normalizedBase) {
    return "";
  }
  const existing = new Set(
    (Array.isArray(existingConfigs) ? existingConfigs : []).map((name) => normalizeConfigName(name)).filter(Boolean),
  );
  if (!existing.has(normalizedBase)) {
    return normalizedBase;
  }

  const plainBase = normalizedBase.replace(/\.ya?ml$/i, "");
  let index = 2;
  while (true) {
    const candidate = normalizeConfigName(`${plainBase}-${index}`);
    if (candidate && !existing.has(candidate)) {
      return candidate;
    }
    index += 1;
  }
}

function renderPresetItems(catalog) {
  const container = state.presetListContainer;
  if (!container) {
    return;
  }

  const configs = Array.isArray(catalog?.configs) ? catalog.configs : [];
  const activeConfig = text(catalog?.activeConfig, state.activeConfigName || "config.yaml");
  container.replaceChildren();

  if (!configs.length) {
    container.append(createElement("p", "preset-empty", t("config.empty_profiles")));
    return;
  }

  for (const configName of configs) {
    const isActive = configName === activeConfig;
    const item = createElement("article", `preset-item${isActive ? " active" : ""}`);
    const info = createElement("div", "preset-info");
    const name = createElement("p", "preset-name", displayConfigName(configName));
    info.append(name);
    if (isActive) {
      info.append(createElement("p", "preset-tag", t("config.active_tag")));
    }

    const actions = createElement("div", "preset-actions");
    const duplicate = iconButton(
      createIcon("copy", 16),
      t("config.duplicate"),
      "preset-action",
      async (event) => {
        event.stopPropagation();
        const suggested = `${configName.replace(/\.ya?ml$/i, "")}-copy`;
        const target = buildUniqueConfigName(suggested, configs);
        if (!target) {
          return;
        }
        await duplicateManagedConfig(configName, target);
      },
    );
    actions.append(duplicate);
    const remove = iconButton(
      createIcon("trash", 16),
      t("config.delete"),
      "preset-action danger",
      async (event) => {
        event.stopPropagation();
        if (!confirmAction(t("config.delete_confirm", { name: displayConfigName(configName) }))) {
          return;
        }
        await deleteManagedConfig(configName);
      },
    );
    actions.append(remove);

    item.append(info, actions);
    item.addEventListener("click", async () => {
      if (isActive) {
        return;
      }
      await switchConfig(configName);
    });
    container.append(item);
  }
}

export function updateConfigManager(catalog) {
  state.configCatalogData = catalog;
  setActiveConfigMeta(catalog);
  renderPresetItems(catalog);
}

export async function loadActiveManagedConfig() {
  if (!isTauri()) {
    return;
  }

  const config = await invoke("load_defaults");
  syncFormFromConfig(config ?? {});
}

export function syncFormFromConfig(config) {
  const current = mapping(config);
  const capturer = mapping(current.capturer);
  const audio = mapping(capturer.audio);
  const vad = mapping(audio.vad);
  const screen = mapping(capturer.screen);
  const processor = mapping(current.processor);
  const ocr = mapping(processor.ocr);
  const asr = mapping(processor.asr);
  const contentFilter = mapping(processor.content_filter);
  const notes = mapping(processor.notes);

  state.defaults = current;

  setSelectValue(state.fields.log_level, text(current.log_level, "INFO").toUpperCase(), "INFO");

  setCheckboxValue(state.fields.audio_enabled, audio.enabled);
  setInputValue(state.fields.audio_chunk_seconds, text(audio.chunk_seconds, 30));
  setInputValue(state.fields.audio_sample_rate, text(audio.sample_rate, 16000));
  setInputValue(state.fields.audio_channels, text(audio.channels, 1));
  setInputValue(state.fields.audio_expired_in, text(audio.expired_in, 0));

  setCheckboxValue(state.fields.vad_enabled, vad.enabled);
  setInputValue(state.fields.vad_aggressiveness, text(vad.aggressiveness, 2));
  setInputValue(state.fields.vad_frame_ms, text(vad.frame_ms, 30));
  setInputValue(state.fields.vad_pre_roll_seconds, text(vad.pre_roll_seconds, 0.3));
  setInputValue(state.fields.vad_min_speech_seconds, text(vad.min_speech_seconds, 0.2));
  setInputValue(state.fields.vad_min_silence_seconds, text(vad.min_silence_seconds, 0.8));

  setCheckboxValue(state.fields.screen_enabled, screen.enabled);
  setInputValue(state.fields.screen_interval_seconds, text(screen.interval_seconds, 5));
  setInputValue(state.fields.screen_expired_in, text(screen.expired_in, 0));

  setCheckboxValue(state.fields.ocr_enabled, ocr.enabled);
  setSelectValue(state.fields.ocr_provider, text(ocr.provider, "mistral"), "mistral");
  setInputValue(state.fields.ocr_model, text(ocr.model, ""));
  setInputValue(state.fields.ocr_api_base, text(ocr.api_base, ""));
  setInputValue(state.fields.ocr_api_key_env, text(ocr.api_key_env, "test_key"));
  setSelectValue(state.fields.ocr_format, text(ocr.format, "ocr"), "ocr");
  setInputValue(state.fields.ocr_timeout_s, text(ocr.timeout_s, 30));
  setInputValue(state.fields.ocr_retries, text(ocr.retries, 2));
  setInputValue(state.fields.ocr_expired_in, text(ocr.expired_in, 0));
  setInputValue(state.fields.ocr_language, text(ocr.language, ""));
  setInputValue(state.fields.ocr_prompt, text(ocr.prompt, ""));

  setCheckboxValue(state.fields.asr_enabled, asr.enabled);
  setSelectValue(state.fields.asr_provider, text(asr.provider, "openai"), "openai");
  setInputValue(state.fields.asr_model, text(asr.model, ""));
  setInputValue(state.fields.asr_api_base, text(asr.api_base, ""));
  setInputValue(state.fields.asr_api_key_env, text(asr.api_key_env, "test_key"));
  setSelectValue(state.fields.asr_format, text(asr.format, "asr"), "asr");
  setInputValue(state.fields.asr_timeout_s, text(asr.timeout_s, 30));
  setInputValue(state.fields.asr_retries, text(asr.retries, 2));
  setInputValue(state.fields.asr_expired_in, text(asr.expired_in, 0));
  setInputValue(state.fields.asr_language, text(asr.language, ""));
  setInputValue(state.fields.asr_prompt, text(asr.prompt, ""));

  setCheckboxValue(state.fields.content_filter_enabled, contentFilter.enabled);
  if (state.envList) {
    const envOverrides = mapping(current.env_overrides);
    const processor = mapping(current.processor);
    const keys = [];
    for (const sectionName of ["ocr", "asr", "notes"]) {
      const section = mapping(processor[sectionName]);
      const key = text(section.api_key_env, "").trim();
      if (key && !keys.includes(key)) {
        keys.push(key);
      }
    }
    for (const key of Object.keys(envOverrides)) {
      const normalized = String(key).trim();
      if (normalized && !keys.includes(normalized)) {
        keys.push(normalized);
      }
    }

    state.envRows = [];
    state.envList.replaceChildren();
    for (const key of keys) {
      state.envList.append(addEnvRow(key, text(envOverrides[key], "")));
    }
  }
  if (state.ruleList) {
    state.ruleRows = [];
    state.ruleList.replaceChildren();
    const rules = Array.isArray(contentFilter.rules) ? contentFilter.rules : [];
    rules.forEach((rule, index) => {
      const ruleMapping = mapping(rule);
      state.ruleList.append(
        addRuleRow(
          text(ruleMapping.name, `rule_${index + 1}`),
          Array.isArray(ruleMapping.keywords)
            ? ruleMapping.keywords.map((item) => String(item).trim()).filter(Boolean)
            : [],
          Array.isArray(ruleMapping.regexes)
            ? ruleMapping.regexes.map((item) => String(item).trim()).filter(Boolean)
            : [],
        ),
      );
    });
  }

  setCheckboxValue(state.fields.notes_enabled, notes.enabled);
  setInputValue(state.fields.notes_interval_seconds, text(notes.interval_seconds, 60));
  setInputValue(state.fields.notes_max_input_tokens, text(notes.max_input_tokens, 10000));
  setInputValue(state.fields.notes_max_concurrent_batch, text(notes.max_concurrent_batch, 4));
  setInputValue(state.fields.notes_provider, text(notes.provider, ""));
  setInputValue(state.fields.notes_model, text(notes.model, ""));
  setInputValue(state.fields.notes_api_base, text(notes.api_base, ""));
  setInputValue(state.fields.notes_api_key_env, text(notes.api_key_env, "test_key"));
  setInputValue(state.fields.notes_timeout_s, text(notes.timeout_s, 30));
  setInputValue(state.fields.notes_retries, text(notes.retries, 2));
  setInputValue(state.fields.notes_temperature, text(notes.temperature, 0.0));
  setInputValue(state.fields.notes_max_tool_iterations, text(notes.max_tool_iterations, 8));
  setInputValue(state.fields.notes_language, text(notes.language, "English"));
  setInputValue(state.fields.notes_prompt, text(notes.prompt, ""));
}

export async function switchConfig(configName) {
  const normalized = normalizeConfigName(configName);
  if (!normalized || normalized === state.activeConfigName) {
    return;
  }

  try {
    await persistConfig();
    state.configLoading = true;
    const catalog = await invoke("set_active_config", { configName: normalized });
    updateConfigManager(catalog);
    await loadActiveManagedConfig();
  } catch (error) {
    showError(error instanceof Error ? error.message : String(error));
  } finally {
    state.configLoading = false;
  }
}

export async function createManagedConfig(configName) {
  if (!isTauri()) {
    return;
  }

  try {
    await persistConfig();
    state.configLoading = true;
    const catalog = await invoke("create_config", { configName });
    updateConfigManager(catalog);
    await loadActiveManagedConfig();
  } catch (error) {
    showError(error instanceof Error ? error.message : String(error));
  } finally {
    state.configLoading = false;
  }
}

export async function duplicateManagedConfig(sourceConfig, targetConfig) {
  if (!isTauri()) {
    return;
  }

  try {
    await persistConfig();
    state.configLoading = true;
    const catalog = await invoke("duplicate_config", {
      sourceConfig,
      targetConfig,
    });
    updateConfigManager(catalog);
    await loadActiveManagedConfig();
  } catch (error) {
    showError(error instanceof Error ? error.message : String(error));
  } finally {
    state.configLoading = false;
  }
}

export async function renameManagedConfig(sourceConfig, targetConfig) {
  if (!isTauri()) {
    return;
  }

  try {
    await persistConfig();
    state.configLoading = true;
    const catalog = await invoke("rename_config", {
      sourceConfig,
      targetConfig,
    });
    updateConfigManager(catalog);
    await loadActiveManagedConfig();
  } catch (error) {
    showError(error instanceof Error ? error.message : String(error));
  } finally {
    state.configLoading = false;
  }
}

export async function deleteManagedConfig(configName) {
  if (!isTauri()) {
    return;
  }

  try {
    await persistConfig();
    state.configLoading = true;
    const catalog = await invoke("delete_config", { configName });
    updateConfigManager(catalog);
    await loadActiveManagedConfig();
  } catch (error) {
    showError(error instanceof Error ? error.message : String(error));
  } finally {
    state.configLoading = false;
  }
}

export function updateStatus({ running, pid = null, message }) {
  state.backend.running = Boolean(running);
  state.backend.pid = pid;
  state.backend.message = message;

  if (state.homeStatusBadge) {
    state.homeStatusBadge.textContent = state.backend.running ? t("home.status_active") : t("home.status_stopped");
    state.homeStatusBadge.classList.toggle("is-running", state.backend.running);
  }
  if (state.homeStatusText) {
    state.homeStatusText.textContent = t("home.backend_label");
  }
  if (state.homeStatusMeta) {
    state.homeStatusMeta.textContent = "";
  }
  if (state.homeActionButton) {
    state.homeActionButton.textContent = state.backend.running ? t("home.stop") : t("home.start");
    state.homeActionButton.classList.toggle("danger", state.backend.running);
    state.homeActionButton.classList.toggle("primary", !state.backend.running);
    state.homeActionButton.classList.toggle("secondary", false);
  }
  updateHomeQuickAccessUI();
}

function getHomeActivitySourceServiceName() {
  return state.homeActivitySource.startsWith("service:") ? state.homeActivitySource.slice(8) : "";
}

function getHomeActivityDisplayName() {
  const serviceName = getHomeActivitySourceServiceName();
  if (!serviceName) {
    return t("home.backend_label");
  }
  return HOME_SERVICE_LABELS[serviceName] || serviceName;
}

function updateHomeQuickAccessUI() {
  const list = state.homeServicesQuickList;
  if (!list) {
    return;
  }

  for (const item of list.querySelectorAll(".home-service-item")) {
    const source = item.dataset.source || HOME_BACKEND_SOURCE;
    const serviceName = source.startsWith("service:") ? source.slice(8) : "";
    const service = serviceName ? state.servicesList.find((entry) => entry.name === serviceName) : null;
    const running = serviceName ? Boolean(service?.running) : state.backend.running;
    const selected = state.homeActivitySource === source;

    item.classList.toggle("is-selected", selected);

    const dot = item.querySelector(".service-status-dot");
    if (dot) {
      dot.classList.toggle("is-running", running);
    }

    const nameEl = item.querySelector(".home-service-name");
    if (nameEl) {
      nameEl.textContent = serviceName ? HOME_SERVICE_LABELS[serviceName] || serviceName : t("home.backend_label");
    }

    const badge = item.querySelector(".status-pill");
    if (badge) {
      badge.textContent = running ? t("home.status_active") : t("home.status_stopped");
      badge.classList.toggle("is-running", running);
    }

    const toggle = item.querySelector(".home-service-toggle");
    if (toggle) {
      toggle.textContent = running ? t("home.stop") : t("home.start");
      toggle.classList.toggle("danger", running);
      toggle.classList.toggle("primary", !running);
      toggle.classList.toggle("secondary", false);
    }
  }
}

export function refreshHomeActivityView() {
  const logList = state.homeLogList;
  if (!logList) {
    return;
  }

  const activeServiceName = getHomeActivitySourceServiceName();
  if (activeServiceName && !state.servicesList.some((service) => service.name === activeServiceName)) {
    state.homeActivitySource = HOME_BACKEND_SOURCE;
  }

  updateHomeQuickAccessUI();

  const logTitle = state.homeLogList?.parentElement?.querySelector(".home-logs-title");
  if (logTitle) {
    logTitle.textContent = `${t("home.activity")} - ${getHomeActivityDisplayName()}`;
  }

  logList.replaceChildren();

  if (state.homeActivitySource === HOME_BACKEND_SOURCE) {
    if (!state.logEntries.length) {
      logList.append(createElement("p", "home-logs-empty", t("home.empty_logs")));
    } else {
      for (const entry of state.logEntries) {
        logList.append(buildFriendlyRow(entry));
      }
    }

    return;
  }

  const entries = state.servicesLogEntries[activeServiceName] || [];
  if (!entries.length) {
    logList.append(createElement("p", "home-logs-empty", t("home.empty_logs")));
  } else {
    for (const entry of entries) {
      logList.append(buildServiceLogRow(entry));
    }
  }
}

export function setHomeActivitySource(source) {
  const next = source && source !== HOME_BACKEND_SOURCE ? source : HOME_BACKEND_SOURCE;
  const serviceName = next.startsWith("service:") ? next.slice(8) : "";
  if (serviceName && !state.servicesList.some((service) => service.name === serviceName)) {
    state.homeActivitySource = HOME_BACKEND_SOURCE;
  } else {
    state.homeActivitySource = next;
  }

  if (state.activeView === "home") {
    const activeServiceName = getHomeActivitySourceServiceName();
    if (activeServiceName) {
      startServiceLogsPolling(activeServiceName);
      void refreshServiceLogs(activeServiceName);
    } else {
      stopServiceLogsPolling();
    }
  }

  refreshHomeActivityView();
}

function buildFriendlyRow(entry) {
  const classified = classifyLog(entry);
  const row = createElement("article", `friendly-log-row severity-${classified.severity}`);
  const icon = createElement("span", "friendly-log-icon", classified.icon);
  const body = createElement("div", "friendly-log-body");
  const meta = createElement("div", "friendly-log-meta");
  const pill = createElement("span", "friendly-log-pill", classified.category);
  const time = createElement(
    "span",
    "friendly-log-time",
    classified.timestamp ? formatRelativeTime(classified.timestamp) || classified.timestamp : formatRelativeTime(entry?.receivedAt ?? Date.now()),
  );
  meta.append(pill, time);
  const message = createElement("p", "friendly-log-message", classified.message);
  message.title = classified.rawMessage;
  body.append(meta, message);
  row.append(icon, body);
  return row;
}

export function refreshFriendlyLogs() {
  if (!state.homeLogList || state.homeActivitySource !== HOME_BACKEND_SOURCE) {
    return;
  }
  const entries = state.logEntries;
  state.homeLogList.replaceChildren();
  if (!entries.length) {
    state.homeLogList.append(createElement("p", "home-logs-empty", t("home.empty_logs")));
    return;
  }
  for (const entry of entries) {
    state.homeLogList.append(buildFriendlyRow(entry));
  }
}

export function appendFriendlyLogs(entries) {
  if (!entries.length) {
    return;
  }
  const stamped = entries.map((entry) => ({ ...entry, receivedAt: entry?.receivedAt ?? Date.now() }));
  state.logEntries.push(...stamped);
  if (state.logEntries.length > MAX_LOG_ENTRIES) {
    state.logEntries.splice(0, state.logEntries.length - MAX_LOG_ENTRIES);
  }
  if (!state.homeLogList || state.homeActivitySource !== HOME_BACKEND_SOURCE) {
    return;
  }
  const emptyState = state.homeLogList.querySelector(".home-logs-empty");
  if (emptyState) {
    emptyState.remove();
  }
  for (const entry of stamped) {
    state.homeLogList.append(buildFriendlyRow(entry));
  }
  while (state.homeLogList.children.length > MAX_LOG_ENTRIES) {
    state.homeLogList.firstElementChild?.remove();
  }
}

export async function clearFriendlyLogs() {
  if (isTauri()) {
    try {
      await invoke("clear_backend_logs");
    } catch (error) {
      showError(error instanceof Error ? error.message : String(error));
      return;
    }
  }

  state.logCursor = 0;
  state.logEntries = [];
  if (state.homeLogList) {
    state.homeLogList.replaceChildren(
      createElement(
        "p",
        "home-logs-empty",
        state.backend.running ? t("home.logs_clean_running") : t("home.logs_clean_stopped"),
      ),
    );
  }
}

export async function clearHomeActivityLogs() {
  const serviceName = getHomeActivitySourceServiceName();
  if (!serviceName) {
    await clearFriendlyLogs();
    return;
  }

  state.servicesLogEntries[serviceName] = [];
  state.servicesLogCursors[serviceName] = 0;
  if (state.homeLogList) {
    state.homeLogList.replaceChildren(createElement("p", "home-logs-empty", t("home.service_logs_cleared")));
  }
}

export function resetFriendlyLogs() {
  state.logCursor = 0;
  state.logEntries = [];
  if (state.homeLogList) {
    state.homeLogList.replaceChildren(
      createElement("p", "home-logs-empty", t("home.empty_logs")),
    );
  }
  refreshHomeActivityView();
}

export async function refreshStatus() {
  if (!isTauri()) {
    return;
  }

  if (state.refreshing) {
    return;
  }

  state.refreshing = true;
  try {
    const status = await invoke("get_backend_status");
    updateStatus(status);
  } catch (error) {
    showError(error instanceof Error ? error.message : String(error));
  } finally {
    state.refreshing = false;
  }
}

export async function startBackend() {
  if (!isTauri()) {
    showError("Esta interfaz necesita ejecutarse dentro de Tauri.");
    return;
  }

  if (state.backend.running) {
    await refreshStatus();
    return;
  }

  clearError();

  try {
    await persistConfig();
    const config = buildConfig();
    const envOverrides = buildEnvOverrides();
    await invoke("start_backend", {
      activeConfig: state.activeConfigName,
      config,
      envOverrides,
    });
    resetFriendlyLogs();
    await refreshStatus();
    await refreshBackendLogs();
  } catch (error) {
    showError(error instanceof Error ? error.message : String(error));
    await refreshStatus();
  }
}

export async function stopBackend() {
  if (!isTauri()) {
    showError("Esta interfaz necesita ejecutarse dentro de Tauri.");
    return;
  }

  clearError();

  try {
    await invoke("stop_backend");
    await refreshStatus();
    await refreshBackendLogs();
  } catch (error) {
    showError(error instanceof Error ? error.message : String(error));
    await refreshStatus();
  }
}

export async function toggleBackend() {
  if (state.backend.running) {
    await stopBackend();
    return;
  }

  await startBackend();
}

// ─── Services ────────────────────────────────────────────────────────────────

export async function refreshServiceList() {
  if (!isTauri()) {
    return;
  }
  try {
    const list = await invoke("list_services");
    state.servicesList = Array.isArray(list) ? list : [];
    updateServiceListUI();
  } catch (error) {
    showError(error instanceof Error ? error.message : String(error));
  }
}

function updateServiceListUI() {
  const container = state.servicesListContainer;
  if (container) {
    const items = container.querySelectorAll(".service-item");
    for (const item of items) {
      const name = item.dataset.serviceName;
      const service = state.servicesList.find((s) => s.name === name);
      if (!service) {
        continue;
      }
      const dot = item.querySelector(".service-status-dot");
      if (dot) {
        dot.classList.toggle("is-running", service.running);
      }
    }
  }

  updateHomeQuickAccessUI();
  refreshHomeActivityView();

  const selected = state.servicesSelectedName;
  if (selected) {
    const service = state.servicesList.find((s) => s.name === selected);
    if (service) {
      updateServiceDetailHeader(service);
    }
  }
}

function updateServiceDetailHeader(service) {
  const btn = state.servicesStatusButton;
  if (!btn) {
    return;
  }
  btn.textContent = service.running ? t("services.stop") : t("services.start");
  btn.classList.toggle("danger", service.running);
  btn.classList.toggle("primary", !service.running);
}

export async function selectService(name) {
  if (state.servicesSelectedName === name) {
    return;
  }
  state.servicesSelectedName = name;
  state.servicesActiveTab = "config";

  if (state.servicesListContainer) {
    const items = state.servicesListContainer.querySelectorAll(".service-item");
    for (const item of items) {
      item.classList.toggle("active", item.dataset.serviceName === name);
    }
  }

  if (!state.servicesConfigs[name]) {
    await loadServiceConfig(name);
  }

  const { renderServiceDetail } = await import("./services.js");
  const service = state.servicesList.find((s) => s.name === name);
  if (service && state.servicesDetailContainer) {
    renderServiceDetail(service, state.servicesConfigs[name] || {});
  }

  stopServiceLogsPolling();
  if (state.servicesActiveTab === "logs") {
    startServiceLogsPolling(name);
  }
}

export async function startService(name) {
  if (!isTauri()) {
    return;
  }
  clearError();
  try {
    const info = await invoke("start_service", { serviceName: name });
    const idx = state.servicesList.findIndex((s) => s.name === name);
    if (idx !== -1) {
      state.servicesList[idx] = info;
    }
    updateServiceListUI();
  } catch (error) {
    showError(error instanceof Error ? error.message : String(error));
  }
}

export async function stopService(name) {
  if (!isTauri()) {
    return;
  }
  clearError();
  try {
    const info = await invoke("stop_service", { serviceName: name });
    const idx = state.servicesList.findIndex((s) => s.name === name);
    if (idx !== -1) {
      state.servicesList[idx] = info;
    }
    updateServiceListUI();
  } catch (error) {
    showError(error instanceof Error ? error.message : String(error));
  }
}

export async function loadServiceConfig(name) {
  if (!isTauri()) {
    return;
  }
  try {
    const config = await invoke("load_service_config", { serviceName: name });
    state.servicesConfigs[name] = config ?? {};
  } catch (error) {
    state.servicesConfigs[name] = {};
    showError(error instanceof Error ? error.message : String(error));
  }
}

export async function saveServiceConfig(name, fields = state.servicesFields) {
  if (!isTauri()) {
    return;
  }
  if (!fields || Object.keys(fields).length === 0) {
    return;
  }
  const config = {};
  for (const [key, control] of Object.entries(fields)) {
    if (control.type === "checkbox") {
      config[key] = control.checked;
    } else {
      const raw = control.value;
      const num = Number(raw);
      config[key] = raw !== "" && !Number.isNaN(num) && control.dataset.isNumber ? num : raw;
    }
  }
  try {
    await invoke("save_service_config", { serviceName: name, config });
    state.servicesConfigs[name] = config;
  } catch (error) {
    showError(error instanceof Error ? error.message : String(error));
  }
}

export async function refreshServiceLogs(name) {
  if (!isTauri() || !name) {
    return;
  }
  try {
    const cursor = state.servicesLogCursors[name] ?? 0;
    const response = await invoke("get_service_logs", { serviceName: name, sinceSeq: cursor });
    const entries = Array.isArray(response?.entries) ? response.entries : [];
    if (typeof response?.nextSeq === "number") {
      state.servicesLogCursors[name] = response.nextSeq;
    }
    if (!state.servicesLogEntries[name]) {
      state.servicesLogEntries[name] = [];
    }
    state.servicesLogEntries[name].push(...entries);
    if (state.servicesLogEntries[name].length > 500) {
      state.servicesLogEntries[name].splice(0, state.servicesLogEntries[name].length - 500);
    }
    appendServiceLogs(name, entries);
    if (entries.length && getHomeActivitySourceServiceName() === name) {
      refreshHomeActivityView();
    }
  } catch {
    // ignore
  }
}

function appendServiceLogs(name, entries) {
  const panel = state.servicesLogsPanel;
  if (!panel || name !== state.servicesSelectedName) {
    return;
  }
  const logList = panel.querySelector(".home-logs-list");
  if (!logList) {
    return;
  }
  const empty = logList.querySelector(".home-logs-empty");
  if (empty && entries.length) {
    empty.remove();
  }
  const atBottom = logList.scrollHeight - logList.scrollTop - logList.clientHeight < 80;
  for (const entry of entries) {
    const row = buildServiceLogRow(entry);
    logList.append(row);
  }
  while (logList.children.length > 500) {
    logList.firstElementChild?.remove();
  }
  if (atBottom) {
    logList.scrollTop = logList.scrollHeight;
  }
}

export function startServiceLogsPolling(name) {
  stopServiceLogsPolling();
  if (!name) {
    return;
  }
  state.servicesLogCursors[name] = state.servicesLogCursors[name] ?? 0;
  state.servicesLogsTimer = setInterval(() => {
    void refreshServiceLogs(name);
  }, 1000);
}

export function stopServiceLogsPolling() {
  if (state.servicesLogsTimer !== null) {
    clearInterval(state.servicesLogsTimer);
    state.servicesLogsTimer = null;
  }
}

export function startServicesRefresh() {
  if (state.servicesRefreshTimer !== null) {
    return;
  }
  state.servicesRefreshTimer = setInterval(() => {
    void refreshServiceList();
  }, 3000);
}

export function stopServicesRefresh() {
  if (state.servicesRefreshTimer !== null) {
    clearInterval(state.servicesRefreshTimer);
    state.servicesRefreshTimer = null;
  }
  stopServiceLogsPolling();
}

export async function refreshBackendLogs() {
  if (!isTauri() || state.logRefreshing) {
    return;
  }

  state.logRefreshing = true;
  try {
    const response = await invoke("get_backend_logs", { sinceSeq: state.logCursor });
    const entries = Array.isArray(response?.entries) ? response.entries : [];
    appendFriendlyLogs(entries);
    if (typeof response?.nextSeq === "number") {
      state.logCursor = response.nextSeq;
    }
  } catch (error) {
    showError(error instanceof Error ? error.message : String(error));
  } finally {
    state.logRefreshing = false;
  }
}
