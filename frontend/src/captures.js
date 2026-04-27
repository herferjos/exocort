import { invoke, isTauri } from "@tauri-apps/api/core";
import { createElement, iconButton } from "./dom.js";
import { createIcon } from "./icons.js";
import { t } from "./i18n.js";
import { registerStyles } from "./style-registry.js";
import { state } from "./state.js";
import { confirmAction } from "./actions.js";
import { formatCaptureDate, formatFileSize } from "./utils.js";

const CAPTURE_TABS = ["screen", "audio", "notes"];
const CAPTURES_REFRESH_INTERVAL_MS = 4000;
let pendingCapturesRefresh = false;
let pendingCapturesForce = false;

registerStyles("captures-page", `
  .captures-view {
    display: grid;
    gap: 18px;
    padding: 26px;
    border-radius: var(--radius);
    background: var(--panel);
    border: 1px solid var(--border);
    box-shadow: var(--shadow);
  }

  .captures-header-copy {
    display: grid;
    gap: 6px;
  }

  .captures-header-row {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 16px;
  }

  .captures-title {
    margin: 0;
    font-size: clamp(1.4rem, 2.5vw, 1.9rem);
    font-weight: 700;
    letter-spacing: -0.02em;
  }

  .captures-subtitle {
    margin: 0;
    color: var(--muted);
    line-height: 1.5;
  }

  .captures-tabs {
    display: flex;
    gap: 4px;
    overflow-x: auto;
    border-bottom: 1px solid var(--border);
  }

  .captures-tab {
    padding: 0.7rem 1rem;
    border: 0;
    border-bottom: 2px solid transparent;
    background: transparent;
    color: var(--muted);
    cursor: pointer;
    white-space: nowrap;
    font-size: 0.95rem;
    font-weight: 700;
    transition: color 120ms ease, border-color 120ms ease;
  }

  .captures-tab:hover {
    color: var(--text);
  }

  .captures-tab.active {
    color: var(--primary);
    border-color: var(--primary);
  }

  .captures-list {
    display: grid;
    gap: 14px;
  }

  .captures-empty {
    margin: 0;
    padding: 32px 20px;
    color: var(--muted);
    text-align: center;
    font-size: 0.92rem;
    border: 1px dashed var(--border);
    border-radius: 18px;
    background: rgba(255, 255, 255, 0.5);
  }

  .activity-card {
    overflow: hidden;
    border-radius: 22px;
    background: linear-gradient(180deg, rgba(255, 255, 255, 0.94), rgba(247, 250, 252, 0.95));
    border: 1px solid var(--border);
    box-shadow: var(--shadow-soft);
  }

  .activity-card.is-blocked {
    background: linear-gradient(180deg, rgba(255, 245, 245, 0.96), rgba(255, 255, 255, 0.94));
    border-color: rgba(219, 76, 66, 0.24);
  }

  .activity-card-header {
    width: 100%;
    padding: 18px 20px;
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
    gap: 12px;
  }

  .activity-card-header.is-compact {
    padding: 14px 16px;
  }

  .activity-card-toggle-shell {
    width: 100%;
    padding: 0;
    display: grid;
    gap: 12px;
    border: 0;
    background: transparent;
    text-align: left;
    cursor: pointer;
  }

  .activity-card-toggle-shell:hover {
    color: var(--text);
  }

  .activity-card-toggle-row {
    display: flex;
    align-items: flex-start;
    gap: 14px;
    min-width: 0;
  }

  .activity-card-toggle-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    width: 18px;
    height: 18px;
    margin-top: 10px;
    color: var(--muted);
  }

  .activity-card-main {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    min-width: 0;
  }

  .activity-card-icon {
    width: 42px;
    height: 42px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    border-radius: 14px;
    background: rgba(23, 104, 255, 0.1);
    color: var(--primary);
    font-size: 1.15rem;
  }

  .activity-card-copy {
    display: grid;
    gap: 6px;
    min-width: 0;
  }

  .activity-card-title {
    margin: 0;
    font-size: 1rem;
    font-weight: 700;
    letter-spacing: -0.01em;
  }

  .activity-card-subtitle {
    margin: 0;
    color: var(--muted);
    font-size: 0.9rem;
  }

  .activity-card-chevron {
    flex-shrink: 0;
    color: var(--muted);
  }

  .activity-card-chevron svg {
    display: block;
  }

  .activity-card-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .activity-card-delete {
    flex-shrink: 0;
    align-self: start;
  }

  .activity-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    min-height: 30px;
    padding: 0.3rem 0.72rem;
    border-radius: 999px;
    background: rgba(22, 32, 44, 0.06);
    color: var(--muted);
    font-size: 0.76rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }

  .activity-pill.status-processed {
    background: rgba(15, 159, 107, 0.12);
    color: var(--success);
  }

  .activity-pill.status-blocked_sensitive {
    background: rgba(219, 76, 66, 0.12);
    color: var(--danger);
  }

  .activity-pill.status-pending {
    background: rgba(234, 179, 8, 0.12);
    color: var(--warning);
  }

  .activity-card-body {
    display: grid;
    gap: 18px;
    padding: 0 20px 20px;
  }

  .activity-card-actions {
    display: flex;
    justify-content: flex-end;
  }

  .activity-section {
    display: grid;
    gap: 10px;
  }

  .activity-section-label {
    margin: 0;
    color: var(--primary);
    font-size: 0.8rem;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }

  .activity-file-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 14px 16px;
    border-radius: 16px;
    background: var(--panel-muted);
    border: 1px solid var(--border);
  }

  .activity-file-copy {
    display: grid;
    gap: 4px;
    min-width: 0;
  }

  .activity-file-name,
  .activity-file-meta,
  .activity-unavailable,
  .activity-note-empty,
  .activity-inline-message {
    margin: 0;
  }

  .activity-file-name {
    font-size: 0.94rem;
    font-weight: 700;
    word-break: break-word;
  }

  .activity-file-meta,
  .activity-unavailable,
  .activity-note-empty,
  .activity-inline-message {
    color: var(--muted);
    font-size: 0.88rem;
    line-height: 1.5;
  }

  .activity-media-button {
    width: auto;
    min-width: 0;
    padding: 0.65rem 0.95rem;
    border-radius: 999px;
    border: 1px solid var(--border-strong);
    background: #fff;
    color: var(--text);
    cursor: pointer;
    font-weight: 700;
    white-space: nowrap;
  }

  .activity-audio-player {
    width: 100%;
  }

  .activity-text-box,
  .activity-note-box,
  .activity-blocked-box,
  .activity-related-list {
    display: grid;
    gap: 10px;
    padding: 16px;
    border-radius: 18px;
    border: 1px solid var(--border);
    background: var(--panel-muted);
  }

  .activity-blocked-box {
    background: var(--danger-soft);
    border-color: rgba(219, 76, 66, 0.22);
  }

  .activity-text-body,
  .activity-note-body {
    margin: 0;
    line-height: 1.65;
    white-space: pre-wrap;
    word-break: break-word;
  }

  .activity-note-list {
    display: grid;
    gap: 10px;
  }

  .activity-note-card {
    overflow: hidden;
    border-radius: 16px;
    border: 1px solid var(--border);
    background: rgba(255, 255, 255, 0.78);
  }

  .activity-note-title-wrap {
    width: 100%;
    display: grid;
    gap: 4px;
    min-width: 0;
  }

  .activity-note-title {
    margin: 0;
    font-size: 0.96rem;
    font-weight: 700;
    word-break: break-word;
  }

  .activity-note-meta {
    margin: 0;
    color: var(--muted);
    font-size: 0.84rem;
  }

  .activity-note-panel {
    display: grid;
    gap: 12px;
    padding: 0 16px 16px;
  }

  .activity-related-items {
    display: grid;
    gap: 8px;
  }

  .activity-related-link {
    width: 100%;
    padding: 13px 15px;
    display: grid;
    gap: 4px;
    border-radius: 14px;
    border: 1px solid var(--border);
    background: rgba(255, 255, 255, 0.82);
    color: var(--text);
    text-align: left;
    cursor: pointer;
    transition:
      background-color 120ms ease,
      border-color 120ms ease,
      transform 120ms ease;
  }

  .activity-related-link:hover {
    transform: translateY(-1px);
    background: #fff;
    border-color: var(--border-strong);
  }

  .activity-related-link-title,
  .activity-related-link-meta {
    margin: 0;
  }

  .activity-related-link-title {
    font-size: 0.9rem;
    font-weight: 700;
    word-break: break-word;
  }

  .activity-related-link-meta {
    color: var(--muted);
    font-size: 0.82rem;
    line-height: 1.4;
  }

  .captures-modal {
    position: fixed;
    inset: 0;
    z-index: 40;
    display: grid;
    place-items: center;
    padding: 28px;
    background: rgba(15, 23, 42, 0.52);
    backdrop-filter: blur(8px);
  }

  .captures-modal[hidden] {
    display: none;
  }

  .captures-modal-dialog {
    width: min(980px, 100%);
    max-height: calc(100vh - 56px);
    overflow: auto;
    display: grid;
    gap: 14px;
    padding: 18px;
    border-radius: 24px;
    background: #fff;
    box-shadow: 0 28px 80px rgba(15, 23, 42, 0.28);
  }

  .captures-modal-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }

  .captures-modal-title {
    margin: 0;
    font-size: 1rem;
    font-weight: 700;
  }

  .captures-modal-close {
    width: auto;
    min-width: 0;
    padding: 0.55rem 0.85rem;
    border-radius: 999px;
    border: 1px solid var(--border);
    background: rgba(22, 32, 44, 0.04);
    cursor: pointer;
    font-weight: 700;
  }

  .captures-modal-image {
    display: block;
    width: 100%;
    border-radius: 18px;
    border: 1px solid var(--border);
  }

  .md-h1 { margin: 0; font-size: 1.3rem; font-weight: 700; letter-spacing: -0.01em; }
  .md-h2 { margin: 0; font-size: 1.1rem; font-weight: 700; }
  .md-h3 { margin: 0; font-size: 0.98rem; font-weight: 700; color: var(--muted); }
  .md-p { margin: 0; }
  .md-list { margin: 0; padding-left: 20px; display: grid; gap: 4px; }
  .md-li { line-height: 1.55; }
  .md-hr { border: 0; border-top: 1px solid var(--border); margin: 4px 0; }

  @media (max-width: 860px) {
    .activity-file-row,
    .captures-modal-top,
    .activity-card-toggle-row {
      grid-template-columns: 1fr;
    }

    .activity-file-row,
    .activity-card-toggle-row {
      display: grid;
    }

    .captures-modal {
      padding: 16px;
    }
  }
`);

