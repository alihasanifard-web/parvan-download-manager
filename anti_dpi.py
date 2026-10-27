# -*- coding: utf-8 -*-
"""
Parvan Anti-DPI & Clean DNS Resilience Engine (v3.0)
Integrated from Parvan Emergency Gate resilience concepts:
1. TCP ClientHello SNI Packet Fragmentation (Anti-DPI)
2. DoH (DNS-over-HTTPS) with Cloudflare/Quad9 clean IPs
3. Custom socket factory for urllib/http.client
"""

import ssl
import socket
import struct
import urllib.request
import urllib.parse
from typing import Tuple, Optional

# Public Clean DNS-over-HTTPS Endpoints & Clean IPs
CLEAN_DOH_SERVERS = [
    ("1.1.1.1", "cloudflare-dns.com", "/dns-query"),
    ("8.8.8.8", "dns.google", "/resolve"),
    ("9.9.9.9", "dns.quad9.net", "/dns-query"),
]

class CleanDNSResolver:
    """Resolves domains via direct socket DoH or direct clean IP query."""
    _cache = {}

    @classmethod
    def resolve(cls, host: str, timeout: float = 3.0) -> str:
        # Check if already IP
        try:
            socket.inet_aton(host)
            return host
        except socket.error:
            pass

        if host in cls._cache:
            return cls._cache[host]

        # Standard resolution fallback first
        try:
            ip = socket.gethostbyname(host)
            cls._cache[host] = ip
            return ip
        except Exception:
            pass

        # DoH Fallback using raw IP connection to 1.1.1.1 or 8.8.8.8
        for doh_ip, doh_sni, doh_path in CLEAN_DOH_SERVERS:
            try:
                url = f"https://{doh_ip}{doh_path}?name={host}&type=A"
                req = urllib.request.Request(
                    url,
                    headers={
                        "Host": doh_sni,
                        "Accept": "application/dns-json",
                        "User-Agent": "ParvanAntiDPI/3.0"
                    }
                )
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
                    import json
                    data = json.loads(resp.read().decode('utf-8'))
                    if "Answer" in data:
                        for ans in data["Answer"]:
                            if ans.get("type") == 1: # A record
                                resolved_ip = ans.get("data")
                                if resolved_ip:
                                    cls._cache[host] = resolved_ip
                                    return resolved_ip
            except Exception:
                continue

        return host


class AntiDPISocket(socket.socket):
    """
    Socket wrapper that fragments the TLS ClientHello handshake packet.
    DPI middleboxes inspect the TLS SNI (Server Name Indication) in the first TCP packet.
    By splitting the ClientHello across 2 TCP segments, the SNI is fragmented
    and cannot be matched by DPI signature filters.
    """
    def __init__(self, *args, fragment_size: int = 40, **kwargs):
        super().__init__(*args, **kwargs)
        self.fragment_size = fragment_size
        self._handshake_done = False

    def send(self, data, flags: int = 0) -> int:
        b_data = bytes(data) if not isinstance(data, (bytes, bytearray)) else data
        # If this is the initial TLS ClientHello (starts with 0x16 0x03)
        if not self._handshake_done and len(b_data) > 100 and b_data[0] == 0x16 and b_data[1] == 0x03:
            self._handshake_done = True
            try:
                # Fragment 1
                part1 = b_data[:self.fragment_size]
                part2 = b_data[self.fragment_size:]
                sent1 = super().send(part1, flags)
                import time
                time.sleep(0.01)
                sent2 = super().send(part2, flags)
                return sent1 + sent2
            except Exception:
                return super().send(data, flags)
        return super().send(data, flags)


def create_antidpi_connection(address: Tuple[str, int], timeout: float = 10.0, fragment_size: int = 40) -> socket.socket:
    host, port = address
    resolved_ip = CleanDNSResolver.resolve(host, timeout=timeout)
    
    sock = AntiDPISocket(socket.AF_INET, socket.SOCK_STREAM, fragment_size=fragment_size)
    sock.settimeout(timeout)
    sock.connect((resolved_ip, port))
    return sock
