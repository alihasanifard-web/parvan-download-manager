import os
import sys
import json
import time
import subprocess
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
import urllib.parse
from engine import engine

def get_clipboard_url():
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        txt = root.clipboard_get().strip()
        root.destroy()
        if txt.startswith("http://") or txt.startswith("https://"):
            return txt
    except Exception:
        pass
    return ""

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

class ParvanJsApi:
    """JavaScript API bridge exposed to the Webview window"""
    def get_telemetry(self):
        return engine.get_telemetry()

    def add_download(self, url, num_threads=16, save_dir=None, cookies=None, headers=None):
        return engine.add_download(url, num_threads=num_threads, save_dir=save_dir, cookies=cookies, headers=headers)

    def add_batch_downloads(self, urls, num_threads=16, save_dir=None):
        return engine.add_batch_downloads(urls, num_threads=num_threads, save_dir=save_dir)

    def play_sound(self):
        engine.play_completion_sound()
        return True

    def pause_download(self, task_id):
        return engine.pause_download(task_id)

    def resume_download(self, task_id):
        return engine.resume_download(task_id)

    def delete_download(self, task_id, remove_file=False):
        return engine.delete_download(task_id, remove_file=remove_file)

    def resume_all(self):
        for t in engine.tasks.values():
            if t.status == "paused" or t.status == "error":
                t.resume()
        engine.save_state()
        return True

    def pause_all(self):
        for t in engine.tasks.values():
            if t.status == "downloading":
                t.pause()
        engine.save_state()
        return True

    def set_priority(self, task_id, priority):
        return engine.set_task_priority(task_id, priority)

    def reorder_queue(self, task_id, new_pos):
        return engine.reorder_task_queue(task_id, new_pos)

    def get_network_interfaces(self):
        from engine import get_network_interfaces
        return get_network_interfaces()

    def update_settings(self, new_cfg):
        return engine.update_settings(new_cfg)

    def sniff_media(self, page_url):
        return engine.sniff_media(page_url)

    def scan_file(self, task_id):
        if task_id in engine.tasks:
            task = engine.tasks[task_id]
            if os.path.exists(task.save_path):
                from engine import scan_file_with_defender
                return scan_file_with_defender(task.save_path)
        return {"status": "error", "message": "Task not found"}

    def auto_extract(self, task_id):
        if task_id in engine.tasks:
            task = engine.tasks[task_id]
            if task.status == "completed" and os.path.exists(task.save_path):
                from engine import auto_extract_archive
                success, path_or_err = auto_extract_archive(task.save_path)
                return {"success": success, "path": path_or_err}
        return {"success": False, "error": "Task not found or not completed"}

    def get_file_checksum(self, task_id, algorithm="sha256"):
        if task_id in engine.tasks:
            task = engine.tasks[task_id]
            if os.path.exists(task.save_path):
                from engine import calculate_file_hash
                return {"hash": calculate_file_hash(task.save_path, algorithm)}
        return {"hash": ""}

    def open_folder(self, task_id):
        if task_id in engine.tasks:
            path = engine.tasks[task_id].save_path
            folder = os.path.dirname(path)
            if os.path.exists(folder):
                os.system(f'explorer /select,"{path}"')
                return True
        return False


