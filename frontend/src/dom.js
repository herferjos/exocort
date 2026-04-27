import { registerStyles } from "./style-registry.js";

registerStyles("dom-primitives", `
  .eyebrow,
  .mini-label {
    margin: 0;
    color: var(--primary);
    font-size: 0.78rem;
    font-weight: 800;
    letter-spacing: 0.16em;
    text-transform: uppercase;
  }

  .section-card {
    padding: 22px;
    border-radius: var(--radius);
    background: var(--panel);
    border: 1px solid var(--border);
    box-shadow: var(--shadow);
    backdrop-filter: blur(14px);
    min-width: 0;
  }

  .section-card[hidden] {
    display: none;
  }

  .section-title {
    margin: 0 0 6px;
    font-size: 1.22rem;
    letter-spacing: -0.02em;
  }

  .section-subtitle {
    margin: 0 0 18px;
    color: var(--muted);
    line-height: 1.5;
  }

  .section-stack {
    display: grid;
    gap: 14px;
  }

  .section-divider {
    height: 1px;
    margin: 4px 0;
    background: var(--border);
  }

  .helper-text {
    margin: 0;
    color: var(--muted);
    line-height: 1.5;
  }

  .field-row {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
  }

  .inline-button {
    padding: 0.7rem 1rem;
    border-radius: 999px;
    color: var(--text);
    background: rgba(255, 255, 255, 0.86);
    border: 1px solid rgba(22, 32, 44, 0.08);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.7);
    cursor: pointer;
    font-weight: 700;
    transition:
      transform 120ms ease,
      background-color 120ms ease,
      border-color 120ms ease,
      box-shadow 120ms ease,
      opacity 120ms ease;
  }

  .inline-button.icon-button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
  }

  .inline-button:hover:not(:disabled) {
    transform: translateY(-1px);
    background: #fff;
    border-color: rgba(22, 32, 44, 0.14);
  }

  .back-button {
    padding: 0.55rem 0.95rem 0.55rem 0.75rem;
    gap: 8px;
    color: var(--muted);
    background: rgba(255, 255, 255, 0.8);
  }

  .back-button:hover:not(:disabled) {
    color: var(--text);
  }

  .back-button svg {
    display: block;
  }

  .back-button-label {
    font-weight: 700;
    font-size: 0.9rem;
  }

  .inline-button.primary {
    color: #fff;
    background: var(--primary);
    border-color: transparent;
    box-shadow: 0 12px 28px rgba(23, 104, 255, 0.24);
  }

  .inline-button.primary:hover:not(:disabled) {
    background: var(--primary-hover);
  }

  .inline-button.secondary {
    color: var(--text);
  }

  .inline-button.danger {
    color: #fff;
    background: var(--danger);
    border-color: transparent;
    box-shadow: 0 12px 28px rgba(219, 76, 66, 0.2);
  }

  .inline-button.danger:hover:not(:disabled) {
    background: var(--danger-hover);
  }

  .inline-button.ghost {
    padding: 0.45rem 0.75rem;
    font-size: 0.84rem;
    background: transparent;
    box-shadow: none;
    border: 1px solid transparent;
    color: var(--muted);
  }

  .inline-button.ghost:hover:not(:disabled) {
    color: var(--text);
    background: rgba(22, 32, 44, 0.04);
    border-color: var(--border);
    transform: none;
  }

  .inline-button.ghost.danger {
    color: var(--danger);
    background: transparent;
    box-shadow: none;
  }

  .inline-button.ghost.danger:hover:not(:disabled) {
    color: #fff;
    background: var(--danger);
    border-color: var(--danger);
  }

  .inline-button.preset-action {
    width: 30px;
    height: 30px;
    min-width: 0;
    padding: 0;
    border-radius: 10px;
    background: transparent;
    border: 1px solid transparent;
    box-shadow: none;
    color: var(--muted);
  }

  .inline-button.preset-action:hover:not(:disabled) {
    color: var(--text);
    background: rgba(22, 32, 44, 0.06);
    border-color: transparent;
    transform: none;
  }

  .inline-button.preset-action.danger {
    color: var(--muted);
    background: transparent;
    box-shadow: none;
  }

  .inline-button.preset-action.danger:hover:not(:disabled) {
    color: var(--danger);
    background: var(--danger-soft);
  }

  .inline-button.preset-action svg {
    display: block;
  }

  .inline-button:disabled {
    cursor: not-allowed;
    opacity: 0.6;
  }

  .status-pill {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-height: 30px;
    width: fit-content;
    padding: 0.34rem 0.8rem;
    border-radius: 999px;
    border: 1px solid transparent;
    color: var(--muted);
    background: rgba(22, 32, 44, 0.06);
    font-size: 0.74rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .status-pill.is-running {
    color: #fff;
    background: var(--success);
    box-shadow: 0 8px 20px rgba(15, 159, 107, 0.28);
  }

  .preset-pill {
    display: inline-flex;
    align-items: center;
    min-height: 30px;
    padding: 0.28rem 0.8rem;
    border-radius: 999px;
    font-size: 0.82rem;
    font-weight: 600;
    color: var(--primary);
    background: var(--primary-soft);
  }

  .inline-button:focus-visible {
    outline: 3px solid var(--focus);
    outline-offset: 2px;
  }

  @media (max-width: 640px) {
    .section-card {
      border-radius: 20px;
    }

    .inline-button {
      width: 100%;
    }

    .inline-button.preset-action {
      width: auto;
    }
  }
`);