function mediaKindLabel(kind) {
  return kind === "audio" ? t("captures.kind_audio") : t("captures.kind_screen");
}

function mediaKindIcon(kind) {
  return kind === "audio" ? "🎙" : "🖥";
}

function statusLabel(status) {
  if (status === "blocked_sensitive") return t("captures.kind_blocked");
  if (status === "processed") return t("captures.processed");
  return t("captures.pending_processing");
}

function mediaMimeFromName(name = "") {
  const value = name.toLowerCase();
  if (value.endsWith(".mp3")) return "audio/mpeg";
  if (value.endsWith(".m4a")) return "audio/mp4";
  if (value.endsWith(".wav")) return "audio/wav";
  if (value.endsWith(".jpg") || value.endsWith(".jpeg")) return "image/jpeg";
  if (value.endsWith(".webp")) return "image/webp";
  return "image/png";
}

function displayName(fileName = "") {
  return fileName
    .replace(/\.sensitive\.json$/i, "")
    .replace(/\.json$/i, "")
    .replace(/\.(md|wav|mp3|m4a|png|jpe?g|webp)$/i, "");
}

function setFilter(filter) {
  state.capturesFilter = filter;
  for (const tabBtn of state.capturesTabButtons) {
    tabBtn.classList.toggle("active", tabBtn.dataset.tab === filter);
  }
  renderCapturesList();
}

