# -*- coding: utf-8 -*-
"""
Parvan Batch Media Playlist Downloader (v3.0)
Extracts items from YouTube / SoundCloud / Media playlists using yt-dlp flat-playlist extraction
and populates the Parvan queue with sequenced order numbering.
"""

import json
import subprocess
from typing import List, Dict, Any, Optional

class PlaylistExtractor:
    @classmethod
    def is_playlist_url(cls, url: str) -> bool:
        u = url.lower()
        return "list=" in u or "/playlist" in u or "/sets/" in u or "/album/" in u

    @classmethod
    def extract_playlist_entries(cls, playlist_url: str, max_items: int = 50) -> List[Dict[str, Any]]:
        """Extracts individual video/audio entries from a playlist without downloading media files."""
        cmd = [
            "yt-dlp",
            "--flat-playlist",
            "--dump-single-json",
            "--playlist-end", str(max_items),
            "--no-warnings",
            playlist_url
        ]

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if res.returncode == 0 and res.stdout.strip():
                data = json.loads(res.stdout)
                entries = data.get("entries", [])
                results = []
                for idx, entry in enumerate(entries, start=1):
                    entry_url = entry.get("url") or entry.get("webpage_url")
                    if not entry_url and entry.get("id"):
                        entry_url = f"https://www.youtube.com/watch?v={entry['id']}"
                    
                    if entry_url:
                        results.append({
                            "index": idx,
                            "title": entry.get("title", f"Track {idx:02d}"),
                            "url": entry_url,
                            "duration": entry.get("duration", 0)
                        })
                return results
        except Exception as e:
            print(f"[PlaylistExtractor] Warning: {e}")

        return []
