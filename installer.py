import os
import sys
import zipfile
import winreg
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk

VERSION = "3.0.0"
APP_NAME = "Parvan Download Manager"
APP_NAME_FA = "پروان دانلود منیجر"

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

def create_shortcut(target, shortcut_path, icon_path=None, description=""):
    vbs_script = f'''
Set oWS = WScript.CreateObject("WScript.Shell")
Set oLink = oWS.CreateShortcut("{shortcut_path}")
oLink.TargetPath = "{target}"
oLink.WorkingDirectory = "{os.path.dirname(target)}"
oLink.Description = "{description}"
'''
    if icon_path and os.path.exists(icon_path):
        vbs_script += f'oLink.IconLocation = "{icon_path}, 0"\n'
    vbs_script += 'oLink.Save\n'

    temp_vbs = os.path.join(os.environ.get("TEMP", "C:\\Temp"), f"shortcut_{int(os.getpid())}.vbs")
    with open(temp_vbs, "w", encoding="utf-8") as f:
        f.write(vbs_script)
    try:
        subprocess.run(["cscript", "//nologo", temp_vbs], check=True, capture_output=True)
    finally:
        if os.path.exists(temp_vbs):
            os.remove(temp_vbs)

def register_uninstaller(install_dir):
    try:
        uninstall_cmd = os.path.join(install_dir, "uninstall.cmd")
        with open(uninstall_cmd, "w", encoding="utf-8") as f:
            f.write(f'''@echo off
title Uninstall Parvan Download Manager
echo Removing Parvan Download Manager...
taskkill /IM ParvanDownloadManager.exe /F >nul 2>&1
timeout /t 1 >nul
rmdir /s /q "{install_dir}"
reg delete "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\ParvanDownloadManager" /f >nul 2>&1
del "%USERPROFILE%\\Desktop\\Parvan Download Manager.lnk" >nul 2>&1
del "%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\Parvan Download Manager.lnk" >nul 2>&1
echo Parvan Download Manager was uninstalled successfully.
pause
''')

        key_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\ParvanDownloadManager"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, "پروان دانلود منیجر (Parvan Download Manager)")
            winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, VERSION)
            winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, "Ali Hasanifard")
            winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, install_dir)
            winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, os.path.join(install_dir, "icon.ico"))
            winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, f'"{uninstall_cmd}"')
    except Exception as e:
        print("Registry error:", e)


class ParvanInstallerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("برنامه نصب پروان دانلود منیجر | Setup Wizard")
        self.geometry("620x460")
        self.resizable(False, False)
        self.configure(bg="#04060A")

        # Set window icon if exists
        base_dir = get_base_dir()
        ico = os.path.join(base_dir, "icon.ico")
        if os.path.exists(ico):
            try:
                self.iconbitmap(ico)
            except Exception:
                pass

        # Configure custom ttk progress bar style
        self.style = ttk.Style(self)
        try:
            self.style.theme_use('clam')
        except Exception:
            pass
        self.style.configure(
            "Parvan.Horizontal.TProgressbar",
            troughcolor="#0B101D",
            background="#00F5FF",
            bordercolor="#1E293B",
            lightcolor="#00F5FF",
            darkcolor="#00F5FF",
            thickness=10
        )

        default_dir = os.path.join(os.environ.get("LOCALAPPDATA", "C:\\"), "Programs", "ParvanDownloadManager")
        self.target_dir = tk.StringVar(value=default_dir)
        self.create_desktop_shortcut = tk.BooleanVar(value=True)
        self.create_start_shortcut = tk.BooleanVar(value=True)
        self.auto_start = tk.BooleanVar(value=False)
        self.launch_after = tk.BooleanVar(value=True)

        self.container = tk.Frame(self, bg="#04060A")
        self.container.pack(fill="both", expand=True)

        self.load_logo()
        self.show_welcome_screen()

    def load_logo(self):
        base_dir = get_base_dir()
        logo_file = os.path.join(base_dir, "logo.png")
        if os.path.exists(logo_file):
            try:
                img = Image.open(logo_file).resize((72, 72), Image.Resampling.LANCZOS)
                self.logo_img = ImageTk.PhotoImage(img)
            except Exception:
                self.logo_img = None
        else:
            self.logo_img = None

    def clear_container(self):
        for widget in self.container.winfo_children():
            widget.destroy()

    def render_step_bar(self, current_step=1):
        step_bar = tk.Frame(self.container, bg="#070B14", height=32)
        step_bar.pack(fill="x", side="top")
        steps = [
            ("۱. معرفی", 1),
            ("۲. مسیر نصب", 2),
            ("۳. استخراج", 3),
            ("۴. اتمام", 4)
        ]
        wrap = tk.Frame(step_bar, bg="#070B14")
        wrap.pack(anchor="center", pady=5)
        for name, num in steps:
            is_active = num == current_step
            is_done = num < current_step
            color = "#00F5FF" if is_active else ("#00FF88" if is_done else "#475569")
            weight = "bold" if is_active else "normal"
            tk.Label(wrap, text=name, font=("Tahoma", 8, weight), fg=color, bg="#070B14").pack(side="right", padx=12)
            if num < 4:
                tk.Label(wrap, text="‹", font=("Tahoma", 8), fg="#1E293B", bg="#070B14").pack(side="right")

    def show_welcome_screen(self):
        self.clear_container()
        self.render_step_bar(1)

        # Top Banner
        header = tk.Frame(self.container, bg="#090e1a", height=85)
        header.pack(fill="x", side="top")

        if self.logo_img:
            lbl_logo = tk.Label(header, image=self.logo_img, bg="#090e1a")
            lbl_logo.pack(side="right", padx=20, pady=10)

        title_box = tk.Frame(header, bg="#090e1a")
        title_box.pack(side="right", padx=10, pady=16)

        lbl_t1 = tk.Label(title_box, text=APP_NAME_FA, font=("Tahoma", 13, "bold"), fg="#00F5FF", bg="#090e1a")
        lbl_t1.pack(anchor="e")
        lbl_t2 = tk.Label(title_box, text=f"نسخه حرفه‌ای و ضدتحریم — v{VERSION}", font=("Segoe UI", 9), fg="#94A3B8", bg="#090e1a")
        lbl_t2.pack(anchor="e")

        # Body
        body = tk.Frame(self.container, bg="#030407", padx=28, pady=18)
        body.pack(fill="both", expand=True)

        welcome_text = (
            "به دستیار نصب هوشمند پروان دانلود منیجر خوش آمدید.\n"
            "نسل جدید دانلود چندکاناله با نهایت پایداری و کشش سرعت اینترنت:"
        )
        lbl_desc = tk.Label(body, text=welcome_text, font=("Tahoma", 9), fg="#E2E8F0", bg="#030407", justify="right")
        lbl_desc.pack(anchor="e", pady=(0, 10))

        # Highlights Grid
        grid_frame = tk.Frame(body, bg="#080D1A", bd=1, relief="solid", padx=16, pady=12)
        grid_frame.pack(fill="x", pady=8)

        feats = [
            ("⚡ دانلود ۳۲ کانکشن توربو", "تقسیم هوشمند چانک‌ها، ضد فریز ۹۹٪ و تجمیع کارت‌های شبکه"),
            ("🛡️ موتور ضدتحریم و Anti-DPI", "دور زدن اختلالات شبکه بدون نیاز به فیلترشکن خارجی"),
            ("🎬 اسنیفر ویدیو و M3U8", "دریافت استریم‌های آنلاین با انتخاب کیفیت و پخش زنده حین دانلود"),
            ("🧲 موتور بومی تورنت و مگنت", "دانلود فایل‌های P2P و بیت‌تورنت با اعتبارسنجی قطعات"),
            ("🔒 صندوقچه امن و سهمیه اینترنت", "رمزگذاری صف دانلود و کنترل خودکار حجم مصرفی روزانه")
        ]
        for title, sub in feats:
            row = tk.Frame(grid_frame, bg="#080D1A")
            row.pack(fill="x", pady=3)
            tk.Label(row, text=title, font=("Tahoma", 8, "bold"), fg="#00F5FF", bg="#080D1A").pack(side="right")
            tk.Label(row, text=f"— {sub}", font=("Tahoma", 7), fg="#94A3B8", bg="#080D1A").pack(side="right", padx=6)

        # Footer
        footer = tk.Frame(self.container, bg="#070B14", height=55)
        footer.pack(fill="x", side="bottom")

        btn_cancel = tk.Button(footer, text="انصراف", font=("Tahoma", 9), bg="#1E293B", fg="#F8FAFC", activebackground="#334155", activeforeground="#FFFFFF", relief="flat", padx=18, pady=6, cursor="hand2", command=self.destroy)
        btn_cancel.pack(side="left", padx=20, pady=10)

        btn_next = tk.Button(footer, text="بعدی >", font=("Tahoma", 9, "bold"), bg="#00F5FF", fg="#04060A", activebackground="#38BDF8", activeforeground="#000000", relief="flat", padx=24, pady=6, cursor="hand2", command=self.show_directory_screen)
        btn_next.pack(side="right", padx=20, pady=10)

    def show_directory_screen(self):
        self.clear_container()
        self.render_step_bar(2)

        header = tk.Frame(self.container, bg="#090e1a", height=70)
        header.pack(fill="x", side="top")
        tk.Label(header, text="انتخاب مسیر نصب نرم‌افزار", font=("Tahoma", 11, "bold"), fg="#00F5FF", bg="#090e1a").pack(anchor="e", padx=25, pady=8)
        tk.Label(header, text="پوشه‌ای که فایل‌های برنامه در آن نصب می‌شوند را تایید یا تغییر دهید.", font=("Tahoma", 8), fg="#94A3B8", bg="#090e1a").pack(anchor="e", padx=25)

        body = tk.Frame(self.container, bg="#030407", padx=25, pady=20)
        body.pack(fill="both", expand=True)

        tk.Label(body, text="مسیر نصب در حافظه:", font=("Tahoma", 9, "bold"), fg="#E2E8F0", bg="#030407").pack(anchor="e", pady=(0, 5))

        dir_frame = tk.Frame(body, bg="#030407")
        dir_frame.pack(fill="x", pady=5)

        btn_browse = tk.Button(dir_frame, text="انتخاب...", font=("Tahoma", 8), bg="#1e293b", fg="#F3F4F6", relief="flat", padx=12, pady=4, command=self.browse_folder)
        btn_browse.pack(side="left")

        entry_dir = tk.Entry(dir_frame, textvariable=self.target_dir, font=("Consolas", 9), bg="#080c14", fg="#00F5FF", relief="solid", bd=1)
        entry_dir.pack(side="right", fill="x", expand=True, padx=(8, 0))

        # Checkboxes
        opts_box = tk.LabelFrame(body, text="گزینه‌های تکمیلی میانبرها", font=("Tahoma", 8), fg="#94A3B8", bg="#080c14", padx=12, pady=8)
        opts_box.pack(fill="x", pady=16)

        c1 = tk.Checkbutton(opts_box, text="ایجاد میانبر دسکتاپ (Desktop Shortcut)", variable=self.create_desktop_shortcut, font=("Tahoma", 8), fg="#F3F4F6", bg="#080c14", selectcolor="#030407", activebackground="#080c14")
        c1.pack(anchor="e", pady=2)
        c2 = tk.Checkbutton(opts_box, text="افزودن به منوی استارت ویندوز (Start Menu)", variable=self.create_start_shortcut, font=("Tahoma", 8), fg="#F3F4F6", bg="#080c14", selectcolor="#030407", activebackground="#080c14")
        c2.pack(anchor="e", pady=2)

        # Footer
        footer = tk.Frame(self.container, bg="#060912", height=50)
        footer.pack(fill="x", side="bottom")

        btn_back = tk.Button(footer, text="< قبلی", font=("Tahoma", 9), bg="#1e293b", fg="#F3F4F6", relief="flat", padx=16, pady=5, command=self.show_welcome_screen)
        btn_back.pack(side="right", padx=5, pady=10)

        btn_install = tk.Button(footer, text="شروع نصب", font=("Tahoma", 9, "bold"), bg="#00F5FF", fg="#030407", relief="flat", padx=22, pady=5, command=self.start_installation)
        btn_install.pack(side="right", padx=15, pady=10)

    def browse_folder(self):
        chosen = filedialog.askdirectory(initialdir=self.target_dir.get(), title="انتخاب پوشه نصب پروان")
        if chosen:
            self.target_dir.set(os.path.join(chosen, "ParvanDownloadManager"))

    def start_installation(self):
        self.clear_container()
        self.render_step_bar(3)

        header = tk.Frame(self.container, bg="#090e1a", height=70)
        header.pack(fill="x", side="top")
        tk.Label(header, text="در حال نصب پروان دانلود منیجر...", font=("Tahoma", 11, "bold"), fg="#00F5FF", bg="#090e1a").pack(anchor="e", padx=25, pady=12)

        body = tk.Frame(self.container, bg="#030407", padx=30, pady=40)
        body.pack(fill="both", expand=True)

        self.lbl_status = tk.Label(body, text="آماده‌سازی فایل‌های برنامه...", font=("Tahoma", 9), fg="#94A3B8", bg="#030407")
        self.lbl_status.pack(anchor="e", pady=8)

        self.pbar = ttk.Progressbar(body, orient="horizontal", mode="determinate", length=480, style="Parvan.Horizontal.TProgressbar")
        self.pbar.pack(fill="x", pady=10)

        self.after(200, self.perform_unpack)

    def perform_unpack(self):
        target = self.target_dir.get()
        base_dir = get_base_dir()
        payload_zip = os.path.join(base_dir, "app_payload.zip")

        try:
            os.makedirs(target, exist_ok=True)
            if not os.path.exists(payload_zip):
                payload_zip = os.path.join(os.path.dirname(base_dir), "app_payload.zip")

            with zipfile.ZipFile(payload_zip, 'r') as z:
                total_files = len(z.infolist())
                for idx, item in enumerate(z.infolist()):
                    z.extract(item, target)
                    pct = int(((idx + 1) / total_files) * 100)
                    self.pbar["value"] = pct
                    self.lbl_status.config(text=f"استخراج: {item.filename[:45]}")
                    self.update_idletasks()

            # Create Shortcuts
            exe_target = os.path.join(target, "ParvanDownloadManager.exe")
            ico_target = os.path.join(target, "icon.ico")

            if self.create_desktop_shortcut.get():
                desktop = os.path.join(os.path.expanduser("~"), "Desktop")
                desk_link = os.path.join(desktop, "Parvan Download Manager.lnk")
                create_shortcut(exe_target, desk_link, ico_target, "Parvan Download Manager")

            if self.create_start_shortcut.get():
                start_menu = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs")
                start_link = os.path.join(start_menu, "Parvan Download Manager.lnk")
                create_shortcut(exe_target, start_link, ico_target, "Parvan Download Manager")

            # Register in Windows Installed Apps
            register_uninstaller(target)

            self.after(400, self.show_finish_screen)

        except Exception as e:
            messagebox.showerror("خطای نصب", f"در حین نصب خطایی رخ داد:\n{e}")
            self.destroy()

    def show_finish_screen(self):
        self.clear_container()
        self.render_step_bar(4)

        header = tk.Frame(self.container, bg="#090e1a", height=80)
        header.pack(fill="x", side="top")

        if self.logo_img:
            lbl_logo = tk.Label(header, image=self.logo_img, bg="#090e1a")
            lbl_logo.pack(side="right", padx=20, pady=10)

        title_box = tk.Frame(header, bg="#090e1a")
        title_box.pack(side="right", padx=10, pady=15)
        tk.Label(title_box, text="نصب با موفقیت پایان یافت!", font=("Tahoma", 12, "bold"), fg="#10B981", bg="#090e1a").pack(anchor="e")
        tk.Label(title_box, text="Parvan Download Manager is ready to launch.", font=("Segoe UI", 9), fg="#94A3B8", bg="#090e1a").pack(anchor="e")

        body = tk.Frame(self.container, bg="#030407", padx=30, pady=25)
        body.pack(fill="both", expand=True)

        msg = (
            "برنامه پروان دانلود منیجر با موفقیت روی سیستم شما نصب گردید.\n\n"
            "✓ موتور ضدتحریم و Anti-DPI فعال است.\n"
            "✓ ریموت تحت شبکه محلی آماده به کار می‌باشد.\n"
            "✓ میانبرهای دسترسی سریع روی دسکتاپ و استارت منو ایجاد شد.\n"
        )
        tk.Label(body, text=msg, font=("Tahoma", 9), fg="#E2E8F0", bg="#030407", justify="right").pack(anchor="e", pady=8)

        c_launch = tk.Checkbutton(body, text="اجرای فوری پروان دانلود منیجر (Launch now)", variable=self.launch_after, font=("Tahoma", 9, "bold"), fg="#00F5FF", bg="#030407", selectcolor="#080c14", activebackground="#030407")
        c_launch.pack(anchor="e", pady=12)

        footer = tk.Frame(self.container, bg="#060912", height=50)
        footer.pack(fill="x", side="bottom")

        btn_finish = tk.Button(footer, text="پایان و خروج", font=("Tahoma", 9, "bold"), bg="#10B981", fg="#030407", relief="flat", padx=26, pady=5, command=self.finish_installation)
        btn_finish.pack(side="right", padx=20, pady=10)

    def finish_installation(self):
        if self.launch_after.get():
            target_exe = os.path.join(self.target_dir.get(), "ParvanDownloadManager.exe")
            if os.path.exists(target_exe):
                subprocess.Popen([target_exe], cwd=self.target_dir.get())
        self.destroy()

if __name__ == "__main__":
    app = ParvanInstallerApp()
    app.mainloop()
