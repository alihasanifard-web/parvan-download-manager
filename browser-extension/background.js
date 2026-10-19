const API_BASE = "http://127.0.0.1:9876/api";

// Initialize default settings on install
chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.get(["autoIntercept", "threads"], (res) => {
    if (res.autoIntercept === undefined) {
      chrome.storage.local.set({ autoIntercept: true, threads: 16 });
    }
  });

  // Create Context Menu Item
  chrome.contextMenus.create({
    id: "parvan_download_link",
    title: "⚡ دانلود با پروان (Download with Parvan)",
    contexts: ["link", "image", "video", "audio"]
  });
});

// Context Menu Click Handler
chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === "parvan_download_link") {
    const targetUrl = info.linkUrl || info.srcUrl;
    if (targetUrl) {
      sendToParvan(targetUrl);
    }
  }
});

// Auto Intercept Browser Downloads
chrome.downloads.onCreated.addListener(async (downloadItem) => {
  const url = downloadItem.finalUrl || downloadItem.url;

  // Ignore internal downloads or localhost
  if (!url || url.startsWith("blob:") || url.startsWith("data:") || url.includes("127.0.0.1:9876")) {
    return;
  }

  // Check if autoIntercept is enabled
  const config = await chrome.storage.local.get(["autoIntercept", "threads"]);
  if (config.autoIntercept === false) {
    return;
  }

  // Attempt to forward to Parvan Desktop
  const sent = await sendToParvan(url, config.threads || 16, downloadItem.filename);
  if (sent) {
    // Successfully handed off to Parvan -> Cancel browser download
    try {
      chrome.downloads.cancel(downloadItem.id, () => {
        chrome.downloads.erase({ id: downloadItem.id });
      });
    } catch (e) {
      console.log("Could not cancel browser download:", e);
    }
  }
});

// Function to send download task to Parvan API
async function sendToParvan(url, threads = 16, filename = "") {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 2500);

    const response = await fetch(`${API_BASE}/add`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, threads, filename }),
      signal: controller.signal
    });
    clearTimeout(timeoutId);

    if (response.ok) {
      const data = await response.json();
      chrome.notifications.create({
        type: "basic",
        iconUrl: "icons/icon128.png",
        title: "⚡ پروان دانلود منیجر",
        message: `دانلود با ۱۶ کانکشن آغاز شد:\n${data.filename || url.split("/").pop() || "فایل جدید"}`
      });
      return true;
    }
  } catch (err) {
    console.warn("Parvan Desktop is not running or unreachable:", err);
  }
  return false;
}
