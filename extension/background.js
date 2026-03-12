const COLLECTOR_URL = "http://127.0.0.1:8787/events";
const QUEUE_KEY = "event_queue_v1";

const lastPageText = new Map();
const lastPageView = new Map();

function baseEvent(type, meta) {
  return {
    id: crypto.randomUUID ? crypto.randomUUID() : String(Date.now()),
    ts: new Date().toISOString(),
    source: "browser",
    type,
    meta
  };
}

async function sha256Hex(s) {
  const data = new TextEncoder().encode(s || "");
  const hashBuf = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(hashBuf))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

async function getQueue() {
  const obj = await chrome.storage.local.get([QUEUE_KEY]);
  return Array.isArray(obj[QUEUE_KEY]) ? obj[QUEUE_KEY] : [];
}

async function setQueue(queue) {
  await chrome.storage.local.set({ [QUEUE_KEY]: queue });
}

async function enqueue(event) {
  const q = await getQueue();
  q.push(event);
  await setQueue(q);
}

let isFlushing = false;
async function flushQueue(max = 50) {
  if (isFlushing) return;
  isFlushing = true;
  try {
    const q = await getQueue();
    if (q.length === 0) return;

    const batch = q.slice(0, max);
    try {
      const resp = await fetch(COLLECTOR_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ events: batch })
      });
      if (!resp.ok) throw new Error("collector_rejected");
      await setQueue(q.slice(batch.length));
    } catch (e) {}
  } finally {
    isFlushing = false;
  }
}

chrome.runtime.onMessage.addListener((msg, sender) => {
  if (!msg || msg.kind !== "page_text") return;

  (async () => {
    const tabId = sender && sender.tab ? sender.tab.id : null;
    const p = msg.payload || {};
    const text = typeof p.text === "string" ? p.text : "";

    if (!text || text.length < 50) return;

    const textSha = await sha256Hex(text);
    if (tabId && lastPageText.get(tabId) === textSha) {
      return;
    }
    if (tabId) {
      lastPageText.set(tabId, textSha);
    }

    await enqueue(
      baseEvent("browser.page_text", {
        tab_id: tabId,
        url: p.url,
        title: p.title,
        text,
        text_len: text.length,
        text_sha256: textSha,
        truncated: !!p.truncated,
        content_method: "innerText",
        reason: msg.reason
      })
    );
    await flushQueue();
  })();
});

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  (async () => {
    if (changeInfo.status !== "complete") return;

    const now = Date.now();
    const last = lastPageView.get(tabId);
    const currentUrl = tab.url || "";

    if (last && last.url === currentUrl && now - last.ts < 2000) {
      return;
    }

    if (last && last.url !== currentUrl) {
      lastPageText.delete(tabId);
    }

    lastPageView.set(tabId, { url: currentUrl, ts: now });

    await enqueue(
      baseEvent("browser.page_view", {
        tab_id: tabId,
        url: currentUrl,
        title: tab.title || ""
      })
    );
    await flushQueue();
  })();
});

chrome.tabs.onRemoved.addListener((tabId) => {
  (async () => {
    lastPageView.delete(tabId);
    lastPageText.delete(tabId);
  })();
});

setInterval(() => flushQueue(), 3000);
