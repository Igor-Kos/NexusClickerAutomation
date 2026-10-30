"use strict";

// One extension for Firefox and Chromium browsers (Chrome, Edge, Yandex).
// Firefox exposes promise-based APIs as `browser`, Chromium as `chrome`.
const ext = globalThis.browser ?? globalThis.chrome;

const NEXUS_PAGES = ["https://www.nexusmods.com/*/mods/*"];
const RETRY_MS = 10000;
const inFlightPages = new Set();
const closingTabs = new Set();
const claimedTabs = new Map();
const pendingPages = new Set();
const retryTimers = new Map();
const retryUrls = new Map();
let lastClaimedPageKey = "";

// Firefox shows a failed page load as about:neterror?...&u=<requested url>.
function requestedUrl(url) {
  if (typeof url === "string" && url.startsWith("about:neterror")) {
    try {
      return new URLSearchParams(url.slice(url.indexOf("?") + 1)).get("u");
    } catch {
      return null;
    }
  }
  return url;
}

function pageKey(url) {
  try {
    const parsed = new URL(requestedUrl(url));
    if (parsed.origin !== "https://www.nexusmods.com" ||
        !/^\/[^/]+\/mods\/\d+\/?$/i.test(parsed.pathname)) {
      return null;
    }
    return `${parsed.origin}${parsed.pathname.replace(/\/+$/, "")}`.toLowerCase();
  } catch {
    return null;
  }
}

async function readLastClaim() {
  if (!ext.storage?.session) {
    return lastClaimedPageKey;
  }
  const stored = await ext.storage.session.get("lastClaimedPageKey");
  return stored.lastClaimedPageKey || "";
}

async function writeLastClaim(key) {
  lastClaimedPageKey = key;
  if (ext.storage?.session) {
    await ext.storage.session.set({ lastClaimedPageKey: key });
  }
}

// Reopen a mod page that loaded but was never clicked (slow load, network error).
function scheduleRetry(tabId, url) {
  if (retryUrls.get(tabId) === url && retryTimers.has(tabId)) {
    return;
  }
  const previous = retryTimers.get(tabId);
  if (previous) {
    clearTimeout(previous);
  }
  const timer = setTimeout(async () => {
    retryTimers.delete(tabId);
    retryUrls.delete(tabId);
    if (claimedTabs.has(tabId) || closingTabs.has(tabId)) {
      return;
    }
    try {
      const current = await ext.tabs.get(tabId);
      if (pageKey(current.url) !== pageKey(url)) {
        return;
      }
      const replacement = await ext.tabs.create({ url, active: false });
      if (!Number.isInteger(replacement.id)) {
        throw new Error("The browser did not return an ID for the replacement tab.");
      }
      console.warn(`No click after ${RETRY_MS}ms; replaced tab ${tabId} with background tab ${replacement.id}.`);
      await ext.tabs.remove(tabId);
    } catch (error) {
      console.error("Could not reopen the Nexus page:", error);
      scheduleRetry(tabId, url);
    }
  }, RETRY_MS);
  retryTimers.set(tabId, timer);
  retryUrls.set(tabId, url);
}

async function hasNexusAccess() {
  if (!ext.permissions?.contains) {
    return true;
  }
  return ext.permissions.contains({ origins: NEXUS_PAGES });
}

async function monitorExistingTabs() {
  const tabs = await ext.tabs.query({});
  for (const tab of tabs) {
    const url = requestedUrl(tab.url);
    if (!Number.isInteger(tab.id) || !pageKey(url)) {
      continue;
    }
    if (url !== tab.url) {
      await ext.tabs.update(tab.id, { url });
      continue;
    }
    try {
      await ext.scripting.executeScript({
        target: { tabId: tab.id, allFrames: true },
        files: ["content.js"]
      });
      scheduleRetry(tab.id, url);
    } catch (error) {
      console.warn("Could not attach to an existing tab:", error);
    }
  }
}

// Firefox may not grant site access to a newly loaded add-on. Ask once with a
// small page, because the permission prompt needs a click from the user.
async function start() {
  if (await hasNexusAccess()) {
    await monitorExistingTabs();
    return;
  }
  const setupUrl = ext.runtime.getURL("setup.html");
  const open = await ext.tabs.query({ url: setupUrl }).catch(() => []);
  if (!open.length) {
    await ext.tabs.create({ url: setupUrl, active: true });
  }
}

ext.runtime.onInstalled.addListener(() => {
  start().catch((error) => console.error("Could not start Nexus Clicker:", error));
});

ext.runtime.onStartup.addListener(() => {
  start().catch((error) => console.error("Could not start Nexus Clicker:", error));
});

ext.permissions?.onAdded?.addListener(() => {
  monitorExistingTabs().catch((error) => console.error("Could not scan existing tabs:", error));
});

ext.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  const url = requestedUrl(changeInfo.url || tab.url);
  const key = pageKey(url);
  if (!key) {
    return;
  }
  const oldKey = claimedTabs.get(tabId);
  if (oldKey && oldKey !== key) {
    claimedTabs.delete(tabId);
    inFlightPages.delete(oldKey);
  }
  scheduleRetry(tabId, url);
});

ext.tabs.onRemoved.addListener((tabId) => {
  const timer = retryTimers.get(tabId);
  if (timer) {
    clearTimeout(timer);
    retryTimers.delete(tabId);
  }
  retryUrls.delete(tabId);
  const key = claimedTabs.get(tabId);
  if (key) {
    inFlightPages.delete(key);
    claimedTabs.delete(tabId);
  }
  closingTabs.delete(tabId);
});

function closeTab(tabId, delay) {
  if (closingTabs.has(tabId)) {
    return;
  }
  closingTabs.add(tabId);
  setTimeout(() => {
    Promise.resolve(ext.tabs.remove(tabId)).catch((error) => console.warn("Tab already closed:", error));
  }, delay);
}

ext.runtime.onMessage.addListener((message, sender, sendResponse) => {
  const tabId = sender.tab?.id;
  const key = pageKey(sender.tab?.url);

  if (message?.type === "claim-click") {
    if (!Number.isInteger(tabId) || !key) {
      sendResponse({ result: "invalid" });
      return false;
    }
    if (claimedTabs.has(tabId)) {
      sendResponse({ result: "same-tab" });
      return false;
    }
    if (inFlightPages.has(key) || pendingPages.has(key)) {
      sendResponse({ result: "duplicate-page" });
      return false;
    }

    pendingPages.add(key);
    readLastClaim().then((lastKey) => {
      if (lastKey === key) {
        sendResponse({ result: "duplicate-page" });
        return;
      }
      inFlightPages.add(key);
      claimedTabs.set(tabId, key);
      return writeLastClaim(key).then(() => {
        const timer = retryTimers.get(tabId);
        if (timer) {
          clearTimeout(timer);
          retryTimers.delete(tabId);
        }
        retryUrls.delete(tabId);
        sendResponse({ result: "claimed" });
      });
    }).catch((error) => {
      console.error("Could not save the click claim:", error);
      sendResponse({ result: "claim-error" });
    }).finally(() => {
      pendingPages.delete(key);
    });
    return true;
  }

  if (message?.type === "close-duplicate") {
    if (Number.isInteger(tabId) && key) {
      closeTab(tabId, 100);
    }
    return false;
  }

  if (message?.type === "slow-download-clicked") {
    if (Number.isInteger(tabId) && claimedTabs.has(tabId)) {
      closeTab(tabId, 500);
    }
    return false;
  }
  return false;
});
