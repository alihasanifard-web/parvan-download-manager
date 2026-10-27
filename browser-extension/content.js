// Parvan Video Sniffer Content Script
(function () {
  let activeFloatingBtn = null;
  const detectedVideos = new Set();

  // Create floating download button over video player
  function createFloatingButton(videoEl) {
    if (videoEl.dataset.parvanBound) return;
    videoEl.dataset.parvanBound = "true";

    const btn = document.createElement("div");
    btn.className = "parvan-video-grabber-btn";
    btn.innerHTML = `
      <div class="parvan-grabber-inner">
        <svg width="15" height="15" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M19 14l-7 7m0 0l-7-7m7 7V3" />
        </svg>
        <span>دانلود این ویدیو (پروان)</span>
      </div>
    `;

    // Style the button directly or with class
    btn.style.cssText = `
      position: absolute;
      top: 14px;
      right: 14px;
      z-index: 2147483647;
      background: linear-gradient(135deg, rgba(0, 245, 255, 0.95), rgba(37, 99, 235, 0.95));
      color: #07090E;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Tahoma, sans-serif;
      font-size: 12px;
      font-weight: 800;
      padding: 6px 12px;
      border-radius: 8px;
      cursor: pointer;
      box-shadow: 0 4px 15px rgba(0, 245, 255, 0.4), 0 2px 6px rgba(0,0,0,0.5);
      display: flex;
      align-items: center;
      gap: 6px;
      opacity: 0;
      transform: translateY(-4px);
      transition: opacity 200ms ease, transform 200ms ease;
      pointer-events: auto;
      user-select: none;
      direction: rtl;
    `;

    // Position relative to video or container
    const parent = videoEl.parentElement || document.body;
    if (getComputedStyle(parent).position === "static") {
      parent.style.position = "relative";
    }
    parent.appendChild(btn);

    // Show on hover
    function showBtn() {
      btn.style.opacity = "1";
      btn.style.transform = "translateY(0)";
    }
    function hideBtn() {
      btn.style.opacity = "0";
      btn.style.transform = "translateY(-4px)";
    }

    videoEl.addEventListener("mouseenter", showBtn);
    parent.addEventListener("mouseenter", showBtn);
    videoEl.addEventListener("mouseleave", hideBtn);
    parent.addEventListener("mouseleave", hideBtn);

    // Click handler to download with quality picker
    let qualityMenu = null;

    function createQualityMenu() {
      if (qualityMenu) return qualityMenu;
      qualityMenu = document.createElement("div");
      qualityMenu.className = "parvan-quality-picker-menu";
      qualityMenu.style.cssText = `
        position: absolute;
        top: 42px;
        right: 0;
        background: #090d16;
        border: 1px solid rgba(0, 245, 255, 0.4);
        border-radius: 8px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.8);
        padding: 6px;
        display: none;
        flex-direction: column;
        gap: 4px;
        z-index: 2147483647;
        min-width: 170px;
        font-family: inherit;
        font-size: 11.5px;
        color: #e2e8f0;
      `;

      const qualities = [
        { id: "1080p", label: "🎬 1080p (Full HD)", tag: "FHD" },
        { id: "720p", label: "🎬 720p (HD Ready)", tag: "HD" },
        { id: "480p", label: "🎬 480p (کم‌حجم)", tag: "SD" },
        { id: "audio", label: "🎵 استخراج صوت (MP3)", tag: "MP3" }
      ];

      qualities.forEach(q => {
        const item = document.createElement("div");
        item.style.cssText = `
          padding: 6px 10px;
          border-radius: 5px;
          cursor: pointer;
          display: flex;
          justify-content: space-between;
          align-items: center;
          transition: background 0.15s;
        `;
        item.innerHTML = `<span>${q.label}</span><span style="color:#00F5FF; font-size:10px; font-weight:700;">${q.tag}</span>`;
        item.addEventListener("mouseenter", () => item.style.background = "rgba(0, 245, 255, 0.15)");
        item.addEventListener("mouseleave", () => item.style.background = "transparent");
        item.addEventListener("click", (evt) => {
          evt.stopPropagation();
          qualityMenu.style.display = "none";
          const videoUrl = videoEl.currentSrc || videoEl.src || (videoEl.querySelector("source") ? videoEl.querySelector("source").src : window.location.href);
          
          chrome.runtime.sendMessage({
            action: "download_media",
            url: videoUrl,
            quality: q.id,
            title: document.title || "video"
          });

          btn.querySelector("span").textContent = `✓ ارسال کیفیت ${q.tag}`;
          setTimeout(() => {
            btn.querySelector("span").textContent = "دانلود این ویدیو (پروان)";
          }, 2000);
        });
        qualityMenu.appendChild(item);
      });

      btn.appendChild(qualityMenu);
      return qualityMenu;
    }

    btn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();

      const menu = createQualityMenu();
      const isVisible = menu.style.display === "flex";
      menu.style.display = isVisible ? "none" : "flex";
    });

    document.addEventListener("click", () => {
      if (qualityMenu) qualityMenu.style.display = "none";
    });
  }

  // Scan for videos on page
  function scanVideos() {
    const videos = document.querySelectorAll("video");
    videos.forEach((v) => {
      if (v.offsetWidth > 150 && v.offsetHeight > 100) {
        createFloatingButton(v);
      }
    });
  }

  // Initial scan & dynamic DOM observer
  scanVideos();
  const observer = new MutationObserver(() => scanVideos());
  observer.observe(document.body || document.documentElement, {
    childList: true,
    subtree: true
  });
})();