# HTTP Request Handler for API & Static files
class ParvanHttpHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=CURRENT_DIR, **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/api/telemetry':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            data = json.dumps(engine.get_telemetry(), ensure_ascii=False)
            self.wfile.write(data.encode('utf-8'))
            return
        elif parsed.path == '/api/settings':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            data = json.dumps(engine.config, ensure_ascii=False)
            self.wfile.write(data.encode('utf-8'))
            return
        elif parsed.path == '/api/site_logins':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            logins = engine.get_site_logins()
            self.wfile.write(json.dumps(logins, ensure_ascii=False).encode('utf-8'))
            return
        elif parsed.path == '/api/multipart_archives':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            groups = engine.get_multipart_archives()
            self.wfile.write(json.dumps(groups, ensure_ascii=False).encode('utf-8'))
            return
        elif parsed.path == '/api/schedule_matrix':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            sched = engine.get_weekly_schedule()
            self.wfile.write(json.dumps(sched, ensure_ascii=False).encode('utf-8'))
            return
        elif parsed.path == '/api/queue/export':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Disposition', 'attachment; filename="parvan_queue_backup.json"')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            backup = engine.export_queue()
            self.wfile.write(json.dumps(backup, ensure_ascii=False, indent=2).encode('utf-8'))
            return
        elif parsed.path == '/api/clipboard':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            clip = get_clipboard_url()
            self.wfile.write(json.dumps({"has_url": bool(clip), "url": clip}).encode('utf-8'))
            return
        elif parsed.path == '/api/stream':
            qs = urllib.parse.parse_qs(parsed.query)
            task_id = qs.get('task_id', [''])[0]
            if task_id in engine.tasks:
                task = engine.tasks[task_id]
                file_path = task.save_path
                if os.path.exists(file_path):
                    file_size = os.path.getsize(file_path)
                    range_header = self.headers.get('Range')
                    mime = 'video/mp4'
                    if file_path.lower().endswith('.mkv'): mime = 'video/x-matroska'
                    elif file_path.lower().endswith('.webm'): mime = 'video/webm'
                    elif file_path.lower().endswith('.mp3'): mime = 'audio/mpeg'

                    if range_header:
                        try:
                            ranges = range_header.replace('bytes=', '').split('-')
                            start = int(ranges[0])
                            end = int(ranges[1]) if len(ranges) > 1 and ranges[1] else min(start + 2*1024*1024 - 1, file_size - 1)
                            end = min(end, file_size - 1)
                            length = end - start + 1

                            self.send_response(206)
                            self.send_header('Content-Type', mime)
                            self.send_header('Content-Range', f'bytes {start}-{end}/{file_size}')
                            self.send_header('Content-Length', str(length))
                            self.send_header('Accept-Ranges', 'bytes')
                            self.send_header('Access-Control-Allow-Origin', '*')
                            self.end_headers()

                            with open(file_path, 'rb') as f:
                                f.seek(start)
                                self.wfile.write(f.read(length))
                            return
                        except Exception as e:
                            print("Streaming error:", e)

                    self.send_response(200)
                    self.send_header('Content-Type', mime)
                    self.send_header('Content-Length', str(file_size))
                    self.send_header('Accept-Ranges', 'bytes')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    with open(file_path, 'rb') as f:
                        self.wfile.write(f.read(min(file_size, 4 * 1024 * 1024)))
                    return
            self.send_response(404)
            self.end_headers()
            return
        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length).decode('utf-8') if length > 0 else '{}'
        req_data = json.loads(body) if body else {}

        res = {"success": False}
        if parsed.path == '/api/add':
            url = req_data.get('url', '')
            threads = int(req_data.get('threads', 16))
            cookies = req_data.get('cookies', None)
            headers = req_data.get('headers', None)
            if url:
                res = engine.add_download(url, num_threads=threads, cookies=cookies, headers=headers)
        elif parsed.path == '/api/batch':
            urls = req_data.get('urls', [])
            threads = int(req_data.get('threads', 16))
            if urls:
                res = {"success": True, "tasks": engine.add_batch_downloads(urls, num_threads=threads)}
        elif parsed.path == '/api/pause':
            task_id = req_data.get('task_id', '')
            res = {"success": engine.pause_download(task_id)}
        elif parsed.path == '/api/resume':
            task_id = req_data.get('task_id', '')
            res = {"success": engine.resume_download(task_id)}
        elif parsed.path == '/api/resume_all':
            for t in engine.tasks.values():
                if t.status in ("paused", "queued", "error"):
                    t.resume()
            engine.save_state()
            res = {"success": True}
        elif parsed.path == '/api/pause_all':
            for t in engine.tasks.values():
                if t.status == "downloading":
                    t.pause()
            engine.save_state()
            res = {"success": True}
        elif parsed.path == '/api/delete':
            task_id = req_data.get('task_id', '')
            remove_file = bool(req_data.get('remove_file', False))
            res = {"success": engine.delete_download(task_id, remove_file)}
        elif parsed.path == '/api/open_folder':
            task_id = req_data.get('task_id', '')
            if task_id in engine.tasks:
                path = engine.tasks[task_id].save_path
                folder = os.path.dirname(path)
                if os.path.exists(path):
                    os.system(f'explorer /select,"{path}"')
                elif os.path.exists(folder):
                    os.system(f'explorer "{folder}"')
                res = {"success": True}
        elif parsed.path == '/api/play_external':
            task_id = req_data.get('task_id', '')
            if task_id in engine.tasks:
                path = engine.tasks[task_id].save_path
                if os.path.exists(path):
                    os.system(f'start "" "{path}"')
                    res = {"success": True}
        elif parsed.path == '/api/clear_completed':
            to_del = [tid for tid, t in engine.tasks.items() if t.status == "completed"]
            for tid in to_del:
                del engine.tasks[tid]
            engine.save_state()
            res = {"success": True}
        elif parsed.path == '/api/limiter':
            limit = int(req_data.get('limit', 150))
            engine.config["speed_limit_mb"] = limit
            res = {"success": True}
        elif parsed.path == '/api/settings':
            res = engine.update_settings(req_data)
        elif parsed.path == '/api/task/refresh_url':
            task_id = req_data.get('task_id', '')
            new_url = req_data.get('new_url', '')
            hdrs = req_data.get('headers', None)
            cookies = req_data.get('cookies', None)
            success = engine.refresh_task_url(task_id, new_url, new_headers=hdrs, new_cookies=cookies)
            res = {"success": success}
        elif parsed.path == '/api/site_logins':
            domain = req_data.get('domain', '')
            cookies = req_data.get('cookies', '')
            auth = req_data.get('auth_header', '')
            custom = req_data.get('custom_headers', {})
            success = engine.set_site_login(domain, cookies=cookies, auth_header=auth, custom_headers=custom)
            res = {"success": success}
        elif parsed.path == '/api/site_logins/delete':
            domain = req_data.get('domain', '')
            success = engine.delete_site_login(domain)
            res = {"success": success}
        elif parsed.path == '/api/schedule_matrix':
            rules = req_data.get('rules', [])
            enabled = bool(req_data.get('enabled', True))
            success = engine.set_weekly_schedule(rules, enabled=enabled)
            res = {"success": success}
        elif parsed.path == '/api/queue/import':
            imported = engine.import_queue(req_data)
            res = {"success": True, "imported_count": imported}

        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(res, ensure_ascii=False).encode('utf-8'))

    def log_message(self, format, *args):
        # suppress noisy static file logs
        pass


