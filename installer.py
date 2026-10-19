import os
import sys
import zipfile
import winreg
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk

VERSION = "2.5.0"
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
        self.geometry("560x420")
        self.resizable(False, False)
        self.configure(bg="#07090E")

        # Set window icon if exists
        base_dir = get_base_dir()
        ico = os.path.join(base_dir, "icon.ico")
        if os.path.exists(ico):
            try:
                self.iconbitmap(ico)
            except Exception:
                pass

        default_dir = os.path.join(os.environ.get("LOCALAPPDATA", "C:\\"), "Programs", "ParvanDownloadManager")
        self.target_dir = tk.StringVar(value=default_dir)
        self.create_desktop_shortcut = tk.BooleanVar(value=True)
        self.create_start_shortcut = tk.BooleanVar(value=True)
        self.auto_start = tk.BooleanVar(value=False)
        self.launch_after = tk.BooleanVar(value=True)

        self.container = tk.Frame(self, bg="#07090E")
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

    def show_welcome_screen(self):
        self.clear_container()

        # Top Banner
        header = tk.Frame(self.container, bg="#101626", height=90)
        header.pack(fill="x", side="top")

        if self.logo_img:
            lbl_logo = tk.Label(header, image=self.logo_img, bg="#101626")
            lbl_logo.pack(side="right", padx=20, pady=10)

        title_box = tk.Frame(header, bg="#101626")
        title_box.pack(side="right", padx=10, pady=18)

        lbl_t1 = tk.Label(title_box, text=APP_NAME_FA, font=("Tahoma", 13, "bold"), fg="#00F5FF", bg="#101626")
        lbl_t1.pack(anchor="e")
        lbl_t2 = tk.Label(title_box, text=f"Setup Wizard — v{VERSION}", font=("Segoe UI", 9), fg="#94A3B8", bg="#101626")
        lbl_t2.pack(anchor="e")

        # Body
        body = tk.Frame(self.container, bg="#07090E", padx=30, pady=25)
        body.pack(fill="both", expand=True)

        welcome_text = (
            "به دستیار نصب پروان دانلود منیجر خوش آمدید.\n\n"
            "این نرم‌افزار، قدرتمندترین ابزار دانلود چندکاناله برای ویندوز است\n"
            "که سرعت دانلود شما را با ۱۶ الی ۳۲ کانکشن همزمان به اوج می‌رساند.\n\n"
            "برای ادامه فرایند نصب روی دکمه «بعدی >» کلیک کنید."
        )
        lbl_desc = tk.Label(body, text=welcome_text, font=("Tahoma", 9), fg="#F3F4F6", bg="#07090E", justify="right")
        lbl_desc.pack(anchor="e", pady=10)

        # Footer
        footer = tk.Frame(self.container, bg="#0B0F19", height=55)
        footer.pack(fill="x", side="bottom")

        btn_cancel = tk.Button(footer, text="انصراف", font=("Tahoma", 9), bg="#162035", fg="#F3F4F6", relief="flat", padx=16, pady=5, command=self.destroy)
        btn_cancel.pack(side="left", padx=20, pady=12)

        btn_next = tk.Button(footer, text="بعدی >", font=("Tahoma", 9, "bold"), bg="#00F5FF", fg="#07090E", relief="flat", padx=22, pady=5, command=self.show_directory_screen)
        btn_next.pack(side="right", padx=20, pady=12)

    def show_directory_screen(self):
        self.clear_container()

        header = tk.Frame(self.container, bg="#101626", height=70)
        header.pack(fill="x", side="top")
        tk.Label(header, text="انتخاب مسیر نصب نرم‌افزار", font=("Tahoma", 11, "bold"), fg="#00F5FF", bg="#101626").pack(anchor="e", padx=25, pady=10)
        tk.Label(header, text="پوشه‌ای که فایل‌های پروان دانلود منیجر در آن قرار می‌گیرد را مشخص کنید.", font=("Tahoma", 8), fg="#94A3B8", bg="#101626").pack(anchor="e", padx=25)

        body = tk.Frame(self.container, bg="#07090E", padx=25, pady=20)
        body.pack(fill="both", expand=True)

        tk.Label(body, text="مسیر نصب:", font=("Tahoma", 9, "bold"), fg="#F3F4F6", bg="#07090E").pack(anchor="e", pady=(0, 5))
        
        dir_frame = tk.Frame(body, bg="#07090E")
        dir_frame.pack(fill="x", pady=5)

        btn_browse = tk.Button(dir_frame, text="انتخاب...", font=("Tahoma", 8), bg="#162035", fg="#F3F4F6", relief="flat", padx=10, pady=4, command=self.browse_folder)
        btn_browse.pack(side="left")

        entry_dir = tk.Entry(dir_frame, textvariable=self.target_dir, font=("Consolas", 9), bg="#101626", fg="#00F5FF", relief="solid", bd=1)
        entry_dir.pack(side="right", fill="x", expand=True, padx=(8, 0))

        # Checkboxes
        opts_box = tk.LabelFrame(body, text="گزینه‌های تکمیلی", font=("Tahoma", 9), fg="#94A3B8", bg="#07090E", padx=12, pady=10)
        opts_box.pack(fill="x", pady=20)

        c1 = tk.Checkbutton(opts_box, text="ایجاد میانبر روی صفحه دسکتاپ (Desktop Shortcut)", variable=self.create_desktop_shortcut, font=("Tahoma", 8), fg="#F3F4F6", bg="#07090E", selectcolor="#101626", activebackground="#07090E")
        c1.pack(anchor="e", pady=2)
        c2 = tk.Checkbutton(opts_box, text="افزودن به منوی استارت ویندوز (Start Menu)", variable=self.create_start_shortcut, font=("Tahoma", 8), fg="#F3F4F6", bg="#07090E", selectcolor="#101626", activebackground="#07090E")
        c2.pack(anchor="e", pady=2)

        # Footer
        footer = tk.Frame(self.container, bg="#0B0F19", height=55)
        footer.pack(fill="x", side="bottom")

        btn_back = tk.Button(footer, text="< قبلی", font=("Tahoma", 9), bg="#162035", fg="#F3F4F6", relief="flat", padx=16, pady=5, command=self.show_welcome_screen)
        btn_back.pack(side="right", padx=5, pady=12)

        btn_install = tk.Button(footer, text="شروع نصب", font=("Tahoma", 9, "bold"), bg="#00F5FF", fg="#07090E", relief="flat", padx=22, pady=5, command=self.start_installation)
        btn_install.pack(side="right", padx=15, pady=12)

    def browse_folder(self):
        chosen = filedialog.askdirectory(initialdir=self.target_dir.get(), title="انتخاب پوشه نصب پروان")
        if chosen:
            self.target_dir.set(os.path.join(chosen, "ParvanDownloadManager"))

    def start_installation(self):
        self.clear_container()

        header = tk.Frame(self.container, bg="#101626", height=70)
        header.pack(fill="x", side="top")
        tk.Label(header, text="در حال نصب پروان دانلود منیجر...", font=("Tahoma", 11, "bold"), fg="#00F5FF", bg="#101626").pack(anchor="e", padx=25, pady=12)

        body = tk.Frame(self.container, bg="#07090E", padx=30, pady=40)
        body.pack(fill="both", expand=True)

        self.lbl_status = tk.Label(body, text="آماده‌سازی فایل‌های برنامه...", font=("Tahoma", 9), fg="#94A3B8", bg="#07090E")
        self.lbl_status.pack(anchor="e", pady=8)

        self.pbar = ttk.Progressbar(body, orient="horizontal", mode="determinate", length=480)
        self.pbar.pack(fill="x", pady=10)

        self.after(200, self.perform_unpack)

    def perform_unpack(self):
        target = self.target_dir.get()
        base_dir = get_base_dir()
        payload_zip = os.path.join(base_dir, "app_payload.zip")

        try:
            os.makedirs(target, exist_ok=True)
            if not os.path.exists(payload_zip):
                # Search parent or current dir
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

        header = tk.Frame(self.container, bg="#101626", height=80)
        header.pack(fill="x", side="top")

        if self.logo_img:
            lbl_logo = tk.Label(header, image=self.logo_img, bg="#101626")
            lbl_logo.pack(side="right", padx=20, pady=10)

        title_box = tk.Frame(header, bg="#101626")
        title_box.pack(side="right", padx=10, pady=15)
        tk.Label(title_box, text="نصب با موفقیت پایان یافت!", font=("Tahoma", 12, "bold"), fg="#10B981", bg="#101626").pack(anchor="e")
        tk.Label(title_box, text="Parvan Download Manager has been installed.", font=("Segoe UI", 9), fg="#94A3B8", bg="#101626").pack(anchor="e")

        body = tk.Frame(self.container, bg="#07090E", padx=30, pady=30)
        body.pack(fill="both", expand=True)

        msg = (
            "برنامه پروان دانلود منیجر با موفقیت روی سیستم شما نصب و آماده استفاده شد.\n\n"
            "• میانبر برنامه روی دسکتاپ و منوی استارت ایجاد گردید.\n"
            "• افزونه مرورگر در پوشه browser-extension جهت اتصال به کروم و اج موجود است.\n"
        )
        tk.Label(body, text=msg, font=("Tahoma", 9), fg="#F3F4F6", bg="#07090E", justify="right").pack(anchor="e", pady=10)

        c_launch = tk.Checkbutton(body, text="اجرای پروان دانلود منیجر (Launch now)", variable=self.launch_after, font=("Tahoma", 9, "bold"), fg="#00F5FF", bg="#07090E", selectcolor="#101626", activebackground="#07090E")
        c_launch.pack(anchor="e", pady=15)

        footer = tk.Frame(self.container, bg="#0B0F19", height=55)
        footer.pack(fill="x", side="bottom")

        btn_finish = tk.Button(footer, text="پایان (Finish)", font=("Tahoma", 9, "bold"), bg="#10B981", fg="#07090E", relief="flat", padx=26, pady=5, command=self.finish_installation)
        btn_finish.pack(side="right", padx=20, pady=12)

    def finish_installation(self):
        if self.launch_after.get():
            target_exe = os.path.join(self.target_dir.get(), "ParvanDownloadManager.exe")
            if os.path.exists(target_exe):
                subprocess.Popen([target_exe], cwd=self.target_dir.get())
        self.destroy()

if __name__ == "__main__":
    app = ParvanInstallerApp()
    app.mainloop()
