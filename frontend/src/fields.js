import { createElement, applyTooltip } from "./dom.js";
import { scheduleConfigPersist, persistConfig } from "./actions.js";
import { state } from "./state.js";
import { registerStyles } from "./style-registry.js";

registerStyles("field-controls", `
  .field {
    display: grid;
    gap: 6px;
    min-width: 0;
    flex: 1 1 220px;
  }

  .field-label {
    font-size: 0.92rem;
    font-weight: 700;
  }

  .field-control,
  .textarea-control,
  .select-control {
    width: 100%;
    padding: 0.78rem 0.9rem;
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 14px;
    background: var(--panel-strong);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.5);
  }

  .textarea-control {
    resize: vertical;
    min-height: 104px;
    line-height: 1.45;
  }

  .toggle-field {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    padding: 8px 0;
    font-weight: 600;
  }

  .toggle-field input {
    width: 18px;
    height: 18px;
  }

  .field-control:focus-visible,
  .textarea-control:focus-visible,
  .select-control:focus-visible {
    outline: 3px solid var(--focus);
    outline-offset: 2px;
  }
`);

function registerField(name, input) {
  state.fields[name] = input;
  input.addEventListener("input", scheduleConfigPersist);
  input.addEventListener("change", () => {
    void persistConfig();
  });
  return input;
}

export function createTextField({
  name,
  label,
  value = "",
  placeholder = "",
  multiline = false,
  rows = 3,
  tooltip = label,
}) {
  const wrapper = createElement("label", "field");
  const caption = createElement("span", "field-label", label);
  const control = multiline ? document.createElement("textarea") : document.createElement("input");

  control.className = multiline ? "textarea-control" : "field-control";
  if (!multiline) {
    control.type = "text";
  }
  control.value = String(value ?? "");
  control.placeholder = placeholder;
  control.dataset.label = label;

  if (multiline) {
    control.rows = rows;
  }

  applyTooltip(wrapper, tooltip);
  applyTooltip(caption, tooltip);
  applyTooltip(control, tooltip);
  wrapper.append(caption, control);
  if (name) {
    void registerField(name, control);
  }
  return { wrapper, control };
}

export function createSelectField({ name, label, value = "", options = [], tooltip = label }) {
  const wrapper = createElement("label", "field");
  const caption = createElement("span", "field-label", label);
  const control = document.createElement("select");
  control.className = "select-control";
  control.dataset.label = label;

  for (const option of options) {
    const item = document.createElement("option");
    item.value = typeof option === "object" ? option.value : option;
    item.textContent = typeof option === "object" ? option.label : option;
    control.append(item);
  }

  control.value = String(value ?? (typeof options[0] === "object" ? options[0]?.value ?? "" : options[0] ?? ""));
  applyTooltip(wrapper, tooltip);
  applyTooltip(caption, tooltip);
  applyTooltip(control, tooltip);
  wrapper.append(caption, control);
  if (name) {
    void registerField(name, control);
  }
  return { wrapper, control };
}

export function createToggleField({ name, label, checked = false, tooltip = label }) {
  const wrapper = createElement("label", "toggle-field");
  const control = document.createElement("input");
  control.type = "checkbox";
  control.checked = Boolean(checked);
  control.dataset.label = label;
  const caption = createElement("span", null, label);

  applyTooltip(wrapper, tooltip);
  applyTooltip(control, tooltip);
  applyTooltip(caption, tooltip);
  wrapper.append(control, caption);
  if (name) {
    void registerField(name, control);
  }
  return { wrapper, control };
}
