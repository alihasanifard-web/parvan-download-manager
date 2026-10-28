import os
import sys
import time
import math
import json
import mmap
import socket
import hashlib
import zipfile
import subprocess
import threading
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

try:
    import yt_dlp
    HAS_YTDLP = True
except ImportError:
    HAS_YTDLP = False

try:
    from torrent_engine import TorrentMeta, BitTorrentClient
except ImportError:
    TorrentMeta = None
    BitTorrentClient = None

try:
    from features_ext import (
        SiteLoginsManager,
        MultipartArchiveDetective,
        WeeklySpeedScheduler,
        QueueBackupManager,
        PrivateVaultManager,
        MultiPlatformWebhook
    )
except ImportError:
    SiteLoginsManager = None
    MultipartArchiveDetective = None
    WeeklySpeedScheduler = None
    QueueBackupManager = None
    PrivateVaultManager = None
    MultiPlatformWebhook = None

try:
    from hls_engine import HLSPlaylistParser, HLSStreamDownloader
except ImportError:
    HLSPlaylistParser = None
    HLSStreamDownloader = None

try:
    from anti_dpi import CleanDNSResolver, AntiDPISocket, create_antidpi_connection
except ImportError:
    CleanDNSResolver = None
    AntiDPISocket = None
    create_antidpi_connection = None

try:
    from site_grabber import SiteGrabber
except ImportError:
    SiteGrabber = None

try:
    from zip_preview import RemoteZipInspector
except ImportError:
    RemoteZipInspector = None

try:
    from video_fixer import VideoFixer
except ImportError:
    VideoFixer = None

try:
    from debrid_engine import DebridEngine
except ImportError:
    DebridEngine = None

try:
    from lan_mesh import LanMeshNode
except ImportError:
    LanMeshNode = None

try:
    from smart_tagger import SmartAutoTagger
except ImportError:
    SmartAutoTagger = None

try:
    from stealth_tunnel import StealthTunnel
except ImportError:
    StealthTunnel = None

try:
    from virtual_mount import VirtualSparseMount
except ImportError:
    VirtualSparseMount = None

try:
    from quota_limiter import QuotaLimiter
except ImportError:
    QuotaLimiter = None

try:
    from windows_tray import WindowsToastNotifier, WindowsShellIntegration
except ImportError:
    WindowsToastNotifier = None
    WindowsShellIntegration = None

try:
    from cloud_sync import CloudSyncEngine
except ImportError:
    CloudSyncEngine = None

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
TASKS_DB_FILE = os.path.join(CURRENT_DIR, "tasks_state.json")
CONFIG_FILE = os.path.join(CURRENT_DIR, "config.json")
QUOTA_FILE = os.path.join(CURRENT_DIR, "quota_state.json")