export function createElement(tag, className, textContent) {
  const element = document.createElement(tag);
  if (className) {
    element.className = className;
  }
  if (textContent !== undefined) {
    element.textContent = textContent;
  }
  return element;
}

export function applyTooltip(element, tooltip) {
  if (tooltip) {
    element.title = tooltip;
  }
  return element;
}

export function createSection(title, subtitle, content, tooltip = subtitle) {
  const card = createElement("section", "section-card");
  const heading = createElement("h2", "section-title", title);
  const description = createElement("p", "section-subtitle", subtitle);
  const stack = createElement("div", "section-stack");
  applyTooltip(card, tooltip);
  applyTooltip(heading, tooltip);
  applyTooltip(description, tooltip);
  if (Array.isArray(content)) {
    stack.append(...content);
  } else if (content) {
    stack.append(content);
  }
  card.append(heading, description, stack);
  return card;
}

export function createPageIntro({ eyebrow, title, subtitle, actions = [], compact = false }) {
  const intro = createElement("section", `page-intro${compact ? " compact" : ""}`);
  const copy = createElement("div", "page-intro-copy");

  if (eyebrow) {
    copy.append(createElement("p", "eyebrow", eyebrow));
  }

  copy.append(createElement("h1", "page-title", title));

  if (subtitle) {
    copy.append(createElement("p", "page-subtitle", subtitle));
  }

  intro.append(copy);

  if (actions.length) {
    const actionRow = createElement("div", "page-intro-actions");
    actionRow.append(...actions);
    intro.append(actionRow);
  }

  return intro;
}

export function createFieldRow(fields) {
  const row = createElement("div", "field-row");
  row.append(...fields);
  return row;
}

export function createDivider() {
  return createElement("div", "section-divider");
}

export function createSubsectionLabel(label, tooltip = label) {
  const element = createElement("p", "helper-text", label);
  return applyTooltip(element, tooltip);
}

export function button(label, className, onClick) {
  const element = createElement("button", `inline-button ${className}`.trim(), label);
  element.type = "button";
  element.addEventListener("click", onClick);
  return element;
}

export function iconButton(icon, label, className, onClick) {
  const element = createElement("button", `inline-button icon-button ${className}`.trim());
  element.type = "button";
  element.setAttribute("aria-label", label);
  element.title = label;
  if (typeof icon === "string") {
    element.textContent = icon;
  } else if (icon instanceof Element) {
    element.append(icon);
  }
  element.addEventListener("click", onClick);
  return element;
}
