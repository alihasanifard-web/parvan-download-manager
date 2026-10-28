# -*- coding: utf-8 -*-
"""
Parvan Download Manager - Enterprise Extensions v3.0
1. SiteLoginsManager: VIP Credential & Domain Cookie Vault
2. MultipartArchiveDetective: Detection of split archives (.part1.rar, .r01, etc.)
3. WeeklySpeedScheduler: 7x24 Bandwidth & Time matrix scheduler
4. QueueBackupManager: Export & Import of download queues
"""

import os
import re
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

# --- 1. Site Logins & VIP Credentials Manager ---
class SiteLoginsManager:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.logins: Dict[str, Dict[str, Any]] = {}
        self.load()

    def load(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.logins = data.get("site_logins", {})
            except Exception:
                self.logins = {}

    def save(self):
        data = {}
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}
        data["site_logins"] = self.logins
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[SiteLoginsManager] Save error: {e}")

    def set_login(self, domain: str, cookies: str = "", auth_header: str = "", custom_headers: Optional[Dict[str, str]] = None):
        domain = domain.lower().strip()
        if domain.startswith("http://") or domain.startswith("https://"):
            domain = urllib.parse.urlparse(domain).netloc
        if domain.startswith("www."):
            domain = domain[4:]
        
        self.logins[domain] = {
            "domain": domain,
            "cookies": cookies.strip(),
            "auth_header": auth_header.strip(),
            "custom_headers": custom_headers or {},
            "updated_at": time.time()
        }
        self.save()

    def remove_login(self, domain: str) -> bool:
        domain = domain.lower().strip()
        if domain in self.logins:
            del self.logins[domain]
            self.save()
            return True
        return False

    def match_credentials(self, url: str) -> Dict[str, Any]:
        """Matches a URL against saved domains, returning headers and cookies."""
        try:
            netloc = urllib.parse.urlparse(url).netloc.lower()
            if netloc.startswith("www."):
                netloc = netloc[4:]
            
            # 1. Exact match
            if netloc in self.logins:
                return self.logins[netloc]

            # 2. Subdomain / parent domain match
            for saved_domain, creds in self.logins.items():
                if netloc.endswith("." + saved_domain) or saved_domain.endswith("." + netloc):
                    return creds
        except Exception:
            pass
        return {}


# --- 2. Multi-Part Archive Detective ---
class MultipartArchiveDetective:
    # Patterns for:
    # 1. name.part01.rar / name.part1.rar
    # 2. name.r00, name.r01
    # 3. name.7z.001
    # 4. name.z01, name.zip
    PATTERN_PART = re.compile(r'^(?P<base>.+?)[._-]?(?:part|pt)(?P<part>\d+)\.(?P<ext>rar|zip|7z)$', re.IGNORECASE)
    PATTERN_R_EXT = re.compile(r'^(?P<base>.+?)\.r(?P<part>\d+)$', re.IGNORECASE)
    PATTERN_7Z_EXT = re.compile(r'^(?P<base>.+?)\.7z\.(?P<part>\d+)$', re.IGNORECASE)
    PATTERN_Z_EXT = re.compile(r'^(?P<base>.+?)\.z(?P<part>\d+)$', re.IGNORECASE)

    @classmethod
    def parse_filename(cls, filename: str) -> Optional[Dict[str, Any]]:
        filename = os.path.basename(filename)
        
        # Check partX.rar
        m = cls.PATTERN_PART.match(filename)
        if m:
            return {
                "base_name": m.group("base"),
                "part_number": int(m.group("part")),
                "ext": m.group("ext").lower(),
                "style": "part_num"
            }

        # Check .r01
        m = cls.PATTERN_R_EXT.match(filename)
        if m:
            return {
                "base_name": m.group("base"),
                "part_number": int(m.group("part")) + 1,
                "ext": "rar",
                "style": "r_ext"
            }

        # Check .7z.001
        m = cls.PATTERN_7Z_EXT.match(filename)
        if m:
            return {
                "base_name": m.group("base"),
                "part_number": int(m.group("part")),
                "ext": "7z",
                "style": "7z_ext"
            }

        # Check .z01
        m = cls.PATTERN_Z_EXT.match(filename)
        if m:
            return {
                "base_name": m.group("base"),
                "part_number": int(m.group("part")),
                "ext": "zip",
                "style": "z_ext"
            }

        return None

    @classmethod
    def analyze_tasks(cls, tasks: List[Any]) -> Dict[str, Dict[str, Any]]:
        """
        Groups tasks into multipart archive sets, detects missing parts,
        and computes completion readiness.
        """
        groups: Dict[str, Dict[str, Any]] = {}

        for t in tasks:
            info = cls.parse_filename(t.filename)
            if not info:
                continue

            base = info["base_name"]
            part_num = info["part_number"]

            if base not in groups:
                groups[base] = {
                    "base_name": base,
                    "ext": info["ext"],
                    "parts": {},
                    "tasks": [],
                    "total_detected_parts": 0,
                    "missing_parts": [],
                    "all_completed": False
                }

            groups[base]["parts"][part_num] = {
                "task_id": t.id,
                "filename": t.filename,
                "status": t.status,
                "progress": getattr(t, "downloaded_bytes", 0) / max(1, getattr(t, "total_size", 1)),
                "is_completed": t.status == "completed"
            }
            groups[base]["tasks"].append(t.id)

        # Compute gaps and readiness
        for base, grp in groups.items():
            part_nums = sorted(grp["parts"].keys())
            if part_nums:
                max_part = max(part_nums)
                grp["total_detected_parts"] = max_part
                # Find any missing part number between 1 and max_part
                missing = [p for p in range(1, max_part + 1) if p not in grp["parts"]]
                grp["missing_parts"] = missing
                grp["is_complete_set"] = len(missing) == 0
                grp["all_completed"] = (len(missing) == 0) and all(p["is_completed"] for p in grp["parts"].values())
            else:
                grp["is_complete_set"] = False
                grp["all_completed"] = False

        return groups