function toggleExpandedItem(id) {
  if (state.capturesExpandedItems.has(id)) {
    state.capturesExpandedItems.delete(id);
  } else {
    state.capturesExpandedItems.add(id);
  }
  renderCapturesList({ refresh: true });
}

function toggleExpandedNote(noteId, notePath) {
  if (state.capturesExpandedNotes.has(noteId)) {
    state.capturesExpandedNotes.delete(noteId);
    renderCapturesList({ refresh: true });
    return;
  }
  state.capturesExpandedNotes.add(noteId);
  renderCapturesList({ refresh: true });
  void ensureNoteLoaded(notePath);
}

function cacheValue(map, key, nextValue) {
  map.set(key, nextValue);
  return nextValue;
}

function entrySignature(entry) {
  return JSON.stringify(entry);
}

function getOrderedEntries(filter) {
  return state.capturesOrderedEntries[filter] || [];
}

function getEntryId(filter, entry) {
  return filter === "notes" ? entry.id : entry.id;
}

function mergeVisibleOrder(filter, entries, { force = false } = {}) {
  const incomingIds = entries.map((entry) => getEntryId(filter, entry));
  if (force || !state.capturesVisibleOrder[filter].length) {
    state.capturesVisibleOrder[filter] = incomingIds;
    return incomingIds;
  }

  const incomingSet = new Set(incomingIds);
  const retainedIds = state.capturesVisibleOrder[filter].filter((id) => incomingSet.has(id));
  const retainedSet = new Set(retainedIds);
  const newIds = incomingIds.filter((id) => !retainedSet.has(id) && !state.capturesSeenIds.has(id));
  const newIdSet = new Set(newIds);
  const appendedIds = incomingIds.filter((id) => !retainedSet.has(id) && !newIdSet.has(id));
  const mergedIds = [...newIds, ...retainedIds, ...appendedIds];
  state.capturesVisibleOrder[filter] = mergedIds;
  return mergedIds;
}

function invalidateEntryCaches(previousEntry, nextEntry, filter) {
  if (!previousEntry) {
    return;
  }

  if (filter === "notes") {
    if (previousEntry.path !== nextEntry.path || previousEntry.modifiedMs !== nextEntry.modifiedMs) {
      if (previousEntry.path) state.capturesNoteCache.delete(previousEntry.path);
      if (nextEntry.path) state.capturesNoteCache.delete(nextEntry.path);
    }
    return;
  }

  const previousSource = previousEntry.sourceFile;
  const nextSource = nextEntry.sourceFile;
  if (
    previousSource?.path !== nextSource?.path ||
    previousSource?.modifiedMs !== nextSource?.modifiedMs
  ) {
    if (previousSource?.path) state.capturesMediaCache.delete(previousSource.path);
    if (nextSource?.path) state.capturesMediaCache.delete(nextSource.path);
  }
}

