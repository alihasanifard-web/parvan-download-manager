const API_BASE = "http://127.0.0.1:9876/api";

const statusBadge = document.getElementById("statusBadge");
const statusText = document.getElementById("statusText");
const metricSpeed = document.getElementById("metricSpeed");
const metricActive = document.getElementById("metricActive");
const inputUrl = document.getElementById("inputUrl");
const btnDownload = document.getElementById("btnDownload");
const toggleIntercept = document.getElementById("toggleIntercept");
const selectThreads = document.getElementById("selectThreads");
const btnOpenApp = document.getElementById("btnOpenApp");

// Load stored settings
chrome.storage.local.get(["autoIntercept", "threads"], (res) => {
  if (res.autoIntercept !== undefined) {
    toggleIntercept.checked = res.autoIntercept;
  }
  if (res.threads) {
    selectThreads.value = res.threads;
  }
});

// Update settings on change
toggleIntercept.addEventListener("change", () => {
  chrome.storage.local.set({ autoIntercept: toggleIntercept.checked });
});

selectThreads.addEventListener("change", () => {
  chrome.storage.local.set({ threads: parseInt(selectThreads.value) });
});

// Check status & update telemetry
async function checkStatus() {
  try {
    const res = await fetch(`${API_BASE}/telemetry`, { cache: "no-store" });
    if (!res.ok) throw new Error("Offline");
    const data = await res.json();

    statusBadge.className = "status-badge online";
    statusText.textContent = "متصل به پروان";
    metricSpeed.innerHTML = `${data.aggregate_speed_mb.toFixed(1)} <span class="unit">MB/s</span>`;
    metricActive.innerHTML = `${data.active_tasks_count} <span class="unit">تسک</span>`;
  } catch (err) {
    statusBadge.className = "status-badge offline";
    statusText.textContent = "پروان اجرا نیست";
    metricSpeed.innerHTML = `۰.۰ <span class="unit">MB/s</span>`;
    metricActive.innerHTML = `۰ <span class="unit">تسک</span>`;
  }
}

// Initial status check & interval
checkStatus();
const intervalId = setInterval(checkStatus, 1500);

// Auto-fill clipboard link
navigator.clipboard.readText().then((clipText) => {
  if (clipText && (clipText.startsWith("http://") || clipText.startsWith("https://"))) {
    inputUrl.value = clipText.trim();
  }
}).catch(() => {});

// Add Download button
btnDownload.addEventListener("click", async () => {
  const url = inputUrl.value.trim();
  if (!url) return;

  btnDownload.disabled = true;
  btnDownload.textContent = "...";

  try {
    const res = await fetch(`${API_BASE}/add`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: url,
        threads: parseInt(selectThreads.value)
      })
    });

    if (res.ok) {
      inputUrl.value = "";
      btnDownload.textContent = "✓ افزوده شد";
      setTimeout(() => {
        btnDownload.textContent = "⚡ دانلود";
        btnDownload.disabled = false;
      }, 1500);
      checkStatus();
    } else {
      throw new Error("Failed");
    }
  } catch (e) {
    alert("خطا: برنامه پروان روی سیستم اجرا نیست!");
    btnDownload.textContent = "⚡ دانلود";
    btnDownload.disabled = false;
  }
});

// Open Parvan App / Web
btnOpenApp.addEventListener("click", () => {
  chrome.tabs.create({ url: "http://127.0.0.1:9876/index.html" });
});
