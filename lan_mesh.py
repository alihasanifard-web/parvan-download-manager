# -*- coding: utf-8 -*-
"""
Parvan LAN Mesh P2P Sharing Engine (v3.0)
1. Automatic neighbor discovery on local Wi-Fi/Ethernet via UDP Broadcast (port 9878)
2. Task chunk index sharing across local network peers
3. Gigabit-speed local peer transfer without consuming internet data
"""

import time
import json
import socket
import hashlib
import threading
from typing import Dict, Any, List, Optional, Set

MESH_BROADCAST_PORT = 9878
MESH_MAGIC = "PARVAN_MESH_V1"

class LanMeshNode:
    def __init__(self, node_id: Optional[str] = None, http_port: int = 9876):
        self.node_id = node_id or f"node_{int(time.time()*1000)}"
        self.http_port = http_port
        self.peers: Dict[str, Dict[str, Any]] = {}
        self.local_task_hashes: Dict[str, str] = {} # url_hash -> task_id
        self.is_running = False
        self._sock: Optional[socket.socket] = None
        self._lock = threading.Lock()

    def register_task(self, url: str, task_id: str):
        url_hash = hashlib.sha256(url.encode('utf-8')).hexdigest()[:16]
        with self._lock:
            self.local_task_hashes[url_hash] = task_id

    def unregister_task(self, url: str):
        url_hash = hashlib.sha256(url.encode('utf-8')).hexdigest()[:16]
        with self._lock:
            self.local_task_hashes.pop(url_hash, None)

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self._sock.bind(('', MESH_BROADCAST_PORT))
            self._sock.settimeout(1.0)
        except Exception as e:
            # Port might be in use or unavailable
            self._sock = None
            return

        threading.Thread(target=self._listen_loop, daemon=True).start()
        threading.Thread(target=self._beacon_loop, daemon=True).start()

    def stop(self):
        self.is_running = False
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None

    def _beacon_loop(self):
        while self.is_running:
            try:
                with self._lock:
                    hashes = list(self.local_task_hashes.keys())
                msg = {
                    "magic": MESH_MAGIC,
                    "type": "beacon",
                    "node_id": self.node_id,
                    "port": self.http_port,
                    "hashes": hashes
                }
                data = json.dumps(msg).encode('utf-8')
                if self._sock:
                    self._sock.sendto(data, ('<broadcast>', MESH_BROADCAST_PORT))
            except Exception:
                pass
            time.sleep(5)

    def _listen_loop(self):
        while self.is_running and self._sock:
            try:
                data, addr = self._sock.recvfrom(4096)
                msg = json.loads(data.decode('utf-8'))
                if msg.get("magic") != MESH_MAGIC or msg.get("node_id") == self.node_id:
                    continue

                peer_id = msg["node_id"]
                ip = addr[0]
                port = msg.get("port", 9876)
                hashes = msg.get("hashes", [])

                with self._lock:
                    self.peers[peer_id] = {
                        "ip": ip,
                        "port": port,
                        "hashes": set(hashes),
                        "last_seen": time.time()
                    }
            except socket.timeout:
                continue
            except Exception:
                pass

    def find_peer_for_url(self, url: str) -> Optional[Dict[str, Any]]:
        """Returns peer info if another local computer has this URL cached."""
        url_hash = hashlib.sha256(url.encode('utf-8')).hexdigest()[:16]
        now = time.time()
        with self._lock:
            for peer_id, info in self.peers.items():
                if now - info["last_seen"] < 15 and url_hash in info["hashes"]:
                    return {
                        "peer_id": peer_id,
                        "ip": info["ip"],
                        "port": info["port"],
                        "peer_url": f"http://{info['ip']}:{info['port']}/api/stream?url_hash={url_hash}"
                    }
        return None
