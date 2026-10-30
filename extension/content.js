"use strict";

(() => {
  if (window.__nexusClickerInstalled) {
    return;
  }
  window.__nexusClickerInstalled = true;

  // Firefox exposes promise-based APIs as `browser`, Chromium as `chrome`.
  const ext = globalThis.browser ?? globalThis.chrome;

  let clicked = false;
  let claiming = false;
  const roots = new Set();
  const originalTitle = document.title;

  let lastStatus = "";

  // Only touch the title when the status changes: the title is part of the
  // observed page, so rewriting it every time would trigger the observer again
  // in an endless loop.
  function report(status) {
    if (status === lastStatus) return;
    lastStatus = status;
    document.title = `${originalTitle} [Nexus Clicker: ${status}]`;
  }

  function visible(element) {
    const style = getComputedStyle(element);
    const bounds = element.getBoundingClientRect();
    return style.display !== "none" && style.visibility !== "hidden" &&
      Number(style.opacity) !== 0 && bounds.width > 0 && bounds.height > 0;
  }

  function label(element) {
    return [
      element.innerText,
      element.getAttribute("aria-label"),
      element.getAttribute("title"),
      element.value,
      element.textContent
    ].filter(Boolean).map((text) => text.replace(/\s+/g, " ").trim().toLowerCase())
      .find((text) => /^slow download(?:$|[.\s])/.test(text)) || "";
  }

  function waiting(element) {
    return element.matches(":disabled") ||
      element.getAttribute("aria-disabled") === "true" ||
      /\bwait more\b/i.test(label(element));
  }

  function observe(root) {
    if (roots.has(root)) return;
    roots.add(root);
    observer.observe(root, { childList: true, subtree: true, attributes: true });
    for (const element of root.querySelectorAll("*")) {
      if (element.shadowRoot) observe(element.shadowRoot);
    }
  }

  async function check() {
    if (clicked || claiming) return;
    const selector = 'button, a, [role="button"], input[type="button"], input[type="submit"], [onclick], [tabindex], [class*="btn" i]';
    const candidates = [];
    for (const root of roots) {
      for (const element of root.querySelectorAll(selector)) {
        if (visible(element) && label(element)) candidates.push(element);
      }
    }
    const ready = candidates.filter((element) => !waiting(element));
    if (ready.length !== 1) {
      if (candidates.length) report(ready.length ? `multiple (${ready.length})` : "wait more");
      return;
    }

    claiming = true;
    let response;
    try {
      response = await ext.runtime.sendMessage({ type: "claim-click" });
    } catch (error) {
      claiming = false;
      console.error("Could not claim click:", error);
      report("claim failed");
      return;
    }
    claiming = false;
    if (response?.result === "same-tab") {
      clicked = true;
      observer.disconnect();
      clearInterval(poll);
      report("already claimed in this tab");
      return;
    }
    if (response?.result !== "claimed") {
      clicked = true;
      observer.disconnect();
      clearInterval(poll);
      report("duplicate file; closing tab");
      ext.runtime.sendMessage({ type: "close-duplicate" }).catch(console.error);
      return;
    }

    clicked = true;
    observer.disconnect();
    clearInterval(poll);
    report("clicking");
    ready[0].click();
    ext.runtime.sendMessage({ type: "slow-download-clicked" }).catch(console.error);
  }

  const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      for (const node of mutation.addedNodes) {
        if (node instanceof Element) {
          if (node.shadowRoot) observe(node.shadowRoot);
          for (const element of node.querySelectorAll("*")) {
            if (element.shadowRoot) observe(element.shadowRoot);
          }
        }
      }
    }
    check();
  });
  observe(document);
  const poll = setInterval(check, 250);
  check();
})();