def find_browser_executable():
    paths = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    return None

tray_icon = None
window_proc = None

def launch_window():
    global window_proc
    browser = find_browser_executable()
    app_url = "http://127.0.0.1:9876/index.html"
    user_data_dir = os.path.join(CURRENT_DIR, ".profile_data")

    if window_proc and window_proc.poll() is None:
        # already open, try to focus or reopen
        return

    if browser:
        cmd = [
            browser,
            f"--app={app_url}",
            "--window-size=1180,780",
            f"--user-data-dir={user_data_dir}",
            "--app-id=ParvanDownloadManager"
        ]
        window_proc = subprocess.Popen(cmd)
    else:
        os.system(f'start {app_url}')

def setup_tray():
    global tray_icon
    try:
        import pystray
        from PIL import Image

        icon_path = os.path.join(CURRENT_DIR, "logo.png")
        if not os.path.exists(icon_path):
            icon_path = os.path.join(os.path.dirname(CURRENT_DIR), "logo.png")
        
        image = Image.open(icon_path)

        def on_open(icon, item):
            launch_window()

        def on_resume_all(icon, item):
            for t in engine.tasks.values():
                if t.status in ("paused", "queued", "error"):
                    t.resume()
            engine.save_state()

        def on_pause_all(icon, item):
            for t in engine.tasks.values():
                if t.status == "downloading":
                    t.pause()
            engine.save_state()

        def on_open_folder(icon, item):
            downloads = engine.config.get("save_directory", os.path.join(os.path.expanduser("~"), "Downloads"))
            os.system(f'explorer "{downloads}"')

        def on_exit(icon, item):
            global window_proc
            if window_proc and window_proc.poll() is None:
                try:
                    window_proc.terminate()
                except Exception:
                    pass
            icon.stop()
            os._exit(0)

        menu = pystray.Menu(
            pystray.MenuItem("⚡ پروان دانلود منیجر (باز کردن)", on_open, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("▶️ شروع همه دانلودها", on_resume_all),
            pystray.MenuItem("⏸️ توقف همه دانلودها", on_pause_all),
            pystray.MenuItem("📂 باز کردن پوشه دانلودها", on_open_folder),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("❌ خروج کامل از برنامه", on_exit)
        )

        tray_icon = pystray.Icon("ParvanDownloadManager", image, "پروان دانلود منیجر | Parvan DL", menu)
        return tray_icon
    except Exception as e:
        print("[PARVAN TRAY] Tray initialization error:", e)
        return None

def on_task_completed_notify(task):
    global tray_icon
    print(f"[PARVAN ENGINE] Task completed: {task.filename}")
    if tray_icon:
        try:
            tray_icon.notify(
                f"دانلود با موفقیت پایان یافت:\n{task.filename} ({task.total_size_fmt})",
                "⚡ پروان دانلود منیجر"
            )
        except Exception as e:
            print("[PARVAN NOTIFY] Error:", e)

def start_server(port=9876):
    try:
        server = HTTPServer(('127.0.0.1', port), ParvanHttpHandler)
        server.serve_forever()
    except Exception:
        pass

def main():
    port = 9876
    srv_thread = threading.Thread(target=start_server, args=(port,), daemon=True)
    srv_thread.start()
    print(f"[PARVAN SERVER] Running on http://127.0.0.1:{port}")
    time.sleep(0.5)

    # Register notification hook
    engine.notification_callback = on_task_completed_notify

    # Setup System Tray Icon
    icon = setup_tray()

    # Launch initial window
    launch_window()

    if icon:
        print("[PARVAN TRAY] System Tray active in background.")
        icon.run()
    else:
        while True:
            time.sleep(1)

if __name__ == '__main__':
    main()
