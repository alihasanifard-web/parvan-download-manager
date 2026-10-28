# -*- coding: utf-8 -*-
"""
Parvan Site Grabber & Web Crawler Engine (v3.0)
1. Crawls web pages to a configurable depth (1 or 2)
2. Filters links by file category (media, archives, documents, software, all)
3. Resolves absolute URLs and eliminates duplicate anchors
4. Performs asynchronous lightweight HEAD requests to detect file size & mime type
"""

import os
import re
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any, Set, Optional

# Supported Extension Groups
CATEGORY_EXTENSIONS = {
    "media": [".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".mp3", ".flac", ".wav", ".aac", ".ogg", ".m4a", ".m3u8"],
    "archive": [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso", ".img", ".bin"],
    "software": [".exe", ".msi", ".apk", ".dmg", ".pkg", ".deb", ".rpm", ".appimage"],
    "document": [".pdf", ".epub", ".docx", ".xlsx", ".pptx", ".doc", ".xls", ".ppt", ".txt"],
    "image": [".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".bmp"]
}

class SiteGrabber:
    HREF_PATTERN = re.compile(r'''href=["']([^"']+)["']''', re.IGNORECASE)
    SRC_PATTERN = re.compile(r'''src=["']([^"']+)["']''', re.IGNORECASE)

    @classmethod
    def crawl_page(cls, page_url: str, category: str = "all", max_depth: int = 1, proxy: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Crawls a page and returns candidate downloadable links matching the category filter.
        """
        discovered_urls: Set[str] = set()
        visited_pages: Set[str] = set()
        to_visit = [(page_url, 0)]

        valid_exts = set()
        if category in CATEGORY_EXTENSIONS:
            valid_exts = set(CATEGORY_EXTENSIONS[category])
        elif category == "all":
            for ext_list in CATEGORY_EXTENSIONS.values():
                valid_exts.update(ext_list)

        while to_visit:
            cur_url, depth = to_visit.pop(0)
            if cur_url in visited_pages or depth > max_depth:
                continue
            visited_pages.add(cur_url)

            html_text = cls._fetch_html(cur_url, proxy=proxy)
            if not html_text:
                continue

            links = cls._extract_links(html_text, cur_url)
            for link in links:
                # Check if this link matches our target downloadable extensions
                path_lower = urllib.parse.urlparse(link).path.lower()
                has_target_ext = any(path_lower.endswith(ext) for ext in valid_exts)

                if has_target_ext:
                    discovered_urls.add(link)
                elif depth < max_depth:
                    # Enqueue subpage for further crawling if same domain
                    parsed_cur = urllib.parse.urlparse(cur_url)
                    parsed_link = urllib.parse.urlparse(link)
                    if parsed_link.netloc == parsed_cur.netloc and not any(path_lower.endswith(e) for e in [".jpg", ".png", ".css", ".js"]):
                        to_visit.append((link, depth + 1))

        # Probe candidate URLs for file size & name
        return cls._probe_candidates(list(discovered_urls), proxy=proxy)

    @classmethod
    def _fetch_html(cls, url: str, proxy: Optional[str] = None) -> str:
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ParvanSiteGrabber/3.0",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            })
            if "127.0.0.1" in url or "localhost" in url:
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            elif proxy:
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({'http': proxy, 'https': proxy}))
            else:
                opener = urllib.request.build_opener()

            with opener.open(req, timeout=8) as resp:
                content_type = resp.headers.get("Content-Type", "")
                if "text/html" in content_type or "application/xhtml" in content_type or not content_type:
                    return resp.read().decode('utf-8', errors='replace')
        except Exception:
            pass
        return ""

    @classmethod
    def _extract_links(cls, html: str, base_url: str) -> List[str]:
        found = []
        for match in cls.HREF_PATTERN.findall(html) + cls.SRC_PATTERN.findall(html):
            cleaned = match.strip()
            if cleaned and not cleaned.startswith(("#", "javascript:", "mailto:", "tel:")):
                abs_url = urllib.parse.urljoin(base_url, cleaned)
                found.append(abs_url)
        return found

    @classmethod
    def _probe_candidates(cls, urls: List[str], proxy: Optional[str] = None) -> List[Dict[str, Any]]:
        results = []

        def probe_single(u: str) -> Dict[str, Any]:
            filename = os.path.basename(urllib.parse.urlparse(u).path) or "download.bin"
            item = {
                "url": u,
                "filename": urllib.parse.unquote(filename),
                "size_bytes": 0,
                "size_fmt": "نامشخص",
                "content_type": "application/octet-stream"
            }
            try:
                req = urllib.request.Request(u, method="HEAD", headers={"User-Agent": "ParvanSiteGrabber/3.0"})
                if "127.0.0.1" in u or "localhost" in u:
                    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                elif proxy:
                    opener = urllib.request.build_opener(urllib.request.ProxyHandler({'http': proxy, 'https': proxy}))
                else:
                    opener = urllib.request.build_opener()

                with opener.open(req, timeout=5) as resp:
                    cl = resp.headers.get("Content-Length")
                    if cl and cl.isdigit():
                        size = int(cl)
                        item["size_bytes"] = size
                        item["size_fmt"] = cls._format_bytes(size)
                    ct = resp.headers.get("Content-Type")
                    if ct:
                        item["content_type"] = ct.split(";")[0].strip()
                    cd = resp.headers.get("Content-Disposition")
                    if cd and "filename=" in cd:
                        fpart = cd.split("filename=")[-1].strip(' "\'')
                        if fpart:
                            item["filename"] = urllib.parse.unquote(fpart)
            except Exception:
                pass
            return item

        with ThreadPoolExecutor(max_workers=8) as ex:
            results = list(ex.map(probe_single, urls))

        return sorted(results, key=lambda x: -x["size_bytes"])

    @staticmethod
    def _format_bytes(num: float) -> str:
        val = float(num)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if abs(val) < 1024.0:
                return f"{val:3.1f} {unit}"
            val /= 1024.0
        return f"{val:.1f} TB"