# --- 3. Weekly Speed Schedule Matrix ---
class WeeklySpeedScheduler:
    """
    Manages 7x24 bandwidth calendar schedule:
    - days: 0 (Monday) to 6 (Sunday), or 0 to 6 representing Sat-Fri in Persian
    - time ranges: start_hour to end_hour
    - target speed limit (0 = Unlimited, >0 = Limit in MB/s, -1 = Pause)
    """
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.rules: List[Dict[str, Any]] = []
        self.enabled: bool = True
        self.load()

    def load(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    sched = data.get("weekly_scheduler", {})
                    self.rules = sched.get("rules", self.default_rules())
                    self.enabled = sched.get("enabled", True)
            except Exception:
                self.rules = self.default_rules()
        else:
            self.rules = self.default_rules()

    def default_rules(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "night_unlimited",
                "name": "دانلود شبانه رایگان (Night Free Speed)",
                "days": [0, 1, 2, 3, 4, 5, 6],
                "start_hour": 2,
                "end_hour": 7,
                "speed_limit_mb": 0 # Unlimited
            },
            {
                "id": "day_work",
                "name": "مصرف بهینه روزانه (Work Hours Cap)",
                "days": [0, 1, 2, 3, 4, 5, 6],
                "start_hour": 8,
                "end_hour": 23,
                "speed_limit_mb": 5 # 5 MB/s so browsing/ping stays smooth
            }
        ]

    def save(self):
        data = {}
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}
        data["weekly_scheduler"] = {
            "enabled": self.enabled,
            "rules": self.rules
        }
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[WeeklySpeedScheduler] Save error: {e}")

    def get_current_limit(self, now: Optional[datetime] = None) -> Optional[int]:
        """Evaluates active rules for current timestamp and returns matching speed limit."""
        if not self.enabled:
            return None

        now = now or datetime.now()
        cur_day = now.weekday() # 0 to 6
        cur_hour = now.hour # 0 to 23

        for rule in self.rules:
            if cur_day in rule.get("days", []):
                start = rule.get("start_hour", 0)
                end = rule.get("end_hour", 24)
                if start <= cur_hour < end:
                    return int(rule.get("speed_limit_mb", 0))
        return None


# --- 4. Queue Export & Import Manager ---
class QueueBackupManager:
    @staticmethod
    def export_queue(tasks: Dict[str, Any]) -> Dict[str, Any]:
        """Serializes download tasks into a portable backup dictionary."""
        backup = {
            "version": "3.0.0",
            "app": "Parvan Download Manager",
            "exported_at": time.time(),
            "exported_date": datetime.now().isoformat(),
            "total_tasks": len(tasks),
            "tasks": []
        }

        for task in tasks.values():
            item = {
                "id": task.id,
                "url": task.url,
                "filename": task.filename,
                "category": getattr(task, "category", "app"),
                "priority": getattr(task, "priority", 1),
                "num_threads": getattr(task, "num_threads", 16),
                "save_dir": getattr(task, "save_dir", ""),
                "status": getattr(task, "status", "queued"),
                "total_size": getattr(task, "total_size", 0),
                "cookies": getattr(task, "cookies", None),
                "headers": getattr(task, "headers", {})
            }
            backup["tasks"].append(item)

        return backup

    @staticmethod
    def import_queue(engine_inst: Any, data: Dict[str, Any]) -> int:
        """Restores tasks from backup into the engine queue."""
        imported_count = 0
        tasks_data = data.get("tasks", [])

        for item in tasks_data:
            url = item.get("url", "").strip()
            if not url:
                continue

            # Skip if task id already exists in engine or active downloading
            if item.get("id") in engine_inst.tasks:
                continue

            threads = int(item.get("num_threads", 16))
            save_dir = item.get("save_dir", None)
            cookies = item.get("cookies", None)
            headers = item.get("headers", None)

            res = engine_inst.add_download(
                url=url,
                num_threads=threads,
                save_dir=save_dir,
                cookies=cookies,
                headers=headers
            )
            if res and isinstance(res, dict) and "id" in res:
                task_id = res["id"]
                if task_id in engine_inst.tasks:
                    if "priority" in item:
                        engine_inst.tasks[task_id].priority = int(item["priority"])
                    if "filename" in item and item["filename"]:
                        engine_inst.tasks[task_id].filename = item["filename"]
                        engine_inst.tasks[task_id].save_path = os.path.join(
                            engine_inst.tasks[task_id].save_dir,
                            item["filename"]
                        )
                imported_count += 1

        engine_inst.save_state()
        return imported_count


