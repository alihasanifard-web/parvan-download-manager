# -*- coding: utf-8 -*-
"""
Parvan Windows Desktop Integrator (v3.0)
1. System Tray Icon with interactive menu (pystray or Win32 fallback)
2. Windows Native Toast Notifications (Win10/11)
3. Windows Explorer Context Menu integration (HKCU\\Software\\Classes)
"""

import os
import sys
import threading
import winreg
from typing import Callable, Optional

# --- 1. Windows Explorer Shell Context Menu ---
class WindowsShellIntegration:
    PROG_ID = "ParvanDownloadManager"
    
    @classmethod
    def register_context_menu(cls, app_exe_path: str) -> bool:
        """Registers 'Download with Parvan' in Windows Explorer context menu."""
        try:
            exe_clean = f'"{os.path.abspath(app_exe_path)}"'
            
            # Register for torrent files
            key_path = r"Software\Classes\.torrent\OpenWithProgids"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as k:
                winreg.SetValueEx(k, cls.PROG_ID, 0, winreg.REG_SZ, "")

            # Shell handler for ParvanProgID
            cmd_key = rf"Software\Classes\{cls.PROG_ID}\shell\open\command"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, cmd_key) as k:
                winreg.SetValue(k, "", winreg.REG_SZ, f'{exe_clean} "%1"')

            # Friendly name and icon
            shell_key = rf"Software\Classes\{cls.PROG_ID}\shell\open"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, shell_key) as k:
                winreg.SetValue(k, "", winreg.REG_SZ, "Download with Parvan")
                winreg.SetValueEx(k, "Icon", 0, winreg.REG_SZ, os.path.abspath(app_exe_path))

            # General background context menu (right click inside folder or desktop)
            bg_cmd_key = r"Software\Classes\Directory\Background\shell\ParvanDownloadManager\command"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, bg_cmd_key) as k:
                winreg.SetValue(k, "", winreg.REG_SZ, exe_clean)
            
            bg_menu_key = r"Software\Classes\Directory\Background\shell\ParvanDownloadManager"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, bg_menu_key) as k:
                winreg.SetValue(k, "", winreg.REG_SZ, "پروان دانلود منیجر")
                winreg.SetValueEx(k, "Icon", 0, winreg.REG_SZ, os.path.abspath(app_exe_path))

            return True
        except Exception as e:
            print(f"[WindowsShell] Register failed: {e}")
            return False

    @classmethod
    def unregister_context_menu(cls) -> bool:
        """Removes context menu registry entries."""
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\Directory\Background\shell\ParvanDownloadManager\command")
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\Directory\Background\shell\ParvanDownloadManager")
            return True
        except Exception:
            return False


# --- 2. Windows Native Toast Notifications ---
class WindowsToastNotifier:
    @classmethod
    def show_toast(cls, title: str, message: str, file_path: Optional[str] = None):
        """Dispatches a native Windows notification using PowerShell script asynchronously."""
        def _run():
            try:
                # Escape PowerShell strings
                safe_title = title.replace('"', '`"')
                safe_msg = message.replace('"', '`"')
                ps_code = f"""
                [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
                $template = [Windows.UI.Notifications.ToastTemplateType]::ToastText02
                $xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent($template)
                $textNodes = $xml.GetElementsByTagName('text')
                $textNodes.Item(0).AppendChild($xml.CreateTextNode("{safe_title}")) > $null
                $textNodes.Item(1).AppendChild($xml.CreateTextNode("{safe_msg}")) > $null
                $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
                $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Parvan Download Manager")
                $notifier.Show($toast)
                """
                import subprocess
                subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_code],
                               creationflags=0x08000000, timeout=5)
            except Exception as e:
                print(f"[Toast] Warning: {e}")

        threading.Thread(target=_run, daemon=True).start()


# --- 3. System Tray Manager ---
class SystemTrayManager:
    def __init__(self, on_show_window: Callable, on_exit: Callable, on_pause_all: Callable, on_resume_all: Callable):
        self.on_show_window = on_show_window
        self.on_exit = on_exit
        self.on_pause_all = on_pause_all
        self.on_resume_all = on_resume_all
        self.icon = None
        self._thread = None

    def start(self, icon_path: Optional[str] = None):
        def _tray_worker():
            try:
                import pystray
                from PIL import Image, ImageDraw

                if icon_path and os.path.exists(icon_path):
                    image = Image.open(icon_path)
                else:
                    # Generate cyan square icon fallback
                    image = Image.new('RGB', (64, 64), color=(6, 182, 212))
                    d = ImageDraw.Draw(image)
                    d.rectangle([16, 16, 48, 48], fill=(15, 23, 42))

                menu = pystray.Menu(
                    pystray.MenuItem("نمایش پنجره پروان", lambda icon, item: self.on_show_window()),
                    pystray.Menu.SEPARATOR,
                    pystray.MenuItem("توقف همه دانلودها", lambda icon, item: self.on_pause_all()),
                    pystray.MenuItem("ادامه همه دانلودها", lambda icon, item: self.on_resume_all()),
                    pystray.Menu.SEPARATOR,
                    pystray.MenuItem("خروج کامل", lambda icon, item: self._handle_exit(icon))
                )

                self.icon = pystray.Icon("ParvanDownloadManager", image, "پروان دانلود منیجر", menu)
                self.icon.run()
            except ImportError:
                print("[SystemTray] pystray not installed, skipping GUI tray loop.")
            except Exception as e:
                print(f"[SystemTray] Tray error: {e}")

        self._thread = threading.Thread(target=_tray_worker, daemon=True)
        self._thread.start()

    def _handle_exit(self, icon):
        icon.stop()
        self.on_exit()

    def stop(self):
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
