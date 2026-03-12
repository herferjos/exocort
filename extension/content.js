// Extract structured text (Markdown-like) from the DOM

function getStructuredText(node, preserveWhitespace = false) {
  if (!node) return "";

  if (node.nodeType === Node.TEXT_NODE) {
    const text = node.textContent || "";
    if (preserveWhitespace) return text;
    return text.replace(/\s+/g, " ");
  }

  if (node.nodeType !== Node.ELEMENT_NODE) return "";

  const tag = node.tagName;
  const ignoredTags = [
    "SCRIPT",
    "STYLE",
    "NOSCRIPT",
    "IFRAME",
    "SVG",
    "HEAD",
    "METADATA",
    "LINK",
    "OBJECT",
    "FANCYBOX"
  ];
  if (ignoredTags.includes(tag)) return "";
  if (node.hasAttribute("hidden")) return "";

  const isPre = tag === "PRE" || tag === "TEXTAREA" || tag === "CODE";
  const shouldPreserve = preserveWhitespace || isPre;

  let content = "";

  if (node.shadowRoot) {
    for (let i = 0; i < node.shadowRoot.childNodes.length; i++) {
      content += getStructuredText(node.shadowRoot.childNodes[i], shouldPreserve);
    }
  }

  if (!node.shadowRoot && node.childNodes.length > 0) {
    for (let i = 0; i < node.childNodes.length; i++) {
      content += getStructuredText(node.childNodes[i], shouldPreserve);
    }
  }

  switch (tag) {
    case "SLOT": {
      if (node.assignedNodes) {
        const nodes = node.assignedNodes();
        for (let i = 0; i < nodes.length; i++) {
          content += getStructuredText(nodes[i], shouldPreserve);
        }
      }
      return content;
    }
    case "H1":
      return `\n\n# ${content.trim()}\n\n`;
    case "H2":
      return `\n\n## ${content.trim()}\n\n`;
    case "H3":
      return `\n\n### ${content.trim()}\n\n`;
    case "H4":
    case "H5":
    case "H6":
      return `\n\n#### ${content.trim()}\n\n`;

    case "P":
      return `\n\n${content.trim()}\n\n`;
    case "BR":
      return `\n`;
    case "HR":
      return `\n---\n`;

    case "LI":
      return `\n- ${content.trim()}`;
    case "UL":
    case "OL":
      return `\n\n${content.trim()}\n\n`;

    case "A": {
      const href = node.href || node.getAttribute("href");
      const text = content.trim();
      if (!text) return "";
      if (!href || href.startsWith("javascript:") || href.startsWith("#")) return ` ${text} `;
      return ` [${text}](${href}) `;
    }

    case "IMG": {
      const alt = node.getAttribute("alt");
      return alt ? ` ![${alt}] ` : "";
    }

    case "INPUT": {
      const type = node.getAttribute("type");
      const val = node.value || node.getAttribute("value") || "";
      if (type === "hidden" || type === "password") return "";
      return ` [Input: ${val}] `;
    }

    case "TEXTAREA":
      return `\n${node.value || ""}\n`;

    case "B":
    case "STRONG":
      return ` **${content.trim()}** `;
    case "I":
    case "EM":
      return ` *${content.trim()}* `;

    case "CODE": {
      if (preserveWhitespace && node.parentNode && node.parentNode.tagName === "PRE") return content;
      return ` \`${content.trim()}\` `;
    }

    case "PRE":
      return `\n\`\`\`\n${content}\n\`\`\`\n`;
    case "BLOCKQUOTE":
      return `\n> ${content.trim()}\n`;

    case "TR":
      return `\n| ${content.trim()} |`;
    case "TH":
    case "TD":
      return ` ${content.trim()} |`;

    case "DIV":
    case "SECTION":
    case "ARTICLE":
    case "MAIN":
    case "HEADER":
    case "FOOTER":
    case "ASIDE":
    case "NAV":
    case "FORM":
      return `\n${content}`;

    default:
      return content;
  }
}

function getPageContent() {
  if (!document.body) return "";

  let structured = getStructuredText(document.body);
  structured = structured.replace(/(\n\s*){3,}/g, "\n\n");
  structured = structured.trim();

  if (structured.length < 50 && document.body.innerText.length > 50) {
    return document.body.innerText.trim();
  }

  return structured;
}

let lastSentText = null;

function extractSnapshot() {
  const url = location.href;
  const title = document.title || "";
  const text = getPageContent();

  return {
    url,
    title,
    text,
    text_len: text.length
  };
}

function sendSnapshot(reason) {
  try {
    const payload = extractSnapshot();

    if (!payload.text) return;
    if (payload.text === lastSentText) return;
    if (payload.text.length < 50) return;

    lastSentText = payload.text;

    chrome.runtime.sendMessage({
      kind: "page_text",
      reason,
      payload
    });
  } catch (e) {
    // Extension context might be invalidated
  }
}

setTimeout(() => sendSnapshot("load"), 3000);

let lastUrl = location.href;
setInterval(() => {
  if (location.href !== lastUrl) {
    lastUrl = location.href;
    lastSentText = null;
    setTimeout(() => sendSnapshot("url_change"), 3000);
  }
}, 1000);

let debounceTimer;
let maxWaitTimer;

const observer = new MutationObserver(() => {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    sendSnapshot("dom_settled");
    clearTimeout(maxWaitTimer);
    maxWaitTimer = null;
  }, 2000);

  if (!maxWaitTimer) {
    maxWaitTimer = setTimeout(() => {
      sendSnapshot("dom_active_update");
      maxWaitTimer = null;
    }, 10000);
  }
});

if (document.body) {
  observer.observe(document.body, {
    childList: true,
    subtree: true,
    characterData: true,
    attributes: true
  });
}

// User interaction triggers

document.addEventListener(
  "keydown",
  (e) => {
    if (e.key === "Enter") {
      setTimeout(() => sendSnapshot("user_enter_key"), 500);
    }
  },
  true
);

document.addEventListener(
  "click",
  () => {
    setTimeout(() => sendSnapshot("user_click"), 1000);
  },
  true
);