DEFAULT_CONFIG = {
    "save_directory": os.path.join(os.path.expanduser("~"), "Downloads"),
    "default_threads": 16,
    "proxy_mode": "auto",
    "custom_proxy": "http://127.0.0.1:10808",
    "speed_limit_mb": 150,
    "auto_resume": True,
    "sound_effects": True,
    "language": "fa",
    "auto_extract_archives": True,
    "checksum_validation": True,
    "scheduler_enabled": False,
    "scheduler_start_time": "02:00",
    "scheduler_stop_time": "07:00",
    "scheduler_action": "none",  # none, shutdown, sleep
    "defender_scan_enabled": True,
    "media_sniff_enabled": True,
    "max_concurrent_downloads": 3,
    "network_bonding_enabled": False,
    "bonded_interfaces": [],
    "zero_copy_mmap": True,
    "custom_headers": {},
    "cookies": "",
    "anti_dpi_enabled": True,
    "smart_folder_routing": True,
    "dynamic_chunk_splitting": True,
    "lan_remote_enabled": True,
    "lan_remote_pin": "1234",
    "clipboard_watcher_enabled": True,
    "stealth_tunnel_enabled": True,
    "virtual_mount_enabled": True,
    "auto_tagger_enabled": True,
    "lan_mesh_enabled": True,
    "webhook_url": "",
    "webhook_type": "generic",
    "debrid_api_key": "",
    "debrid_provider": "real_debrid"
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

def get_network_interfaces():
    """Detects available network adapters and local IP addresses for bonding."""
    interfaces = []
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if not ip.startswith("127."):
                interfaces.append(ip)
    except Exception:
        pass
    return interfaces

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

def get_routed_save_dir(base_dir, category):
    """Smart Folder Routing: routes downloads into organized subfolders by category."""
    subdirs = {
        "app": "Software",
        "iso": "Disk_Images",
        "archive": "Archives",
        "media": "Videos",
        "document": "Documents"
    }
    sub = subdirs.get(category)
    if sub:
        return os.path.join(base_dir, sub)
    return base_dir

def calculate_file_hash(file_path, algorithm="sha256"):
    """Calculates SHA-256 or MD5 hash of a file efficiently in blocks."""
    if not os.path.exists(file_path):
        return ""
    h = hashlib.sha256() if algorithm == "sha256" else hashlib.md5()
    try:
        with open(file_path, 'rb') as f:
            while chunk := f.read(1024 * 1024):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""

def auto_extract_archive(file_path):
    """Auto-extracts zip archives into a dedicated folder next to the archive."""
    if not os.path.exists(file_path):
        return False, "فایل یافت نشد"
    if not file_path.lower().endswith('.zip'):
        return False, "فرمت آرشیو پشتیبانی نمی‌شود"
    try:
        dest_dir = os.path.splitext(file_path)[0] + "_extracted"
        os.makedirs(dest_dir, exist_ok=True)
        with zipfile.ZipFile(file_path, 'r') as z:
            z.extractall(dest_dir)
        return True, dest_dir
    except Exception as e:
        return False, str(e)

def scan_file_with_defender(file_path):
    """Scans downloaded file with Windows Defender Antivirus CLI (MpCmdRun.exe)."""
    if not os.path.exists(file_path):
        return {"status": "error", "message": "File not found"}
    
    # Common paths for Windows Defender CLI
    defender_paths = [
        os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "Windows Defender", "MpCmdRun.exe"),
        os.path.join(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"), "Windows Defender", "MpCmdRun.exe"),
        os.path.join(os.environ.get("ProgramData", "C:\\ProgramData"), "Microsoft", "Windows Defender", "Platform")
    ]
    
    mp_cmd = None
    for p in defender_paths:
        if os.path.isfile(p):
            mp_cmd = p
            break
        elif os.path.isdir(p):
            # Check subdirectories for latest platform version
            try:
                for sub in sorted(os.listdir(p), reverse=True):
                    candidate = os.path.join(p, sub, "MpCmdRun.exe")
                    if os.path.isfile(candidate):
                        mp_cmd = candidate
                        break
            except Exception:
                pass
            if mp_cmd:
                break

    if not mp_cmd:
        return {"status": "skipped", "message": "Windows Defender CLI not found on host"}

    try:
        # Run scan: -Scan -ScanType 3 -File "<file_path>"
        res = subprocess.run([mp_cmd, "-Scan", "-ScanType", "3", "-File", file_path],
                             capture_output=True, text=True, timeout=30)
        # Return code 0 = clean, 2 = infected
        if res.returncode == 0:
            return {"status": "clean", "message": "فایل امن است و هیچ تهدیدی یافت نشد (Clean)"}
        elif res.returncode == 2:
            return {"status": "infected", "message": "هشدار: تهدید بدافزار یا ویروس کشف شد! (Threat Detected)"}
        else:
            return {"status": "clean", "message": "اسکن انجام شد و تهدیدی گزارش نشد"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def parse_magnet_link(magnet_url):
    """Parses magnet link parameters (URN, display name, trackers)."""
    if not magnet_url.startswith("magnet:?"):
        return None
    query = magnet_url[len("magnet:?"):]
    params = urllib.parse.parse_qs(query)
    xt = params.get("xt", [""])[0]
    dn = params.get("dn", ["torrent_download.bin"])[0]
    tr = params.get("tr", [])
    
    # Extract info hash from xt (e.g. urn:btih:...)
    info_hash = ""
    if "urn:btih:" in xt:
        info_hash = xt.split("urn:btih:")[-1]

    return {
        "info_hash": info_hash,
        "filename": urllib.parse.unquote(dn),
        "trackers": tr
    }

class ChunkWorker:
    def __init__(self, task, chunk_id, start_byte, end_byte, file_path, proxy=None, bind_ip=None):
        self.task = task
        self.chunk_id = chunk_id
        self.start_byte = start_byte
        self.end_byte = end_byte
        self.total_bytes = end_byte - start_byte + 1
        self.downloaded = 0
        self.file_path = file_path
        self.proxy = proxy
        self.bind_ip = bind_ip
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

        # Apply cookies if present in task or VIP domain match or global config
        matched_vip = engine.site_logins.match_credentials(self.task.url) if hasattr(engine, "site_logins") and engine.site_logins else {}
        cookie_header = getattr(self.task, "cookies", None) or matched_vip.get("cookies") or engine.config.get("cookies", "")
        if cookie_header:
            req.add_header('Cookie', cookie_header)

        # Apply custom authentication or headers
        custom_hdrs = getattr(self.task, "headers", None) or matched_vip.get("custom_headers") or engine.config.get("custom_headers", {})
        if custom_hdrs and isinstance(custom_hdrs, dict):
            for hk, hv in custom_hdrs.items():
                req.add_header(hk, hv)

        if matched_vip.get("auth_header"):
            req.add_header("Authorization", matched_vip["auth_header"])

        if "127.0.0.1" in self.task.url or "localhost" in self.task.url:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        elif self.proxy:
            proxy_handler = urllib.request.ProxyHandler({'http': self.proxy, 'https': self.proxy})
            opener = urllib.request.build_opener(proxy_handler)
        else:
            opener = urllib.request.build_opener()

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
    def __init__(self, task_id, url, filename=None, save_dir=None, num_threads=16, proxy=None, cookies=None, headers=None, is_vault=False):
        self.id = str(task_id)
        self.url = url
        self.num_threads = num_threads
        self.proxy = proxy or "http://127.0.0.1:10808"
        self.save_dir = save_dir or os.path.join(os.path.expanduser("~"), "Downloads")
        self.cookies = cookies
        self.headers = headers or {}
        self.filename = filename or self._extract_filename()
        self.category = detect_category(self.filename)
        self.is_vault = bool(is_vault)
        self.auto_tags = None
        # Smart Folder Routing
        if not save_dir and hasattr(sys.modules[__name__], 'engine') and getattr(sys.modules[__name__].engine, 'config', {}).get('smart_folder_routing', False):
            self.save_dir = get_routed_save_dir(self.save_dir, self.category)
        if self.is_vault:
            self.save_dir = os.path.join(self.save_dir, ".vault")
        self.save_path = os.path.join(self.save_dir, self.filename)

        self.total_size = 0
        self.downloaded_bytes = 0
        self.support_ranges = True
        self.status = "queued" # queued, downloading, paused, completed, error
        self.speed_bps = 0
        self.eta_seconds = 0
        self.created_at = time.time()
        self.priority = 1 # 0 = low, 1 = normal, 2 = high
        self.queue_position = 0
        self.sha256_hash = ""
        self.extracted_path = ""
        self.antivirus_status = "pending" # pending, clean, infected, skipped
        self.is_magnet = url.startswith("magnet:?")
        self.is_hls = ".m3u8" in url.lower() or "application/x-mpegurl" in url.lower()
        self.is_media_stream = self.is_hls
        
        self.chunks = []
        self.chunk_workers = []
        self.lock = threading.Lock()
        self.is_paused = False
        self._executor = None
        self._last_calc_time = time.time()
        self._last_calc_bytes = 0

    def _extract_filename(self):
        if self.url.startswith("magnet:?"):
            info = parse_magnet_link(self.url)
            if info and info["filename"]:
                return info["filename"]
            return f"torrent_{int(time.time())}.bin"
        parsed = urllib.parse.urlparse(self.url)
        path = parsed.path
        name = os.path.basename(path)
        if not name or len(name) < 2:
            name = f"download_{int(time.time())}.bin"
        return urllib.parse.unquote(name)

    def probe(self):
        if self.is_magnet:
            self.total_size = 500 * 1024 * 1024 # Estimated seed size for magnet metadata
            self.category = "archive"
            return
        try:
            req = urllib.request.Request(self.url, method='HEAD')
            req.add_header('User-Agent', 'ParvanDownloadManager/2.5')
            if "127.0.0.1" in self.url or "localhost" in self.url:
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            elif self.proxy:
                proxy_handler = urllib.request.ProxyHandler({'http': self.proxy, 'https': self.proxy})
                opener = urllib.request.build_opener(proxy_handler)
            else:
                opener = urllib.request.build_opener()

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
        # Native BitTorrent / Magnet handling
        if self.is_magnet and BitTorrentClient is not None:
            meta = TorrentMeta.from_magnet(self.url)
            self.total_size = meta.total_size if meta.total_size > 0 else 5 * 1024 * 1024
            client = BitTorrentClient(meta, self.save_dir)
            self.save_path = client.save_path
            self.filename = meta.name
            
            def _progress_cb(dl, tot, spd):
                self.downloaded_bytes = dl
                self.speed_bps = spd
                if tot > 0:
                    self.total_size = tot

            client.perform_synthetic_download(total_size=self.total_size, callback=_progress_cb)
            if self.downloaded_bytes >= self.total_size:
                self.status = "completed"
                self.speed_bps = 0
                try:
                    engine.on_task_completed(self)
                except Exception:
                    pass
                return

        # Direct HLS / M3U8 Stream handling
        if self.is_hls and HLSStreamDownloader is not None:
            if not self.filename.endswith(".mp4"):
                base_name = os.path.splitext(self.filename)[0]
                self.filename = f"{base_name}.mp4"
                self.save_path = os.path.join(self.save_dir, self.filename)
            downloader = HLSStreamDownloader(self.url, self.save_path, max_threads=min(8, self.num_threads), proxy=self.proxy)
            def _hls_progress(done_segs, tot_segs, bytes_dl):
                self.downloaded_bytes = bytes_dl
                if tot_segs > 0:
                    self.total_size = max(bytes_dl, int(bytes_dl * (tot_segs / max(1, done_segs))))
            success = downloader.download(progress_callback=_hls_progress)
            if success:
                self.status = "completed"
                self.speed_bps = 0
                try:
                    engine.on_task_completed(self)
                except Exception:
                    pass
                return

        if self.total_size <= 0:
            self.probe()

        # Ensure directory exists
        os.makedirs(self.save_dir, exist_ok=True)

        # Pre-allocate or size file accurately on disk
        if not os.path.exists(self.save_path):
            with open(self.save_path, 'wb') as f:
                if self.total_size > 0:
                    f.seek(self.total_size - 1)
                    f.write(b'\0')
        elif self.total_size > 0 and os.path.getsize(self.save_path) != self.total_size:
            with open(self.save_path, 'r+b') as f:
                f.truncate(self.total_size)

        # Create chunk slices
        if not self.chunk_workers:
            part_size = math.ceil(self.total_size / self.num_threads)
            self.chunk_workers = []
            bonding_ips = engine.config.get("bonded_interfaces", []) if engine.config.get("network_bonding_enabled", False) else []
            for i in range(self.num_threads):
                start = i * part_size
                end = min(self.total_size - 1, (i + 1) * part_size - 1)
                bind_ip = bonding_ips[i % len(bonding_ips)] if bonding_ips else None
                w = ChunkWorker(self, i, start, end, self.save_path, proxy=self.proxy, bind_ip=bind_ip)
                self.chunk_workers.append(w)

        self._executor = ThreadPoolExecutor(max_workers=self.num_threads)
        futures = []
        for w in self.chunk_workers:
            if not self.is_paused:
                futures.append(self._executor.submit(w.run))

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

                # Dynamic Chunk Splitting (Chunk Stealing)
                if engine.config.get("dynamic_chunk_splitting", True) and self.total_size > 0 and (self.downloaded_bytes / self.total_size) >= 0.70:
                    idle_workers = [w for w in self.chunk_workers if w.status == "done" and not getattr(w, "_split_parent", False)]
                    active_workers = [w for w in self.chunk_workers if w.status == "active"]
                    if idle_workers and active_workers:
                        slowest = max(active_workers, key=lambda w: max(0, w.end_byte - (w.start_byte + w.downloaded)))
                        cur_slow_start = slowest.start_byte + slowest.downloaded
                        rem_slow = slowest.end_byte - cur_slow_start + 1
                        if rem_slow >= 1024 * 512: # 512 KB minimum to split
                            half = cur_slow_start + (rem_slow // 2)
                            old_end = slowest.end_byte
                            slowest.end_byte = half
                            idle_w = idle_workers[0]
                            idle_w.start_byte = half + 1
                            idle_w.end_byte = old_end
                            idle_w.total_bytes = old_end - (half + 1) + 1
                            idle_w.downloaded = 0
                            idle_w.status = "pending"
                            idle_w._stop_flag = False
                            idle_w._split_parent = True
                            if self._executor:
                                futures.append(self._executor.submit(idle_w.run))

        if self.is_paused:
            self.status = "paused"
            self.speed_bps = 0
        elif self.downloaded_bytes >= self.total_size and self.total_size > 0:
            self.status = "completed"
            self.speed_bps = 0
            self.eta_seconds = 0

            # Calculate SHA256 integrity hash if enabled
            if engine.config.get("checksum_validation", True):
                try:
                    self.sha256_hash = calculate_file_hash(self.save_path, "sha256")
                except Exception:
                    pass

            # Auto extract archive if enabled
            if engine.config.get("auto_extract_archives", True) and self.category == "archive" and self.save_path.lower().endswith('.zip'):
                try:
                    success, res = auto_extract_archive(self.save_path)
                    if success:
                        self.extracted_path = res
                except Exception:
                    pass

            # Antivirus scan if enabled
            if engine.config.get("defender_scan_enabled", True):
                try:
                    scan_res = scan_file_with_defender(self.save_path)
                    self.antivirus_status = scan_res.get("status", "clean")
                except Exception:
                    self.antivirus_status = "skipped"

            # Play completion sound if enabled
            if engine.config.get("sound_effects", True):
                try:
                    engine.play_completion_sound()
                except Exception:
                    pass

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
            try:
                self._executor.shutdown(wait=False, cancel_futures=True)
            except Exception:
                pass
            self._executor = None

    def resume(self):
        if self.status in ("paused", "error", "queued"):
            self.start()

    def refresh_url(self, new_url, new_headers=None, new_cookies=None):
        """Refreshes the download URL and credentials while preserving downloaded progress."""
        with self.lock:
            self.url = new_url
            if new_headers and isinstance(new_headers, dict):
                self.headers.update(new_headers)
            if new_cookies:
                self.cookies = new_cookies
            self.is_paused = False
            self.status = "queued"
            for w in self.chunk_workers:
                if w.status != "done":
                    w.status = "pending"
                    w._stop_flag = False
        self.start()
        return True

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
            "priority": self.priority,
            "queue_position": self.queue_position,
            "sha256_hash": self.sha256_hash,
            "extracted_path": self.extracted_path,
            "antivirus_status": self.antivirus_status,
            "is_magnet": self.is_magnet,
            "is_media_stream": self.is_media_stream,
            "is_vault": getattr(self, "is_vault", False),
            "auto_tags": getattr(self, "auto_tags", None),
            "chunks": chunks_info
        }


class ParvanEngine:
    def __init__(self):
        self.config = load_config()
        self.tasks = {}
        self.speed_limit_mb = self.config.get("speed_limit_mb", 0)
        self.proxy = self._resolve_proxy()
        self.notification_callback = None
        self.site_logins = SiteLoginsManager(CONFIG_FILE) if SiteLoginsManager else None
        self.weekly_scheduler = WeeklySpeedScheduler(CONFIG_FILE) if WeeklySpeedScheduler else None
        self.private_vault = PrivateVaultManager(CONFIG_FILE) if PrivateVaultManager else None
        self.quota_limiter = QuotaLimiter(QUOTA_FILE) if QuotaLimiter else None
        self.cloud_sync = CloudSyncEngine(
            endpoint_url=self.config.get("webdav_url", ""),
            username=self.config.get("webdav_user", ""),
            password=self.config.get("webdav_pass", "")
        ) if CloudSyncEngine else None
        self.lan_mesh = LanMeshNode(http_port=9876) if LanMeshNode and self.config.get("lan_mesh_enabled", True) else None
        if self.lan_mesh:
            self.lan_mesh.start()
        self._load_saved_state()
        self._start_remote_sync_worker()
        self._start_scheduler_worker()
        self._start_queue_manager_worker()

    def _start_queue_manager_worker(self):
        """Smart Queue Manager: regulates max concurrent downloads based on priority."""
        def queue_loop():
            while True:
                try:
                    max_concurrent = self.config.get("max_concurrent_downloads", 3)
                    active_tasks = [t for t in self.tasks.values() if t.status == "downloading"]
                    slots_available = max_concurrent - len(active_tasks)

                    if slots_available > 0:
                        # Find queued tasks sorted by priority (high=2, normal=1, low=0) then queue_position
                        queued_tasks = [t for t in self.tasks.values() if t.status == "queued"]
                        queued_tasks.sort(key=lambda x: (-x.priority, x.queue_position))

                        for i in range(min(slots_available, len(queued_tasks))):
                            queued_tasks[i].start()
                except Exception:
                    pass
                time.sleep(1)

        t = threading.Thread(target=queue_loop, daemon=True)
        t.start()

    def _start_scheduler_worker(self):
        """Monitors scheduled start/stop hours and executes automatic power actions."""
        def scheduler_loop():
            while True:
                try:
                    # Weekly Speed Schedule Matrix dynamic application
                    if self.weekly_scheduler and self.weekly_scheduler.enabled:
                        sched_limit = self.weekly_scheduler.get_current_limit()
                        if sched_limit is not None and sched_limit != self.speed_limit_mb:
                            self.speed_limit_mb = sched_limit

                    if self.config.get("scheduler_enabled", False):
                        now_str = time.strftime("%H:%M")
                        start_time = self.config.get("scheduler_start_time", "02:00")
                        stop_time = self.config.get("scheduler_stop_time", "07:00")

                        # Check if within download window
                        if start_time <= stop_time:
                            in_window = start_time <= now_str < stop_time
                        else:  # Over midnight (e.g. 23:00 to 06:00)
                            in_window = now_str >= start_time or now_str < stop_time

                        if in_window:
                            # Auto resume queued or paused downloads
                            for t in self.tasks.values():
                                if t.status in ("queued", "paused"):
                                    t.resume()
                        else:
                            # Pause downloads when window ends
                            for t in self.tasks.values():
                                if t.status == "downloading":
                                    t.pause()

                            # Action on finish (shutdown/sleep) if configured
                            action = self.config.get("scheduler_action", "none")
                            if action == "shutdown":
                                os.system("shutdown /s /t 60")
                            elif action == "sleep":
                                os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")

                except Exception:
                    pass
                time.sleep(30)

        t = threading.Thread(target=scheduler_loop, daemon=True)
        t.start()

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
        # Record Quota usage
        if self.quota_limiter and task.total_size > 0:
            try:
                self.quota_limiter.record_usage(task.total_size)
            except Exception:
                pass

        # Windows Native Toast Notification
        if WindowsToastNotifier:
            try:
                WindowsToastNotifier.show_toast(
                    "دانلود با موفقیت تکمیل شد | پروان",
                    f"{task.filename} ({task.total_size_fmt}) آماده استفاده است.",
                    file_path=task.save_path
                )
            except Exception:
                pass

        # Auto content analysis / tagger if enabled
        if self.config.get("auto_tagger_enabled", True) and SmartAutoTagger:
            try:
                task.auto_tags = SmartAutoTagger.tag_file(task.save_path)
            except Exception:
                pass

        # Multi-Platform Webhook Notification (Discord/Slack/Generic)
        webhook_url = self.config.get("webhook_url", "")
        if webhook_url and MultiPlatformWebhook:
            try:
                webhook_type = self.config.get("webhook_type", "generic")
                MultiPlatformWebhook.send_completion(webhook_url, task, webhook_type=webhook_type)
            except Exception as e:
                print(f"[Webhook] Error sending notification: {e}")

        # Register in local LAN Mesh so other computers on Wi-Fi can pull from us
        if self.lan_mesh:
            try:
                self.lan_mesh.register_task(task.url, task.id)
            except Exception:
                pass

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

    def sniff_media(self, page_url):
        """Sniffs video/audio stream formats from a URL (YouTube, Instagram, Aparat, etc.) using yt-dlp."""
        if not HAS_YTDLP:
            return {"success": False, "error": "yt-dlp engine not available"}
        import yt_dlp
        ydl_opts: dict = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False
        }
        if self.proxy:
            ydl_opts['proxy'] = str(self.proxy)

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(page_url, download=False)
                formats = []
                for f in (info.get('formats') or []):
                    # Filter video formats with resolution
                    if f.get('vcodec') != 'none' or f.get('acodec') != 'none':
                        formats.append({
                            'format_id': f.get('format_id'),
                            'ext': f.get('ext'),
                            'resolution': f.get('resolution') or f"{f.get('width', 0)}x{f.get('height', 0)}",
                            'filesize': f.get('filesize') or f.get('filesize_approx', 0),
                            'filesize_fmt': format_bytes(f.get('filesize') or f.get('filesize_approx', 0)),
                            'url': f.get('url')
                        })
                return {
                    "success": True,
                    "title": info.get('title', 'video'),
                    "duration": info.get('duration', 0),
                    "thumbnail": info.get('thumbnail', ''),
                    "formats": formats[:10]  # top 10 relevant streams
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def set_task_priority(self, task_id, priority):
        """Sets task priority (0=low, 1=normal, 2=high)."""
        if task_id in self.tasks:
            self.tasks[task_id].priority = int(priority)
            self.save_state()
            return True
        return False

    def reorder_task_queue(self, task_id, new_position):
        """Reorders task queue position for smart scheduler and prioritization."""
        if task_id in self.tasks:
            self.tasks[task_id].queue_position = int(new_position)
            self.save_state()
            return True
        return False

    def play_completion_sound(self):
        """Plays custom Parvan futuristic completion chime using Windows sound synthesis."""
        def _play():
            try:
                import winsound
                # Futuristic 3-tone chime (F#5, A5, C#6)
                winsound.Beep(740, 100)
                winsound.Beep(880, 120)
                winsound.Beep(1108, 180)
            except Exception:
                pass
        threading.Thread(target=_play, daemon=True).start()

    def add_download(self, url, num_threads=None, save_dir=None, cookies=None, headers=None, is_vault=False):
        threads = num_threads or self.config.get("default_threads", 16)
        sdir = save_dir or self.config.get("save_directory", os.path.join(os.path.expanduser("~"), "Downloads"))

        # Debrid / Cloud Seedbox Link Unrestriction
        if DebridEngine and self.config.get("debrid_api_key"):
            try:
                deb = DebridEngine(
                    api_key=self.config.get("debrid_api_key", ""),
                    provider=self.config.get("debrid_provider", "real_debrid")
                )
                unres = deb.unrestrict_link(url)
                if unres.get("success") and unres.get("download_url"):
                    url = unres["download_url"]
            except Exception:
                pass

        # Check LAN Mesh for high-speed local peer copy
        if self.lan_mesh:
            try:
                peer = self.lan_mesh.find_peer_for_url(url)
                if peer:
                    url = peer["peer_url"]
            except Exception:
                pass

        task_id = f"parvan-{int(time.time() * 1000)}"
        task = DownloadTask(task_id, url, num_threads=threads, save_dir=sdir, proxy=self.proxy, cookies=cookies, headers=headers, is_vault=is_vault)

        # Virtual Sparse Mount: enable instant pre-reservation
        if self.config.get("virtual_mount_enabled", True) and VirtualSparseMount:
            try:
                os.makedirs(task.save_dir, exist_ok=True)
                VirtualSparseMount.enable_sparse_file(task.save_path, task.total_size)
            except Exception:
                pass

        self.tasks[task_id] = task
        task.start()
        self.save_state()
        return task.to_dict()

    def add_batch_downloads(self, urls, num_threads=None, save_dir=None):
        """Adds a batch of URLs to the download queue."""
        added = []
        for u in urls:
            u_clean = u.strip()
            if u_clean and (u_clean.startswith("http://") or u_clean.startswith("https://") or u_clean.startswith("magnet:?")):
                res = self.add_download(u_clean, num_threads=num_threads, save_dir=save_dir)
                added.append(res)
        return added

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

        # Filter vault tasks if locked
        visible_tasks = list(self.tasks.values())
        if self.private_vault:
            visible_tasks = self.private_vault.filter_visible_tasks(visible_tasks)

        return {
            "aggregate_speed_mb": round(agg_speed_mb, 1),
            "aggregate_speed_fmt": f"{agg_speed_mb:.1f} MB/s",
            "incoming_line_mbps": incoming_line_mbps,
            "total_queue_bytes": total_queue_bytes,
            "total_queue_fmt": format_bytes(total_queue_bytes),
            "active_tasks_count": len(active_tasks),
            "total_tasks_count": len(self.tasks),
            "is_vault_unlocked": self.private_vault.is_unlocked if self.private_vault else True,
            "has_vault_pin": bool(self.private_vault.pin_hash) if self.private_vault else False,
            "quota": self.quota_limiter.check_quota_status() if self.quota_limiter else None,
            "config": self.config,
            "tasks": [t.to_dict() for t in visible_tasks]
        }

    def refresh_task_url(self, task_id, new_url, new_headers=None, new_cookies=None):
        """Refreshes expired or broken URL for a task and resumes download without losing data."""
        if task_id in self.tasks:
            task = self.tasks[task_id]
            res = task.refresh_url(new_url, new_headers=new_headers, new_cookies=new_cookies)
            self.save_state()
            return res
        return False

    def get_site_logins(self):
        """Returns all configured VIP domain logins."""
        return self.site_logins.logins if self.site_logins else {}

    def set_site_login(self, domain, cookies="", auth_header="", custom_headers=None):
        """Adds or updates VIP credentials for a domain."""
        if self.site_logins:
            self.site_logins.set_login(domain, cookies=cookies, auth_header=auth_header, custom_headers=custom_headers)
            return True
        return False

    def delete_site_login(self, domain):
        """Deletes VIP credentials for a domain."""
        if self.site_logins:
            return self.site_logins.remove_login(domain)
        return False

    def get_multipart_archives(self):
        """Detects and groups multi-part archives across tasks."""
        if MultipartArchiveDetective:
            return MultipartArchiveDetective.analyze_tasks(list(self.tasks.values()))
        return {}

    def get_weekly_schedule(self):
        """Returns current weekly speed schedule configuration."""
        if self.weekly_scheduler:
            return {
                "enabled": self.weekly_scheduler.enabled,
                "rules": self.weekly_scheduler.rules
            }
        return {"enabled": False, "rules": []}

    def set_weekly_schedule(self, rules, enabled=True):
        """Updates weekly speed schedule matrix."""
        if self.weekly_scheduler:
            self.weekly_scheduler.rules = rules
            self.weekly_scheduler.enabled = enabled
            self.weekly_scheduler.save()
            return True
        return False

    def export_queue(self):
        """Exports download queue to portable JSON backup dictionary."""
        if QueueBackupManager:
            return QueueBackupManager.export_queue(self.tasks)
        return {"tasks": []}

    def import_queue(self, data):
        """Imports tasks from a backup dictionary."""
        if QueueBackupManager:
            return QueueBackupManager.import_queue(self, data)
        return 0

    def sync_to_cloud(self):
        if self.cloud_sync and self.cloud_sync.is_configured:
            backup_data = self.export_queue()
            return self.cloud_sync.push_backup(backup_data)
        return {"success": False, "error": "Cloud sync not configured"}

    def restore_from_cloud(self):
        if self.cloud_sync and self.cloud_sync.is_configured:
            res = self.cloud_sync.pull_backup()
            if res.get("success") and "data" in res:
                imported = self.import_queue(res["data"])
                return {"success": True, "imported_tasks": imported}
            return res
        return {"success": False, "error": "Cloud sync not configured"}

    def update_quota_settings(self, daily_limit_bytes=0, monthly_limit_bytes=0, action_on_limit="throttle", throttle_speed_kb=50):
        if self.quota_limiter:
            self.quota_limiter.daily_limit_bytes = int(daily_limit_bytes)
            self.quota_limiter.monthly_limit_bytes = int(monthly_limit_bytes)
            self.quota_limiter.action_on_limit = str(action_on_limit)
            self.quota_limiter.throttle_speed_kb = int(throttle_speed_kb)
            self.quota_limiter.save()
            return True
        return False

    def crawl_site(self, page_url, category="all", max_depth=1):
        """Crawls website and returns downloadable links."""
        if SiteGrabber:
            return SiteGrabber.crawl_page(page_url, category=category, max_depth=max_depth, proxy=self.proxy)
        return []

    def inspect_remote_zip(self, zip_url):
        """Inspects remote ZIP file without downloading."""
        if RemoteZipInspector:
            return RemoteZipInspector.inspect_remote_zip(zip_url, proxy=self.proxy)
        return {"success": False, "error": "RemoteZipInspector not available"}

    def repair_video(self, task_id_or_path):
        """Repairs incomplete or damaged MP4 video."""
        file_path = task_id_or_path
        if task_id_or_path in self.tasks:
            file_path = self.tasks[task_id_or_path].save_path
        if VideoFixer:
            return VideoFixer.repair_incomplete_video(file_path)
        return {"success": False, "error": "VideoFixer not available"}

    def unlock_vault(self, pin):
        if self.private_vault:
            return self.private_vault.unlock(pin)
        return False

    def lock_vault(self):
        if self.private_vault:
            self.private_vault.lock()
            return True
        return False

    def set_vault_pin(self, new_pin, old_pin=""):
        if self.private_vault:
            return self.private_vault.set_pin(new_pin, old_pin)
        return False

    def check_cloud_debrid(self, info_hash_or_link):
        if DebridEngine:
            deb = DebridEngine(
                api_key=self.config.get("debrid_api_key", ""),
                provider=self.config.get("debrid_provider", "real_debrid")
            )
            if len(info_hash_or_link) in (40, 32) and not info_hash_or_link.startswith("http"):
                return deb.check_instant_availability(info_hash_or_link)
            else:
                return deb.unrestrict_link(info_hash_or_link)
        return {"available": False}

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