# --- 5. Private Vault / Secret Downloads Manager ---
class PrivateVaultManager:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.pin_hash: str = "" # SHA-256
        self.is_unlocked: bool = False
        self.load()

    def load(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    vault = data.get("private_vault", {})
                    self.pin_hash = vault.get("pin_hash", "")
            except Exception:
                self.pin_hash = ""

    def save(self):
        data = {}
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}
        data["private_vault"] = {
            "pin_hash": self.pin_hash,
            "has_pin": bool(self.pin_hash)
        }
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def set_pin(self, new_pin: str, old_pin: str = "") -> bool:
        new_pin = str(new_pin).strip()
        if self.pin_hash:
            import hashlib
            if hashlib.sha256(old_pin.encode("utf-8")).hexdigest() != self.pin_hash:
                return False
        import hashlib
        self.pin_hash = hashlib.sha256(new_pin.encode("utf-8")).hexdigest() if new_pin else ""
        self.save()
        return True

    def unlock(self, pin: str) -> bool:
        if not self.pin_hash:
            self.is_unlocked = True
            return True
        import hashlib
        h = hashlib.sha256(str(pin).strip().encode("utf-8")).hexdigest()
        if h == self.pin_hash:
            self.is_unlocked = True
            return True
        return False

    def lock(self):
        self.is_unlocked = False

    def filter_visible_tasks(self, tasks: List[Any]) -> List[Any]:
        if self.is_unlocked:
            return tasks
        return [t for t in tasks if not getattr(t, "is_vault", False)]


# --- 6. Multi-Platform Webhook Notifier ---
class MultiPlatformWebhook:
    @classmethod
    def send_completion(cls, webhook_url: str, task: Any, webhook_type: str = "generic") -> bool:
        if not webhook_url:
            return False

        filename = getattr(task, "filename", "download.bin")
        size_fmt = getattr(task, "total_size_fmt", "نامشخص")
        sha256 = getattr(task, "sha256_hash", "") or "محاسبه نشد"

        try:
            payload: Dict[str, Any] = {}
            if webhook_type == "discord":
                payload = {
                    "username": "Parvan Download Manager",
                    "avatar_url": "https://raw.githubusercontent.com/alihasanifard-web/parvan-download-manager/main/logo.png",
                    "embeds": [{
                        "title": "⚡ دانلود تکمیل شد | Parvan DL",
                        "description": f"فایل **{filename}** با موفقیت دانلود شد.",
                        "color": 62965, # Cyan
                        "fields": [
                            {"name": "حجم فایل", "value": size_fmt, "inline": True},
                            {"name": "چک‌سام SHA-256", "value": f"`{sha256[:16]}...`", "inline": True}
                        ],
                        "footer": {"text": "پروان دانلود منیجر ۳.۰ • نسل جدید دانلود چندکاناله"}
                    }]
                }
            elif webhook_type == "slack":
                payload = {
                    "text": f"⚡ *دانلود با موفقیت پایان یافت:*\n*{filename}* ({size_fmt})\nSHA256: `{sha256[:16]}...`"
                }
            else:
                # Generic JSON
                payload = {
                    "event": "task_completed",
                    "app": "Parvan Download Manager",
                    "filename": filename,
                    "total_size": getattr(task, "total_size", 0),
                    "total_size_fmt": size_fmt,
                    "sha256_hash": sha256,
                    "timestamp": time.time()
                }

            data_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                webhook_url,
                data=data_bytes,
                headers={"Content-Type": "application/json", "User-Agent": "ParvanWebhook/3.0"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status in (200, 204)
        except Exception as e:
            print(f"[MultiPlatformWebhook] Send error: {e}")
            return False