function applyIncomingCaptures(result, { force = false } = {}) {
  const incomingItems = Array.isArray(result?.items) ? result.items : [];
  const incomingNotes = Array.isArray(result?.notes) ? result.notes : [];
  const nextSnapshots = new Map();

  for (const item of incomingItems) {
    const previous = state.capturesEntrySnapshot.get(item.id);
    invalidateEntryCaches(previous, item, item.kind);
    nextSnapshots.set(item.id, item);
  }
  for (const note of incomingNotes) {
    const previous = state.capturesEntrySnapshot.get(note.id);
    invalidateEntryCaches(previous, note, "notes");
    nextSnapshots.set(note.id, note);
  }

  const screenItems = incomingItems.filter((item) => item.kind === "screen");
  const audioItems = incomingItems.filter((item) => item.kind === "audio");
  const notes = incomingNotes;

  const orderedScreenIds = mergeVisibleOrder("screen", screenItems, { force });
  const orderedAudioIds = mergeVisibleOrder("audio", audioItems, { force });
  const orderedNoteIds = mergeVisibleOrder("notes", notes, { force });

  const screenMap = new Map(screenItems.map((item) => [item.id, item]));
  const audioMap = new Map(audioItems.map((item) => [item.id, item]));
  const noteMap = new Map(notes.map((note) => [note.id, note]));

  state.capturesOrderedEntries = {
    screen: orderedScreenIds.map((id) => screenMap.get(id)).filter(Boolean),
    audio: orderedAudioIds.map((id) => audioMap.get(id)).filter(Boolean),
    notes: orderedNoteIds.map((id) => noteMap.get(id)).filter(Boolean),
  };
  state.capturesData = {
    items: [...state.capturesOrderedEntries.screen, ...state.capturesOrderedEntries.audio],
    notes: state.capturesOrderedEntries.notes,
  };
  state.capturesEntrySnapshot = nextSnapshots;

  for (const id of nextSnapshots.keys()) {
    state.capturesSeenIds.add(id);
  }
}

function getItemPaths(item) {
  const paths = [];
  if (item.sourceFile?.path) paths.push(item.sourceFile.path);
  if (item.processed?.path) paths.push(item.processed.path);
  return paths;
}

function getVisiblePaths() {
  if (state.capturesFilter === "notes") {
    return getOrderedEntries("notes").map((note) => note.path);
  }
  return getOrderedEntries(state.capturesFilter).flatMap((item) => getItemPaths(item));
}

function forgetPaths(paths) {
  for (const path of paths) {
    state.capturesMediaCache.delete(path);
    state.capturesNoteCache.delete(path);
  }
}

function pruneDeletedPaths(paths) {
  if (!paths.length) {
    return;
  }

  const deleted = new Set(paths);
  state.capturesData = {
    items: (state.capturesData.items || []).filter((item) => {
      return !deleted.has(item.sourceFile?.path) && !deleted.has(item.processed?.path);
    }),
    notes: (state.capturesData.notes || []).filter((note) => !deleted.has(note.path)),
  };
  state.capturesOrderedEntries = {
    screen: getOrderedEntries("screen").filter(
      (item) => !deleted.has(item.sourceFile?.path) && !deleted.has(item.processed?.path),
    ),
    audio: getOrderedEntries("audio").filter(
      (item) => !deleted.has(item.sourceFile?.path) && !deleted.has(item.processed?.path),
    ),
    notes: getOrderedEntries("notes").filter((note) => !deleted.has(note.path)),
  };
  reconcileStateWithData();
  renderCapturesList();
  renderModal();
}

async function deletePaths(paths) {
  if (!paths.length) return;
  if (!confirmAction(paths.length === 1 ? t("captures.delete_confirm_item") : t("captures.delete_confirm_section"))) {
    return;
  }
  try {
    await invoke("delete_activity_paths", { paths });
    forgetPaths(paths);
    pruneDeletedPaths(paths);
    await loadCaptures({ silent: true, force: true });
  } catch (error) {
    window.alert(error instanceof Error ? error.message : String(error));
  }
}

async function ensureMediaLoaded(file) {
  if (!file?.path) return null;
  const cached = state.capturesMediaCache.get(file.path);
  if (cached?.status === "loaded") return cached.data;
  if (cached?.status === "loading") return null;

  cacheValue(state.capturesMediaCache, file.path, { status: "loading", data: null, error: "" });
  try {
    const data = await invoke("read_file_as_base64", { filePath: file.path });
    cacheValue(state.capturesMediaCache, file.path, { status: "loaded", data, error: "" });
  } catch (error) {
    cacheValue(state.capturesMediaCache, file.path, {
      status: "error",
      data: null,
      error: error instanceof Error ? error.message : String(error),
    });
  }
  renderCapturesList({ refresh: true });
  renderModal();
  return state.capturesMediaCache.get(file.path)?.data ?? null;
}

async function ensureNoteLoaded(path) {
  if (!path) return "";
  const cached = state.capturesNoteCache.get(path);
  if (cached?.status === "loaded") return cached.data;
  if (cached?.status === "loading") return "";

  cacheValue(state.capturesNoteCache, path, { status: "loading", data: "", error: "" });
  try {
    const data = await invoke("read_text_file", { filePath: path });
    cacheValue(state.capturesNoteCache, path, { status: "loaded", data, error: "" });
  } catch (error) {
    cacheValue(state.capturesNoteCache, path, {
      status: "error",
      data: "",
      error: error instanceof Error ? error.message : String(error),
    });
  }
  renderCapturesList({ refresh: true });
  return state.capturesNoteCache.get(path)?.data ?? "";
}

function openImageModal(file, title) {
  if (!file?.path) return;
  state.capturesModalPath = file.path;
  state.capturesModalTitle = title;
  renderModal();
  void ensureMediaLoaded(file);
}

function closeImageModal() {
  state.capturesModalPath = "";
  state.capturesModalTitle = "";
  renderModal();
}

