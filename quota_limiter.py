# -*- coding: utf-8 -*-
"""
Parvan Data Usage & Quota Limiter Engine (v3.0)
1. Tracks cumulative downloaded bytes by Date (Daily, Monthly)
2. Enforces daily / monthly data cap quotas
3. Auto-throttles or halts active downloads upon reaching quota
"""

import os
import json
import time
from datetime import datetime
from typing import Dict, Any, Optional

class QuotaLimiter:
    def __init__(self, data_file: str):
        self.data_file = data_file
        self.daily_limit_bytes = 0 # 0 = Unlimited
        self.monthly_limit_bytes = 0
        self.action_on_limit = "throttle" # "throttle" or "pause"
        self.throttle_speed_kb = 50
        self.history: Dict[str, int] = {} # "YYYY-MM-DD" -> bytes
        self.load()

    def load(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.daily_limit_bytes = data.get("daily_limit_bytes", 0)
                    self.monthly_limit_bytes = data.get("monthly_limit_bytes", 0)
                    self.action_on_limit = data.get("action_on_limit", "throttle")
                    self.throttle_speed_kb = data.get("throttle_speed_kb", 50)
                    self.history = data.get("history", {})
            except Exception:
                pass

    def save(self):
        data = {
            "daily_limit_bytes": self.daily_limit_bytes,
            "monthly_limit_bytes": self.monthly_limit_bytes,
            "action_on_limit": self.action_on_limit,
            "throttle_speed_kb": self.throttle_speed_kb,
            "history": self.history
        }
        try:
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def record_usage(self, bytes_transferred: int):
        today = datetime.now().strftime("%Y-%m-%d")
        self.history[today] = self.history.get(today, 0) + bytes_transferred
        self.save()

    def get_today_usage(self) -> int:
        today = datetime.now().strftime("%Y-%m-%d")
        return self.history.get(today, 0)

    def get_monthly_usage(self) -> int:
        cur_month = datetime.now().strftime("%Y-%m")
        total = 0
        for day_str, count in self.history.items():
            if day_str.startswith(cur_month):
                total += count
        return total

    def check_quota_status(self) -> Dict[str, Any]:
        today_bytes = self.get_today_usage()
        month_bytes = self.get_monthly_usage()

        exceeded = False
        reason = "ok"

        if self.daily_limit_bytes > 0 and today_bytes >= self.daily_limit_bytes:
            exceeded = True
            reason = "daily_exceeded"
        elif self.monthly_limit_bytes > 0 and month_bytes >= self.monthly_limit_bytes:
            exceeded = True
            reason = "monthly_exceeded"

        return {
            "exceeded": exceeded,
            "reason": reason,
            "today_bytes": today_bytes,
            "today_fmt": self._format_bytes(today_bytes),
            "monthly_bytes": month_bytes,
            "monthly_fmt": self._format_bytes(month_bytes),
            "daily_limit_bytes": self.daily_limit_bytes,
            "monthly_limit_bytes": self.monthly_limit_bytes,
            "action_on_limit": self.action_on_limit
        }

    @staticmethod
    def _format_bytes(num: float) -> str:
        val = float(num)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if abs(val) < 1024.0:
                return f"{val:3.1f} {unit}"
            val /= 1024.0
        return f"{val:.1f} TB"
