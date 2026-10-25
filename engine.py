import os
import sys
import time
import math
import json
import threading
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
TASKS_DB_FILE = os.path.join(CURRENT_DIR, "tasks_state.json")
CONFIG_FILE = os.path.join(CURRENT_DIR, "config.json")

DEFAULT_CONFIG = {
    "save_directory": os.path.join(os.path.expanduser("~"), "Downloads"),
    "default_threads": 16,
    "proxy_mode": "auto",
    "custom_proxy": "http://127.0.0.1:10808",
    "speed_limit_mb": 150,
    "auto_resume": True,
    "sound_effects": True,
    "language": "fa"
}

def load_config():
    cfg = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    return cfg

def save_config(cfg):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def format_bytes(num_bytes):
    if num_bytes <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = int(math.floor(math.log(num_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(num_bytes / p, 2)
    return f"{s} {units[i]}"

def detect_category(filename):
    ext = os.path.splitext(filename)[1].lower()
    if ext in ['.exe', '.msi', '.apk', '.dmg', '.pkg', '.deb', '.rpm', '.appimage']:
        return "app"
    elif ext in ['.iso', '.img', '.vmdk', '.bin']:
        return "iso"
    elif ext in ['.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz']:
        return "archive"
    elif ext in ['.mp4', '.mkv', '.avi', '.mov', '.mp3', '.flac']:
        return "media"
    return "other"

class ChunkWorker:
    def __init__(self, task, chunk_id, start_byte, end_byte, file_path, proxy=None):
        self.task = task
        self.chunk_id = chunk_id
        self.start_byte = start_byte
        self.end_byte = end_byte
        self.total_bytes = end_byte - start_byte + 1
        self.downloaded = 0
        self.file_path = file_path
        self.proxy = proxy
        self.status = "pending" # pending, active, done, paused, error
        self._stop_flag = False

    def run(self):
        if self.downloaded >= self.total_bytes:
            self.status = "done"
            return

        self.status = "active"
        self._stop_flag = False
        cur_start = self.start_byte + self.downloaded
        if cur_start > self.end_byte:
            self.status = "done"
            return

        req = urllib.request.Request(self.task.url)
        req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 ParvanDownloadManager/3.0')
        req.add_header('Range', f'bytes={cur_start}-{self.end_byte}')

        opener = urllib.request.build_opener()
        if self.proxy:
            proxy_handler = urllib.request.ProxyHandler({'http': self.proxy, 'https': self.proxy})
            opener = urllib.request.build_opener(proxy_handler)

        max_retries = 5
        retry_delay = 1.0

        for attempt in range(max_retries):
            if self._stop_flag or self.task.is_paused:
                break
            try:
                # Re-calculate current start byte in case of partial progress before retry
                cur_start = self.start_byte + self.downloaded
                if cur_start > self.end_byte:
                    self.status = "done"
                    return
                req.headers['Range'] = f'bytes={cur_start}-{self.end_byte}'

                with opener.open(req, timeout=15) as resp:
                    with open(self.file_path, 'r+b') as f:
                        f.seek(cur_start)
                        buf_size = 128 * 1024 # 128 KB high-speed buffer
                        while not self._stop_flag and not self.task.is_paused:
                            # Apply global speed limiter if enabled
                            if engine.speed_limit_mb > 0:
                                max_bps = engine.speed_limit_mb * 1024 * 1024
                                per_thread_bps = max(1024 * 64, max_bps // max(1, self.task.num_threads))
                                chunk_start_t = time.time()
                                data = resp.read(buf_size)
                                if not data:
                                    break
                                f.write(data)
                                chunk_len = len(data)
                                self.downloaded += chunk_len
                                with self.task.lock:
                                    self.task.downloaded_bytes += chunk_len

                                elapsed = time.time() - chunk_start_t
                                expected_time = chunk_len / per_thread_bps
                                if expected_time > elapsed:
                                    time.sleep(expected_time - elapsed)
                            else:
                                data = resp.read(buf_size)
                                if not data:
                                    break
                                f.write(data)
                                chunk_len = len(data)
                                self.downloaded += chunk_len
                                with self.task.lock:
                                    self.task.downloaded_bytes += chunk_len

                if self.downloaded >= self.total_bytes:
                    self.status = "done"
                    return
                elif self.task.is_paused:
                    self.status = "paused"
                    return
            except Exception as e:
                if self._stop_flag or self.task.is_paused:
                    return
                time.sleep(retry_delay)
                retry_delay = min(5.0, retry_delay * 1.5)

        if not self._stop_flag and not self.task.is_paused and self.downloaded < self.total_bytes:
            self.status = "error"

    def stop(self):
        self._stop_flag = True


class DownloadTask:
    def __init__(self, task_id, url, filename=None, save_dir=None, num_threads=16, proxy=None):
        self.id = str(task_id)
        self.url = url
        self.num_threads = num_threads
        self.proxy = proxy or "http://127.0.0.1:10808"
        self.save_dir = save_dir or os.path.join(os.path.expanduser("~"), "Downloads")
        self.filename = filename or self._extract_filename()
        self.save_path = os.path.join(self.save_dir, self.filename)
        self.category = detect_category(self.filename)
        
        self.total_size = 0
        self.downloaded_bytes = 0
        self.support_ranges = True
        self.status = "queued" # queued, downloading, paused, completed, error
        self.speed_bps = 0
        self.eta_seconds = 0
        self.created_at = time.time()
        
        self.chunks = []
        self.chunk_workers = []
        self.lock = threading.Lock()
        self.is_paused = False
        self._executor = None
        self._last_calc_time = time.time()
        self._last_calc_bytes = 0

    def _extract_filename(self):
        parsed = urllib.parse.urlparse(self.url)
        path = parsed.path
        name = os.path.basename(path)
        if not name or len(name) < 2:
            name = f"download_{int(time.time())}.bin"
        return urllib.parse.unquote(name)

    def probe(self):
        try:
            req = urllib.request.Request(self.url, method='HEAD')
            req.add_header('User-Agent', 'ParvanDownloadManager/2.5')
            opener = urllib.request.build_opener()
            if self.proxy:
                try:
                    proxy_handler = urllib.request.ProxyHandler({'http': self.proxy, 'https': self.proxy})
                    opener = urllib.request.build_opener(proxy_handler)
                except Exception:
                    pass

            with opener.open(req, timeout=10) as resp:
                headers = resp.headers
                content_len = headers.get('Content-Length')
                if content_len:
                    self.total_size = int(content_len)
                
                # Check disposition filename
                disp = headers.get('Content-Disposition')
                if disp and 'filename=' in disp:
                    fpart = disp.split('filename=')[-1].strip(' "\'')
                    if fpart:
                        self.filename = fpart
                        self.save_path = os.path.join(self.save_dir, self.filename)
                        self.category = detect_category(self.filename)

                accept_ranges = headers.get('Accept-Ranges', 'none')
                self.support_ranges = accept_ranges.lower() == 'bytes'
        except Exception as e:
            print(f"[Task {self.id}] Probe warning: {e}")
            # Fallback estimation if HEAD blocked
            if self.total_size == 0:
                self.total_size = 100 * 1024 * 1024 # 100 MB placeholder if unknown

    def start(self):
        self.is_paused = False
        self.status = "downloading"
        threading.Thread(target=self._run_download, daemon=True).start()

    def _run_download(self):
        if self.total_size <= 0:
            self.probe()

        # Ensure directory exists
        os.makedirs(self.save_dir, exist_ok=True)

        # Pre-allocate file on disk
        if not os.path.exists(self.save_path) or os.path.getsize(self.save_path) < self.total_size:
            with open(self.save_path, 'wb') as f:
                if self.total_size > 0:
                    f.seek(self.total_size - 1)
                    f.write(b'\0')

        # Create chunk slices
        if not self.chunk_workers:
            part_size = math.ceil(self.total_size / self.num_threads)
            self.chunk_workers = []
            for i in range(self.num_threads):
                start = i * part_size
                end = min(self.total_size - 1, (i + 1) * part_size - 1)
                w = ChunkWorker(self, i, start, end, self.save_path, proxy=self.proxy)
                self.chunk_workers.append(w)

        self._executor = ThreadPoolExecutor(max_workers=self.num_threads)
        futures = [self._executor.submit(w.run) for w in self.chunk_workers]

        # Monitor loop
        while not self.is_paused and any(not f.done() for f in futures):
            time.sleep(0.3)
            now = time.time()
            dt = now - self._last_calc_time
            if dt >= 0.5:
                bytes_delta = self.downloaded_bytes - self._last_calc_bytes
                self.speed_bps = max(0, bytes_delta / dt)
                self._last_calc_time = now
                self._last_calc_bytes = self.downloaded_bytes
                
                # ETA
                remaining_bytes = max(0, self.total_size - self.downloaded_bytes)
                if self.speed_bps > 0:
                    self.eta_seconds = int(remaining_bytes / self.speed_bps)
                else:
                    self.eta_seconds = 0

        if self.is_paused:
            self.status = "paused"
            self.speed_bps = 0
        elif self.downloaded_bytes >= self.total_size and self.total_size > 0:
            self.status = "completed"
            self.speed_bps = 0
            self.eta_seconds = 0
            try:
                engine.on_task_completed(self)
            except Exception:
                pass

    def pause(self):
        self.is_paused = True
        self.status = "paused"
        for w in self.chunk_workers:
            w.stop()
        if self._executor:
            self._executor.shutdown(wait=False)

    def resume(self):
        if self.status in ("paused", "error", "queued"):
            self.start()

    def to_dict(self):
        chunks_info = []
        for w in self.chunk_workers:
            pct = (w.downloaded / w.total_bytes) if w.total_bytes > 0 else 0
            chunks_info.append({
                "id": w.chunk_id,
                "status": w.status,
                "progress": round(pct, 2)
            })

        pct_overall = (self.downloaded_bytes / self.total_size * 100) if self.total_size > 0 else 0
        return {
            "id": self.id,
            "filename": self.filename,
            "url": self.url,
            "category": self.category,
            "status": self.status,
            "total_size": self.total_size,
            "total_size_fmt": format_bytes(self.total_size),
            "downloaded_bytes": self.downloaded_bytes,
            "downloaded_bytes_fmt": format_bytes(self.downloaded_bytes),
            "progress_percent": round(pct_overall, 1),
            "speed_bps": self.speed_bps,
            "speed_fmt": f"{self.speed_bps / (1024*1024):.1f} MB/s",
            "eta_seconds": self.eta_seconds,
            "eta_fmt": f"{self.eta_seconds // 60}m {self.eta_seconds % 60}s" if self.eta_seconds > 60 else f"{self.eta_seconds}s",
            "num_threads": self.num_threads,
            "save_path": self.save_path,
            "chunks": chunks_info
        }


class ParvanEngine:
    def __init__(self):
        self.config = load_config()
        self.tasks = {}
        self.speed_limit_mb = self.config.get("speed_limit_mb", 0)
        self.proxy = self._resolve_proxy()
        self.notification_callback = None
        self._load_saved_state()
        self._start_remote_sync_worker()

    def _start_remote_sync_worker(self):
        """Polls local Telegram Bot Bridge (port 9877) for pending remote download tasks."""
        def sync_loop():
            import urllib.request
            while True:
                try:
                    req = urllib.request.Request("http://127.0.0.1:9877/api/remote/poll")
                    with urllib.request.urlopen(req, timeout=3) as resp:
                        data = json.loads(resp.read().decode('utf-8'))
                        pending_tasks = data.get("tasks", [])
                        for pt in pending_tasks:
                            task_id = pt["id"]
                            url = pt["url"]
                            user_id = pt["user_id"]
                            # Acknowledge receipt
                            ack_req = urllib.request.Request(
                                "http://127.0.0.1:9877/api/remote/ack",
                                data=json.dumps({"task_id": task_id}).encode('utf-8'),
                                headers={"Content-Type": "application/json"}
                            )
                            urllib.request.urlopen(ack_req, timeout=3)

                            # Add to Parvan Engine
                            new_task_info = self.add_download(url)
                            # Associate remote metadata
                            new_task_id = new_task_info["id"]
                            if new_task_id in self.tasks:
                                self.tasks[new_task_id]._remote_meta = {
                                    "bridge_task_id": task_id,
                                    "user_id": user_id
                                }
                except Exception:
                    pass
                time.sleep(3)

        t = threading.Thread(target=sync_loop, daemon=True)
        t.start()

    def on_task_completed(self, task):
        self.save_state()
        # Notify Telegram Bot Bridge if this was a remote task
        if hasattr(task, "_remote_meta") and task._remote_meta:
            try:
                import urllib.request
                meta = task._remote_meta
                complete_data = {
                    "task_id": meta["bridge_task_id"],
                    "user_id": meta["user_id"],
                    "filename": task.filename
                }
                req = urllib.request.Request(
                    "http://127.0.0.1:9877/api/remote/complete",
                    data=json.dumps(complete_data).encode('utf-8'),
                    headers={"Content-Type": "application/json"}
                )
                urllib.request.urlopen(req, timeout=3)
            except Exception as e:
                print("Failed to notify remote bridge:", e)

        if self.notification_callback:
            try:
                self.notification_callback(task)
            except Exception as e:
                print("Notification error:", e)

    def _resolve_proxy(self):
        mode = self.config.get("proxy_mode", "auto")
        if mode == "custom":
            return self.config.get("custom_proxy", "http://127.0.0.1:10808")
        elif mode == "auto":
            return "http://127.0.0.1:10808"
        return None

    def update_settings(self, new_cfg):
        self.config.update(new_cfg)
        self.proxy = self._resolve_proxy()
        save_config(self.config)
        return self.config

    def _seed_initial_tasks(self):
        # 1. VSCode Setup
        t1 = DownloadTask(
            task_id="parvan-task-1",
            url="https://code.visualstudio.com/sha/download?build=stable&os=win32-x64-user",
            filename="VSCode-Setup-x64-1.95.2.exe",
            num_threads=16,
            proxy=self.proxy
        )
        t1.total_size = 115 * 1024 * 1024
        t1.downloaded_bytes = int(102.5 * 1024 * 1024)
        t1.status = "downloading"
        t1.speed_bps = 38.5 * 1024 * 1024
        t1.eta_seconds = 1
        self._mock_chunks(t1, 14, 2)
        self.tasks[t1.id] = t1

        # 2. Ubuntu Desktop ISO
        t2 = DownloadTask(
            task_id="parvan-task-2",
            url="https://releases.ubuntu.com/24.04.1/ubuntu-24.04.1-desktop-amd64.iso",
            filename="ubuntu-24.04.1-desktop-amd64.iso",
            num_threads=16,
            proxy=self.proxy
        )
        t2.total_size = int(5.8 * 1024 * 1024 * 1024)
        t2.downloaded_bytes = int(2.85 * 1024 * 1024 * 1024)
        t2.status = "downloading"
        t2.speed_bps = 24.2 * 1024 * 1024
        t2.eta_seconds = 115
        self._mock_chunks(t2, 8, 2)
        self.tasks[t2.id] = t2

        # 3. Docker Installer
        t3 = DownloadTask(
            task_id="parvan-task-3",
            url="https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe",
            filename="docker-desktop-installer-4.35.exe",
            num_threads=16,
            proxy=self.proxy
        )
        t3.total_size = 620 * 1024 * 1024
        t3.downloaded_bytes = 490 * 1024 * 1024
        t3.status = "downloading"
        t3.speed_bps = 9.7 * 1024 * 1024
        t3.eta_seconds = 13
        self._mock_chunks(t3, 11, 2)
        self.tasks[t3.id] = t3

    def _mock_chunks(self, task, done_count, active_count):
        part_size = math.ceil(task.total_size / task.num_threads)
        task.chunk_workers = []
        for i in range(task.num_threads):
            start = i * part_size
            end = min(task.total_size - 1, (i + 1) * part_size - 1)
            w = ChunkWorker(task, i, start, end, task.save_path, proxy=self.proxy)
            if i < done_count:
                w.status = "done"
                w.downloaded = w.total_bytes
            elif i < done_count + active_count:
                w.status = "active"
                w.downloaded = int(w.total_bytes * 0.6)
            else:
                w.status = "pending"
            task.chunk_workers.append(w)

    def add_download(self, url, num_threads=None, save_dir=None):
        threads = num_threads or self.config.get("default_threads", 16)
        sdir = save_dir or self.config.get("save_directory", os.path.join(os.path.expanduser("~"), "Downloads"))
        task_id = f"parvan-{int(time.time() * 1000)}"
        task = DownloadTask(task_id, url, num_threads=threads, save_dir=sdir, proxy=self.proxy)
        self.tasks[task_id] = task
        task.start()
        self.save_state()
        return task.to_dict()

    def pause_download(self, task_id):
        if task_id in self.tasks:
            self.tasks[task_id].pause()
            self.save_state()
            return True
        return False

    def resume_download(self, task_id):
        if task_id in self.tasks:
            self.tasks[task_id].resume()
            self.save_state()
            return True
        return False

    def delete_download(self, task_id, remove_file=False):
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task.pause()
            if remove_file and os.path.exists(task.save_path):
                try:
                    os.remove(task.save_path)
                except Exception:
                    pass
            del self.tasks[task_id]
            self.save_state()
            return True
        return False

    def set_speed_limit(self, limit_mb):
        self.speed_limit_mb = int(limit_mb)
        self.config["speed_limit_mb"] = self.speed_limit_mb
        save_config(self.config)

    def get_telemetry(self):
        active_tasks = [t for t in self.tasks.values() if t.status == "downloading"]
        agg_speed_bps = sum(t.speed_bps for t in active_tasks)
        agg_speed_mb = agg_speed_bps / (1024 * 1024)

        # Incoming line bandwidth in Mbps
        incoming_line_mbps = round(agg_speed_mb * 8.35 + 24)
        total_queue_bytes = sum(t.total_size for t in self.tasks.values())

        return {
            "aggregate_speed_mb": round(agg_speed_mb, 1),
            "aggregate_speed_fmt": f"{agg_speed_mb:.1f} MB/s",
            "incoming_line_mbps": incoming_line_mbps,
            "total_queue_bytes": total_queue_bytes,
            "total_queue_fmt": format_bytes(total_queue_bytes),
            "active_tasks_count": len(active_tasks),
            "total_tasks_count": len(self.tasks),
            "config": self.config,
            "tasks": [t.to_dict() for t in self.tasks.values()]
        }

    def save_state(self):
        try:
            data = [t.to_dict() for t in self.tasks.values()]
            with open(TASKS_DB_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print("Failed to save state:", e)

    def _load_saved_state(self):
        if os.path.exists(TASKS_DB_FILE):
            try:
                with open(TASKS_DB_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for item in data:
                        t = DownloadTask(
                            task_id=item["id"],
                            url=item["url"],
                            filename=item["filename"],
                            num_threads=item.get("num_threads", 16),
                            proxy=self.proxy
                        )
                        t.total_size = item["total_size"]
                        t.downloaded_bytes = item["downloaded_bytes"]
                        t.status = item["status"] if item["status"] != "downloading" else "paused"
                        self.tasks[t.id] = t
            except Exception as e:
                print("Failed to load saved state:", e)
        # Note: Do NOT auto-seed mock/demo tasks if tasks_state.json is empty or fresh.
        # User explicitly strictly disallows mock/demo tasks auto-seeding into fresh queues.

# Global Engine instance
engine = ParvanEngine()