function renderModal() {
  const modal = state.capturesModal;
  const heading = state.capturesModalHeading;
  const image = state.capturesModalImage;
  if (!modal || !heading || !image) return;

  if (!state.capturesModalPath) {
    modal.hidden = true;
    heading.textContent = "";
    image.removeAttribute("src");
    return;
  }

  modal.hidden = false;
  heading.textContent = state.capturesModalTitle;
  const cached = state.capturesMediaCache.get(state.capturesModalPath);
  if (cached?.status === "loaded") {
    image.src = `data:${mediaMimeFromName(state.capturesModalPath)};base64,${cached.data}`;
    image.alt = t("captures.screenshot_alt");
  } else if (cached?.status === "error") {
    image.removeAttribute("src");
  } else {
    image.removeAttribute("src");
  }
}

function buildFileRow(label, file, availableText, action = null) {
  const row = createElement("div", "activity-file-row");
  const copy = createElement("div", "activity-file-copy");
  copy.append(
    createElement("p", "activity-section-label", label),
    createElement("p", "activity-file-name", file?.name ? displayName(file.name) : t("captures.not_available")),
    createElement(
      "p",
      "activity-file-meta",
      file ? `${formatFileSize(file.sizeBytes)} · ${formatCaptureDate(file.modifiedMs)}` : availableText,
    ),
  );
  row.append(copy);
  if (action) {
    row.append(action);
  }
  return row;
}

function renderMarkdown(text, container) {
  const lines = text.split("\n");
  let listEl = null;

  const flushList = () => {
    if (listEl) {
      container.append(listEl);
      listEl = null;
    }
  };

  for (const line of lines) {
    if (line.startsWith("### ")) {
      flushList();
      container.append(createElement("h3", "md-h3", line.slice(4)));
    } else if (line.startsWith("## ")) {
      flushList();
      container.append(createElement("h2", "md-h2", line.slice(3)));
    } else if (line.startsWith("# ")) {
      flushList();
      container.append(createElement("h1", "md-h1", line.slice(2)));
    } else if (line.startsWith("- ") || line.startsWith("* ")) {
      if (!listEl) listEl = createElement("ul", "md-list");
      listEl.append(createElement("li", "md-li", line.slice(2)));
    } else if (line.trim() === "---") {
      flushList();
      container.append(createElement("hr", "md-hr"));
    } else if (line.trim() === "") {
      flushList();
    } else {
      flushList();
      container.append(createElement("p", "md-p", line));
    }
  }
  flushList();
}

