import { createElement } from "./dom.js";
import { APP_VIEWS } from "./constants.js";
import { t } from "./i18n.js";

export function get(value, path, fallback) {
  const parts = path.split(".");
  let current = value;
  for (const part of parts) {
    if (current == null || typeof current !== "object" || !(part in current)) {
      return fallback;
    }
    current = current[part];
  }
  return current ?? fallback;
}

export function text(value, fallback = "") {
  if (value === null || value === undefined) {
    return fallback;
  }
  return String(value);
}

export function mapping(value) {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value;
  }
  return {};
}

export function fieldValue(input, fallback = "") {
  const raw = text(input.value, "").trim();
  return raw || fallback;
}

export function parseIntField(input, fallback) {
  const value = Number.parseInt(fieldValue(input, String(fallback)), 10);
  if (Number.isNaN(value)) {
    throw new Error(`"${input.dataset.label ?? "Field"}" must be an integer.`);
  }
  return value;
}

export function parseFloatField(input, fallback) {
  const value = Number.parseFloat(fieldValue(input, String(fallback)));
  if (Number.isNaN(value)) {
    throw new Error(`"${input.dataset.label ?? "Field"}" must be a number.`);
  }
  return value;
}

export function parseExpiredIn(input, fallback) {
  const raw = fieldValue(input, fallback === false ? "false" : String(fallback));
  if (raw.toLowerCase() === "false") {
    return false;
  }
  const value = Number.parseInt(raw, 10);
  if (Number.isNaN(value)) {
    throw new Error(`"${input.dataset.label ?? "Field"}" must be an integer or "false".`);
  }
  return value;
}

export function splitLines(input) {
  const raw = fieldValue(input, "");
  if (!raw) {
    return [];
  }
  return raw
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

export function formatLogEntry(entry) {
  const stream = text(entry?.stream, "stdout");
  const rawMessage = text(entry?.message, "").trim();
  const lines = rawMessage.split(/\r?\n/).filter(Boolean);
  const firstLine = lines[0] ?? "";
  let level = "";
  let timestamp = "";
  let message = rawMessage || "Sin mensaje";

  const bracketMatch = firstLine.match(/^\[(DEBUG|INFO|WARNING|ERROR|CRITICAL)\]\s*(.*)$/i);
  if (bracketMatch) {
    level = bracketMatch[1].toUpperCase();
    message = [bracketMatch[2], ...lines.slice(1)].join("\n").trim() || "Sin mensaje";
  } else {
    const isoMatch = firstLine.match(
      /^(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)\s+(DEBUG|INFO|WARNING|ERROR|CRITICAL)\s+(.*)$/i,
    );
    if (isoMatch) {
      timestamp = isoMatch[1];
      level = isoMatch[2].toUpperCase();
      message = [isoMatch[3], ...lines.slice(1)].join("\n").trim() || "Sin mensaje";
    } else {
      const levelMatch = firstLine.match(/^(DEBUG|INFO|WARNING|ERROR|CRITICAL)\s*[:\-]\s*(.*)$/i);
      if (levelMatch) {
        level = levelMatch[1].toUpperCase();
        message = [levelMatch[2], ...lines.slice(1)].join("\n").trim() || "Sin mensaje";
      }
    }
  }

  return {
    stream,
    level,
    timestamp,
    message,
    rawMessage: rawMessage || "Sin mensaje",
  };
}

const CATEGORY_RULES = [
  {
    match: /(capturer?\.?audio|audio\.capture|audio_capture|audio\.service|\baudio\b)/i,
    categoryKey: "Audio",
    icon: "🎙",
    friendlyKey: "logs.audio",
  },
  {
    match: /(capturer?\.?screen|screen\.capture|screen_capture|\bscreen\b|screenshot)/i,
    categoryKey: "Screen",
    icon: "🖥",
    friendlyKey: "logs.screen",
  },
  {
    match: /(processor\.?ocr|\bocr\b)/i,
    categoryKey: "OCR",
    icon: "🔤",
    friendlyKey: "logs.ocr",
  },
  {
    match: /(processor\.?asr|\basr\b|transcri)/i,
    categoryKey: "Transcription",
    icon: "💬",
    friendlyKey: "logs.asr",
  },
  {
    match: /(processor\.?notes|\bnotes?\b|notas?)/i,
    categoryKey: "Notes",
    icon: "📝",
    friendlyKey: "logs.notes",
  },
  {
    match: /(content_filter|content\.filter|\bfilter)/i,
    categoryKey: "Filter",
    icon: "🧹",
    friendlyKey: "logs.filter",
  },
];

function tidyMessage(raw) {
  if (!raw) {
    return "";
  }
  let cleaned = raw.trim();
  cleaned = cleaned.replace(/^[\d T:\-.Z/]{6,}\s+/, "");
  cleaned = cleaned.replace(/^\[(DEBUG|INFO|WARNING|ERROR|CRITICAL)\]\s*/i, "");
  cleaned = cleaned.replace(/^(DEBUG|INFO|WARNING|ERROR|CRITICAL)\s*[:\-]\s*/i, "");
  cleaned = cleaned.replace(/^(\[[^\]]*\]\s*)+/, "");
  cleaned = cleaned.replace(/^[\w\-.]+:\s+/, (match) => {
    if (/\.py|\.ts|\.js|\.rs/.test(match)) {
      return "";
    }
    return match;
  });
  cleaned = cleaned.replace(/\s+File "[^"]+", line \d+.*/g, "");
  if (cleaned.length > 220) {
    cleaned = `${cleaned.slice(0, 217)}…`;
  }
  return cleaned;
}

