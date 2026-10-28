# -*- coding: utf-8 -*-
"""
Parvan Remote ZIP Preview Engine (v3.0)
Inspects remote ZIP files without full download using HTTP Range requests:
1. Requests last 64 KB of remote file
2. Locates End of Central Directory (EOCD) record (0x06054b50)
3. Traverses Central Directory headers (0x02014b50)
4. Returns file list, folder structure, compressed & uncompressed sizes
"""

import struct
import urllib.parse
import urllib.request
from typing import List, Dict, Any, Optional

EOCD_SIGNATURE = b'PK\x05\x06'
CD_HEADER_SIGNATURE = b'PK\x01\x02'

class RemoteZipInspector:
    @classmethod
    def inspect_remote_zip(cls, zip_url: str, proxy: Optional[str] = None) -> Dict[str, Any]:
        """
        Inspects remote ZIP archive and returns file listings and metadata.
        """
        # 1. Probe total size via HEAD
        total_size = cls._probe_file_size(zip_url, proxy=proxy)
        if total_size <= 0:
            return {"success": False, "error": "Remote server does not report Content-Length or file is empty."}

        # 2. Fetch the tail (last 64KB or full file if smaller)
        fetch_len = min(65536, total_size)
        start_byte = total_size - fetch_len
        tail_data = cls._fetch_range(zip_url, start_byte, total_size - 1, proxy=proxy)
        if not tail_data:
            return {"success": False, "error": "Failed to fetch file tail via HTTP Range request."}

        # 3. Locate EOCD signature from end of tail
        eocd_pos = tail_data.rfind(EOCD_SIGNATURE)
        if eocd_pos == -1:
            return {"success": False, "error": "Valid ZIP End of Central Directory record not found in file tail."}

        eocd_bytes = tail_data[eocd_pos:]
        if len(eocd_bytes) < 22:
            return {"success": False, "error": "Truncated ZIP EOCD header."}

        total_entries = struct.unpack_from("<H", eocd_bytes, 10)[0]
        cd_size = struct.unpack_from("<I", eocd_bytes, 12)[0]
        cd_offset = struct.unpack_from("<I", eocd_bytes, 16)[0]

        # 4. Check if CD is inside tail_data or needs an extra Range request
        cd_bytes = b""
        if cd_offset >= start_byte and (cd_offset + cd_size) <= total_size:
            offset_in_tail = cd_offset - start_byte
            cd_bytes = tail_data[offset_in_tail:offset_in_tail + cd_size]
        else:
            # Need targeted Range request for Central Directory
            cd_bytes = cls._fetch_range(zip_url, cd_offset, cd_offset + cd_size - 1, proxy=proxy)

        if not cd_bytes or len(cd_bytes) < 46:
            return {"success": False, "error": "Could not read ZIP Central Directory."}

        # 5. Parse Central Directory entries
        files = []
        pos = 0
        while pos + 46 <= len(cd_bytes):
            if cd_bytes[pos:pos+4] != CD_HEADER_SIGNATURE:
                break

            comp_method = struct.unpack_from("<H", cd_bytes, pos + 10)[0]
            crc32 = struct.unpack_from("<I", cd_bytes, pos + 16)[0]
            comp_size = struct.unpack_from("<I", cd_bytes, pos + 20)[0]
            uncomp_size = struct.unpack_from("<I", cd_bytes, pos + 24)[0]
            fname_len = struct.unpack_from("<H", cd_bytes, pos + 28)[0]
            extra_len = struct.unpack_from("<H", cd_bytes, pos + 30)[0]
            comm_len = struct.unpack_from("<H", cd_bytes, pos + 32)[0]

            fname_start = pos + 46
            fname_end = fname_start + fname_len
            raw_name = cd_bytes[fname_start:fname_end]
            try:
                filename = raw_name.decode("utf-8")
            except UnicodeDecodeError:
                filename = raw_name.decode("cp437", errors="replace")

            is_dir = filename.endswith("/") or (comp_size == 0 and uncomp_size == 0 and not filename.strip())
            files.append({
                "path": filename,
                "is_directory": is_dir,
                "compressed_size": comp_size,
                "uncompressed_size": uncomp_size,
                "compressed_fmt": cls._format_bytes(comp_size),
                "uncompressed_fmt": cls._format_bytes(uncomp_size),
                "crc32": f"{crc32:08x}",
                "method": "Deflate" if comp_method == 8 else ("Stored" if comp_method == 0 else str(comp_method))
            })

            pos = fname_end + extra_len + comm_len

        total_uncompressed = sum(f["uncompressed_size"] for f in files)
        return {
            "success": True,
            "archive_size_bytes": total_size,
            "archive_size_fmt": cls._format_bytes(total_size),
            "total_files": len(files),
            "total_uncompressed_bytes": total_uncompressed,
            "total_uncompressed_fmt": cls._format_bytes(total_uncompressed),
            "files": files
        }

    @classmethod
    def _probe_file_size(cls, url: str, proxy: Optional[str] = None) -> int:
        try:
            req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "ParvanZipInspector/3.0"})
            if "127.0.0.1" in url or "localhost" in url:
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            elif proxy:
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({'http': proxy, 'https': proxy}))
            else:
                opener = urllib.request.build_opener()

            with opener.open(req, timeout=8) as resp:
                cl = resp.headers.get("Content-Length")
                if cl and cl.isdigit():
                    return int(cl)
        except Exception:
            pass
        return 0

    @classmethod
    def _fetch_range(cls, url: str, start: int, end: int, proxy: Optional[str] = None) -> bytes:
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "ParvanZipInspector/3.0",
                "Range": f"bytes={start}-{end}"
            })
            if "127.0.0.1" in url or "localhost" in url:
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            elif proxy:
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({'http': proxy, 'https': proxy}))
            else:
                opener = urllib.request.build_opener()

            with opener.open(req, timeout=10) as resp:
                return resp.read()
        except Exception:
            pass
        return b""

    @staticmethod
    def _format_bytes(num: float) -> str:
        val = float(num)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if abs(val) < 1024.0:
                return f"{val:3.1f} {unit}"
            val /= 1024.0
        return f"{val:.1f} TB"