function escapeSelectorValue(value) {
  if (window.CSS?.escape) {
    return window.CSS.escape(value);
  }
  return String(value).replace(/["\\]/g, "\\$&");
}

function revealEntry(selector) {
  window.requestAnimationFrame(() => {
    const target = state.capturesList?.querySelector(selector);
    if (!target) {
      return;
    }
    target.scrollIntoView({ behavior: "smooth", block: "center" });
    target.querySelector(".activity-card-toggle-shell")?.focus({ preventScroll: true });
  });
}

function openRelatedNote(note) {
  state.capturesExpandedNotes.add(note.id);
  setFilter("notes");
  void ensureNoteLoaded(note.path);
  revealEntry(`[data-note-id="${escapeSelectorValue(note.id)}"]`);
}

function findItemById(itemId) {
  return (state.capturesData.items || []).find((item) => item.id === itemId) ?? null;
}

function buildItemRefTitle(itemRef) {
  const item = findItemById(itemRef.id);
  if (item?.sourceFile?.name) {
    return displayName(item.sourceFile.name);
  }
  if (item?.processed?.name) {
    return displayName(item.processed.name);
  }
  return `${mediaKindLabel(itemRef.kind)} · ${formatCaptureDate(itemRef.capturedMs)}`;
}

function openRelatedItem(itemRef) {
  state.capturesExpandedItems.add(itemRef.id);
  setFilter(itemRef.kind);
  revealEntry(`[data-item-id="${escapeSelectorValue(itemRef.id)}"]`);
}

function buildRelatedLink({ title, meta, onClick, ariaLabel }) {
  const button = createElement("button", "activity-related-link");
  button.type = "button";
  button.setAttribute("aria-label", ariaLabel);
  button.addEventListener("click", onClick);
  button.append(
    createElement("p", "activity-related-link-title", title),
    createElement("p", "activity-related-link-meta", meta),
  );
  return button;
}

function buildRelatedNotesList(relatedNotes) {
  const wrap = createElement("div", "activity-related-items");
  for (const note of relatedNotes) {
    wrap.append(
      buildRelatedLink({
        title: note.title,
        meta: formatCaptureDate(note.modifiedMs),
        ariaLabel: t("captures.open_related_note", { title: note.title }),
        onClick: () => openRelatedNote(note),
      }),
    );
  }
  return wrap;
}

function buildRelatedItemsList(items) {
  const wrap = createElement("div", "activity-related-items");
  for (const item of items) {
    const itemTitle = buildItemRefTitle(item);
    wrap.append(
      buildRelatedLink({
        title: itemTitle,
        meta: `${mediaKindLabel(item.kind)} · ${formatCaptureDate(item.capturedMs)}`,
        ariaLabel: t("captures.open_related_item", { title: itemTitle }),
        onClick: () => openRelatedItem(item),
      }),
    );
  }
  return wrap;
}

function buildExpandableHeader({ expanded, content, onToggle, onDelete, deleteLabel, compact = false }) {
  const header = createElement("div", `activity-card-header${compact ? " is-compact" : ""}`);
  const toggle = createElement("button", "activity-card-toggle-shell");
  toggle.type = "button";
  toggle.addEventListener("click", onToggle);

  const row = createElement("div", "activity-card-toggle-row");
  const toggleIcon = createElement("span", "activity-card-toggle-icon");
  toggleIcon.append(createIcon(expanded ? "chevronUp" : "chevronDown", 16));
  row.append(toggleIcon, content);
  toggle.append(row);

  const deleteButton = iconButton(
    createIcon("trash", 16),
    deleteLabel,
    "preset-action danger activity-card-delete",
    async (event) => {
      event.stopPropagation();
      await onDelete();
    },
  );

  header.append(toggle, deleteButton);
  return header;
}

function buildNoteCard(note) {
  const expanded = state.capturesExpandedNotes.has(note.id);
  const card = createElement("article", "activity-note-card");
  card.dataset.noteId = note.id;

  const titleWrap = createElement("div", "activity-note-title-wrap");
  titleWrap.append(
    createElement("p", "activity-note-title", note.title),
    createElement("p", "activity-note-meta", formatCaptureDate(note.modifiedMs)),
  );
  card.append(
    buildExpandableHeader({
      expanded,
      compact: true,
      content: titleWrap,
      deleteLabel: t("captures.delete_item"),
      onToggle: () => toggleExpandedNote(note.id, note.path),
      onDelete: () => deletePaths([note.path]),
    }),
  );

  if (!expanded) {
    return card;
  }

  const panel = createElement("div", "activity-note-panel");
  const cached = state.capturesNoteCache.get(note.path);
  if (cached?.status === "loaded") {
    const body = createElement("div", "activity-note-box activity-note-body");
    renderMarkdown(cached.data, body);
    panel.append(body);
  } else if (cached?.status === "error") {
    panel.append(createElement("p", "activity-inline-message", `${t("captures.error_load")}: ${cached.error}`));
  } else {
    if (!cached) {
      void ensureNoteLoaded(note.path);
    }
    panel.append(createElement("p", "activity-inline-message", t("captures.loading_note")));
  }

  if (Array.isArray(note.relatedItems) && note.relatedItems.length) {
    panel.append(
      createElement("p", "activity-section-label", t("captures.related_items")),
      buildRelatedItemsList(note.relatedItems),
    );
  } else {
    panel.append(createElement("p", "activity-note-empty", t("captures.note_empty")));
  }

  card.append(panel);
  return card;
}

function buildRelatedNotesSection(item) {
  const section = createElement("section", "activity-section");
  const box = createElement("div", "activity-related-list");
  box.append(createElement("p", "activity-section-label", t("captures.related_notes")));
  if (!item.relatedNotes?.length) {
    box.append(createElement("p", "activity-note-empty", t("captures.note_empty")));
    section.append(box);
    return section;
  }

  box.append(buildRelatedNotesList(item.relatedNotes));
  section.append(box);
  return section;
}

function buildMediaSection(item) {
  const section = createElement("section", "activity-section");
  if (item.kind === "audio") {
    const box = createElement("div", "activity-text-box");
    box.append(createElement("p", "activity-section-label", t("captures.source_file")));
    if (!item.sourceAvailable || !item.sourceFile) {
      box.append(createElement("p", "activity-unavailable", t("captures.not_available")));
      section.append(box);
      return section;
    }

    const cached = state.capturesMediaCache.get(item.sourceFile.path);
    if (!cached) {
      void ensureMediaLoaded(item.sourceFile);
      box.append(createElement("p", "activity-inline-message", t("captures.loading_media")));
      section.append(box);
      return section;
    }
    if (cached.status === "error") {
      box.append(createElement("p", "activity-inline-message", `${t("captures.error_load")}: ${cached.error}`));
      section.append(box);
      return section;
    }
    if (cached.status !== "loaded") {
      box.append(createElement("p", "activity-inline-message", t("captures.loading_media")));
      section.append(box);
      return section;
    }

    const audio = document.createElement("audio");
    audio.className = "activity-audio-player";
    audio.controls = true;
    audio.src = `data:${mediaMimeFromName(item.sourceFile.name)};base64,${cached.data}`;
    box.append(audio);
    section.append(box);
    return section;
  }

  if (!item.sourceAvailable || !item.sourceFile) {
    section.append(createElement("p", "activity-unavailable", t("captures.not_available")));
    return section;
  }

  const openButton = createElement("button", "activity-media-button", t("captures.open_image"));
  openButton.type = "button";
  openButton.addEventListener("click", () => openImageModal(item.sourceFile, item.sourceFile.name));
  section.append(
    buildFileRow(
      t("captures.source_file"),
      item.sourceFile,
      t("captures.available"),
      openButton,
    ),
  );
  return section;
}

function buildProcessedSection(item) {
  const section = createElement("section", "activity-section");

  if (item.processedStatus === "blocked_sensitive") {
    const blocked = createElement("div", "activity-blocked-box");
    blocked.append(createElement("p", "activity-text-body", t("captures.blocked_content")));
    if (item.contentRule) {
      blocked.append(createElement("p", "activity-file-meta", `${t("captures.blocked_rule")}: ${item.contentRule}`));
    }
    if (item.contentMatchType) {
      blocked.append(
        createElement("p", "activity-file-meta", `${t("captures.blocked_match_type")}: ${item.contentMatchType}`),
      );
    }
    if (item.contentPattern) {
      blocked.append(
        createElement("p", "activity-file-meta", `${t("captures.blocked_pattern")}: ${item.contentPattern}`),
      );
    }
    section.append(blocked);
    return section;
  }

  if (!item.processed) {
    section.append(createElement("p", "activity-inline-message", t("captures.pending_processing")));
    return section;
  }

  const textBox = createElement("div", "activity-text-box");
  textBox.append(
    createElement("p", "activity-section-label", t("captures.content")),
    createElement("p", "activity-text-body", item.text?.trim() || t("captures.no_content")),
  );
  section.append(textBox);
  return section;
}

function buildItemCard(item) {
  const expanded = state.capturesExpandedItems.has(item.id);
  const card = createElement(
    "article",
    `activity-card${expanded ? " is-open" : ""}${item.processedStatus === "blocked_sensitive" ? " is-blocked" : ""}`,
  );
  card.dataset.itemId = item.id;

  const main = createElement("div", "activity-card-main");
  const copy = createElement("div", "activity-card-copy");
  const title = item.sourceFile?.name
    ? displayName(item.sourceFile.name)
    : item.processed?.name
      ? displayName(item.processed.name)
      : mediaKindLabel(item.kind);
  const subtitle = item.sourceAvailable ? mediaKindLabel(item.kind) : t("captures.origin_unavailable");
  copy.append(
    createElement("p", "activity-card-title", title),
    createElement("p", "activity-card-subtitle", subtitle),
  );

  main.append(createElement("span", "activity-card-icon", mediaKindIcon(item.kind)), copy);
  const meta = createElement("div", "activity-card-meta");
  meta.append(
    createElement("span", "activity-pill", mediaKindLabel(item.kind)),
    createElement("span", `activity-pill status-${item.processedStatus}`, statusLabel(item.processedStatus)),
    createElement("span", "activity-pill", formatCaptureDate(item.capturedMs)),
  );
  if (item.relatedNotes?.length) {
    meta.append(createElement("span", "activity-pill", t("captures.note_count", { count: item.relatedNotes.length })));
  }
  copy.append(meta);

  card.append(
    buildExpandableHeader({
      expanded,
      content: main,
      deleteLabel: t("captures.delete_item"),
      onToggle: () => toggleExpandedItem(item.id),
      onDelete: () => deletePaths(getItemPaths(item)),
    }),
  );

  if (!expanded) {
    return card;
  }

  const body = createElement("div", "activity-card-body");
  body.append(buildMediaSection(item), buildProcessedSection(item), buildRelatedNotesSection(item));
  card.append(body);
  return card;
}


function getVisibleEntries() {
  if (state.capturesFilter === "notes") {
    return getOrderedEntries("notes");
  }
  return getOrderedEntries(state.capturesFilter);
}

function buildEntryNode(filter, entry) {
  return filter === "notes" ? buildNoteCard(entry) : buildItemCard(entry);
}

function renderCapturesList({ refresh = false } = {}) {
  const listEl = state.capturesList;
  if (!listEl) return;

  const filter = state.capturesFilter;
  const entries = getVisibleEntries();

  if (!entries.length) {
    listEl.replaceChildren(createElement("p", "captures-empty", t("captures.empty")));
    return;
  }

  const cache = state.capturesRenderedEntries[filter];
  const validIds = new Set();
  const nodes = [];

  for (const entry of entries) {
    const id = entry.id;
    const signature = entrySignature(entry);
    validIds.add(id);

    let rendered = cache.get(id);
    if (!rendered) {
      rendered = { signature, node: buildEntryNode(filter, entry) };
      cache.set(id, rendered);
    } else if (refresh || rendered.signature !== signature) {
      const nextNode = buildEntryNode(filter, entry);
      if (rendered.node.isConnected) {
        rendered.node.replaceWith(nextNode);
      }
      rendered = { signature, node: nextNode };
      cache.set(id, rendered);
    }

    nodes.push(rendered.node);
  }

  listEl.replaceChildren(...nodes);

  for (const [id] of cache) {
    if (!validIds.has(id)) {
      cache.delete(id);
    }
  }
}

function reconcileStateWithData() {
  const validItemIds = new Set((state.capturesData.items || []).map((item) => item.id));
  for (const id of [...state.capturesExpandedItems]) {
    if (!validItemIds.has(id)) {
      state.capturesExpandedItems.delete(id);
    }
  }

  const validNoteIds = new Set((state.capturesData.notes || []).map((note) => note.id));
  for (const id of [...state.capturesExpandedNotes]) {
    if (!validNoteIds.has(id)) {
      state.capturesExpandedNotes.delete(id);
    }
  }

  const validIds = new Set([...validItemIds, ...validNoteIds]);
  state.capturesSeenIds = new Set([...state.capturesSeenIds].filter((id) => validIds.has(id)));
  state.capturesVisibleOrder.screen = state.capturesVisibleOrder.screen.filter((id) => validItemIds.has(id));
  state.capturesVisibleOrder.audio = state.capturesVisibleOrder.audio.filter((id) => validItemIds.has(id));
  state.capturesVisibleOrder.notes = state.capturesVisibleOrder.notes.filter((id) => validNoteIds.has(id));
  for (const [id] of state.capturesEntrySnapshot) {
    if (!validIds.has(id)) {
      state.capturesEntrySnapshot.delete(id);
    }
  }
  for (const filter of CAPTURE_TABS) {
    for (const [id] of state.capturesRenderedEntries[filter]) {
      if (!validIds.has(id)) {
        state.capturesRenderedEntries[filter].delete(id);
      }
    }
  }

  if (state.capturesModalPath) {
    const stillExists = (state.capturesData.items || []).some(
      (item) => item.sourceFile?.path === state.capturesModalPath,
    );
    if (!stillExists) {
      closeImageModal();
    }
  }
}

export function startCapturesAutoRefresh() {
  if (state.capturesRefreshTimer !== null) {
    return;
  }
  state.capturesRefreshTimer = window.setInterval(() => {
    void loadCaptures({ silent: true });
  }, CAPTURES_REFRESH_INTERVAL_MS);
}

export function stopCapturesAutoRefresh() {
  if (state.capturesRefreshTimer === null) {
    return;
  }
  window.clearInterval(state.capturesRefreshTimer);
  state.capturesRefreshTimer = null;
}

export async function loadCaptures({ silent = false, force = false } = {}) {
  if (!isTauri()) return;
  if (state.capturesLoading) {
    if (force) {
      pendingCapturesRefresh = true;
      pendingCapturesForce = true;
    }
    return;
  }
  state.capturesLoading = true;

  if (!silent && state.capturesList && !state.capturesData.items.length && !state.capturesData.notes.length) {
    state.capturesList.replaceChildren(createElement("p", "captures-empty", t("captures.loading")));
  }

  try {
    const result = await invoke("list_activity");
    applyIncomingCaptures(result, { force });
    reconcileStateWithData();
    renderCapturesList();
    renderModal();
  } catch (error) {
    if (state.capturesList) {
      state.capturesList.replaceChildren(
        createElement(
          "p",
          "captures-empty",
          `${t("captures.error_load")}: ${error instanceof Error ? error.message : String(error)}`,
        ),
      );
    }
  } finally {
    state.capturesLoading = false;
    if (pendingCapturesRefresh) {
      pendingCapturesRefresh = false;
      const nextForce = pendingCapturesForce;
      pendingCapturesForce = false;
      void loadCaptures({ silent: true, force: nextForce });
    }
  }
}

function bindModalListeners() {
  if (state.capturesModalListenerBound) return;
  state.capturesModalListenerBound = true;
  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && state.capturesModalPath) {
      closeImageModal();
    }
  });
}