export function classifyLog(entry) {
  const formatted = formatLogEntry(entry);
  const rawForMatch = `${formatted.rawMessage}`;
  const level = formatted.level || (formatted.stream === "stderr" ? "ERROR" : "INFO");
  const severity = level === "ERROR" || level === "CRITICAL"
    ? "error"
    : level === "WARNING"
      ? "warning"
      : formatted.level
        ? "info"
        : formatted.stream === "stderr"
          ? "warning"
          : "info";

  let category = t("logs.system");
  let icon = "⚙";
  let friendly = tidyMessage(formatted.message) || t("logs.system_event");

  for (const rule of CATEGORY_RULES) {
    if (rule.match.test(rawForMatch)) {
      category = t(rule.categoryKey);
      icon = rule.icon;
      friendly = tidyMessage(formatted.message) || t(rule.friendlyKey);
      break;
    }
  }

  if (severity === "error") {
    icon = "⚠";
  }

  return {
    category,
    icon,
    severity,
    level,
    message: friendly,
    rawMessage: formatted.rawMessage,
    timestamp: formatted.timestamp,
  };
}

export function buildServiceLogRow(entry) {
  const row = createElement("article", `friendly-log-row${entry?.stream === "stderr" ? " severity-warning" : ""}`);
  const icon = createElement("span", "friendly-log-icon", "⚙");
  const body = createElement("div", "friendly-log-body");
  const meta = createElement("div", "friendly-log-meta");
  meta.append(createElement("span", "friendly-log-pill", entry?.stream === "stderr" ? "ERR" : "OUT"));
  body.append(meta, createElement("p", "friendly-log-message", entry?.message ?? ""));
  row.append(icon, body);
  return row;
}

export function formatRelativeTime(ts) {
  const base = ts instanceof Date ? ts : new Date(ts);
  if (Number.isNaN(base.getTime())) {
    return "";
  }
  const diff = Math.max(0, Math.round((Date.now() - base.getTime()) / 1000));
  if (diff < 5) {
    return "ahora";
  }
  if (diff < 60) {
    return `hace ${diff} s`;
  }
  const minutes = Math.round(diff / 60);
  if (minutes < 60) {
    return `hace ${minutes} min`;
  }
  const hours = Math.round(minutes / 60);
  if (hours < 24) {
    return `hace ${hours} h`;
  }
  const days = Math.round(hours / 24);
  return `hace ${days} d`;
}

export function normalizeViewId(viewId) {
  return APP_VIEWS.some((view) => view.id === viewId) ? viewId : APP_VIEWS[0].id;
}

export function readViewFromHash() {
  return normalizeViewId(window.location.hash.replace(/^#/, "").trim());
}

export function normalizeConfigName(name) {
  const trimmed = text(name, "").trim();
  if (!trimmed) {
    return "";
  }
  if (trimmed.includes("/") || trimmed.includes("\\") || trimmed.includes("..")) {
    return "";
  }
  return trimmed.toLowerCase().endsWith(".yaml") || trimmed.toLowerCase().endsWith(".yml")
    ? trimmed
    : `${trimmed}.yaml`;
}

export function displayConfigName(name) {
  const value = text(name, "").trim();
  if (!value) {
    return "profile";
  }
  return value.replace(/\.ya?ml$/i, "");
}

export function setInputValue(input, value) {
  if (!input) {
    return;
  }
  input.value = text(value, "");
}

export function setCheckboxValue(input, value) {
  if (!input) {
    return;
  }
  input.checked = Boolean(value);
}

export function setSelectValue(input, value, fallback = "") {
  if (!input) {
    return;
  }
  input.value = text(value, fallback);
}

export function isNearBottom(element, threshold = 24) {
  return element.scrollHeight - element.scrollTop - element.clientHeight <= threshold;
}

export function formatCaptureDate(ms) {
  if (!ms) return "–";
  const d = new Date(ms);
  if (Number.isNaN(d.getTime())) return "–";
  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(d);
}

export function formatFileSize(bytes) {
  if (!bytes) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function parseFilenameTimestamp(name) {
  const base = name.split(".")[0];
  const m = base.match(/^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})/);
  if (!m) return null;
  return new Date(`${m[1]}-${m[2]}-${m[3]}T${m[4]}:${m[5]}:${m[6]}Z`);
}
