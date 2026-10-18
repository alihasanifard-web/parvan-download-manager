import os
import sys
import time
import math
import threading
import urllib.request
from concurrent.futures import ThreadPoolExecutor

class ChunkDownloadWorker:
    def __init__(self, task_id, chunk_id, url, start_byte, end_byte, file_path, lock, proxy=None):
        self.task_id = task_id
        self.chunk_id = chunk_id
        self.url = url
        self.start_byte = start_byte
        self.end_byte = end_byte
        self.total_bytes = end_byte - start_byte + 1
        self.downloaded = 0
        self.file_path = file_path
        self.lock = lock
        self.proxy = proxy
        self.is_paused = False
        self.is_cancelled = False
        self.status = "waiting" # waiting, downloading, done, error

    def run(self):
        self.status = "downloading"
        req = urllib.request.Request(self.url)
        req.add_header('User-Agent', 'ParvanDownloadManager/2.5')
        req.add_header('Range', f'bytes={self.start_byte + self.downloaded}-{self.end_byte}')

        opener = urllib.request.build_opener()
        if self.proxy:
            proxy_handler = urllib.request.ProxyHandler({'http': self.proxy, 'https': self.proxy})
            opener = urllib.request.build_opener(proxy_handler)

        try:
            with opener.open(req, timeout=15) as resp:
                with open(self.file_path, 'r+b') as f:
                    f.seek(self.start_byte + self.downloaded)
                    buf_size = 64 * 1024 # 64 KB
                    while not self.is_paused and not self.is_cancelled:
                        data = resp.read(buf_size)
                        if not data:
                            break
                        f.write(data)
                        self.downloaded += len(data)
            
            if self.downloaded >= self.total_bytes:
                self.status = "done"
            elif self.is_paused:
                self.status = "paused"
        except Exception as e:
            self.status = "error"
            print(f"[Chunk {self.chunk_id}] Error: {e}")

print("ChunkDownloadWorker defined successfully")