export function renderCapturesSection() {
  const view = createElement("section", "captures-view");
  const titleGroup = createElement("div", "captures-header-copy");
  titleGroup.append(
    createElement("h1", "captures-title", t("captures.title")),
    createElement("p", "captures-subtitle", t("captures.subtitle")),
  );

  const headerRow = createElement("div", "captures-header-row");
  const deleteSectionButton = createElement("button", "activity-media-button", t("captures.delete_section"));
  deleteSectionButton.type = "button";
  deleteSectionButton.addEventListener("click", async () => {
    await deletePaths(getVisiblePaths());
  });
  headerRow.append(titleGroup, deleteSectionButton);

  const tabBar = createElement("nav", "captures-tabs");
  state.capturesTabButtons = [];
  for (const tab of CAPTURE_TABS) {
    const tabBtn = createElement(
      "button",
      `captures-tab${tab === state.capturesFilter ? " active" : ""}`,
      t(`captures.tab_${tab}`),
    );
    tabBtn.type = "button";
    tabBtn.dataset.tab = tab;
    tabBtn.addEventListener("click", () => setFilter(tab));
    state.capturesTabButtons.push(tabBtn);
    tabBar.append(tabBtn);
  }

  const listEl = createElement("div", "captures-list");
  listEl.append(createElement("p", "captures-empty", t("captures.empty")));
  state.capturesList = listEl;

  const modal = createElement("div", "captures-modal");
  modal.hidden = true;
  modal.addEventListener("click", (event) => {
    if (event.target === modal) {
      closeImageModal();
    }
  });
  const dialog = createElement("div", "captures-modal-dialog");
  dialog.addEventListener("click", (event) => event.stopPropagation());
  const top = createElement("div", "captures-modal-top");
  const modalTitle = createElement("p", "captures-modal-title", "");
  const closeButton = createElement("button", "captures-modal-close", t("captures.close_image"));
  closeButton.type = "button";
  closeButton.addEventListener("click", closeImageModal);
  top.append(modalTitle, closeButton);
  const modalImage = document.createElement("img");
  modalImage.className = "captures-modal-image";
  dialog.append(top, modalImage);
  modal.append(dialog);

  state.capturesModal = modal;
  state.capturesModalHeading = modalTitle;
  state.capturesModalImage = modalImage;
  state.capturesModalCloseButton = closeButton;

  bindModalListeners();

  view.append(headerRow, tabBar, listEl, modal);
  return view;
}
