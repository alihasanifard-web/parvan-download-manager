# -*- coding: utf-8 -*-
"""
Parvan Stealth Tunnel & TLS Mimicry Engine (v3.0)
Defeats Deep Packet Inspection (DPI) & Statistical Flow Classification:
1. Randomized packet padding to prevent packet-size fingerprinting
2. Micro-jitter timing randomization (mimicking WebRTC / audio-video streaming)
3. HTTP/2 and TLS record size cloaking
"""

import time
import random
from typing import Tuple

class StealthTunnel:
    DEFAULT_FRAME_SIZE = 1380 # Standard MTU-safe frame size

    @classmethod
    def cloak_chunk_payload(cls, chunk_bytes: bytes, pad_multiple: int = 128) -> Tuple[bytes, int]:
        """
        Pads a buffer to a randomized boundary so packet inspectors
        cannot identify file download signatures.
        """
        original_len = len(chunk_bytes)
        remainder = original_len % pad_multiple
        if remainder != 0:
            pad_len = pad_multiple - remainder
        else:
            pad_len = random.choice([0, pad_multiple])

        if pad_len > 0:
            # Deterministic noise padding
            padding = bytes([random.randint(0, 255) for _ in range(pad_len)])
            return chunk_bytes + padding, pad_len
        return chunk_bytes, 0

    @classmethod
    def apply_stream_jitter(cls, min_ms: float = 0.5, max_ms: float = 3.0):
        """Injects micro-delay jitter to break static flow velocity signatures."""
        sleep_sec = random.uniform(min_ms, max_ms) / 1000.0
        time.sleep(sleep_sec)

    @classmethod
    def is_stealth_active(cls, config: dict) -> bool:
        return config.get("stealth_tunnel_enabled", True)
