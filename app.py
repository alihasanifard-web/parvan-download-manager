import os
import sys
import json
import time
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

    def add_download(self, url, num_threads=16, save_dir=None):
        return engine.add_download(url, num_threads=num_threads, save_dir=save_dir)

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

    def update_settings(self, new_cfg):
        return engine.update_settings(new_cfg)

    def set_speed_limit(self, limit_mb):
        engine.set_speed_limit(limit_mb)
        return True

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
        elif parsed.path == '/api/clipboard':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            clip = get_clipboard_url()
            self.wfile.write(json.dumps({"has_url": bool(clip), "url": clip}).encode('utf-8'))
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
            if url:
                res = engine.add_download(url, num_threads=threads)
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

    browser = find_browser_executable()
    app_url = f"http://127.0.0.1:{port}/index.html"
    user_data_dir = os.path.join(CURRENT_DIR, ".profile_data")

    if browser:
        print(f"[PARVAN DESKTOP] Launching Window with: {browser}")
        import subprocess
        cmd = [
            browser,
            f"--app={app_url}",
            "--window-size=1180,780",
            f"--user-data-dir={user_data_dir}",
            "--app-id=ParvanDownloadManager"
        ]
        proc = subprocess.Popen(cmd)
        proc.wait()
    else:
        os.system(f'start {app_url}')
        while True:
            time.sleep(1)

if __name__ == '__main__':
    main()
