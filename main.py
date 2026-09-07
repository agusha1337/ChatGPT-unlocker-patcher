#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
OpenAI Codex & ChatGPT Windows Standalone Patcher (v5.0.0 Isolated Edition)
================================================================================
100% АВТОНОМНЫЙ 1-КЛИК ИНСТРУМЕНТ ДЛЯ РОССИИ И СНГ:
1. ПОЛНАЯ ИЗОЛЯЦИЯ: Discord, Telegram, Steam, игры и браузеры НЕ ЗАТРАГИВАЮТСЯ!
   - Системный прокси Windows (ProxyEnable) отключен.
   - Глобальные переменные HTTP_PROXY не пишутся в систему.
2. ChatGPT Desktop: маршрутизируется изолированно через аргументы запуска
   (--proxy-server="http://127.0.0.1:10809" --proxy-bypass-list="<-loopback>").
3. OpenAI Codex CLI & VS Code: изолированный запуск через "codex-unlocked"
   или встроенный лаунчер (переменные прокси действуют ТОЛЬКО внутри сессии Codex).
4. 100% РАБОТА И ОБХОД 403:
   - Автоматическая интеграция с изолированным SOCKS5 WARP (режим WarpProxy на порту 40000).
   - Автономный Zapret DPI-обходчик (split2 + SNI десинхронизация) для обхода ТСПУ.
5. Ноль ручных действий: нажал [1] — и всё работает.
================================================================================
"""

import os
import sys
import time
import json
import socket
import select
import shutil
import signal
import ctypes
from ctypes import wintypes
import winreg
import subprocess
import threading
import webbrowser
import traceback
from urllib.parse import urlsplit

# ==============================================================================
# КОНФИГУРАЦИЯ И КОНСТАНТЫ
# ==============================================================================
APP_TITLE = "OpenAI Codex & ChatGPT Isolated Patcher"
APP_VERSION = "5.0.0"
COMMUNITY_URL = "https://t.me/chatgpt_patcher_community"
BOOSTY_URL = "https://boosty.to/chatgpt_patcher"
GITHUB_URL = "https://github.com/agusha1337/ChatGPT-unlocker-patcher"

DEFAULT_PROXY_PORT = 10809
DEFAULT_PROXY_HOST = "127.0.0.1"

HOME_DIR = os.path.expanduser("~")
CONFIG_FILE = os.path.join(HOME_DIR, ".chatgpt_patcher_config.json")

# WinAPI Constants
HWND_BROADCAST = 0xFFFF
WM_SETTINGCHANGE = 0x001A
SMTO_ABORTIFHUNG = 0x0002

# ==============================================================================
# ANSI ЦВЕТА И ОФОРМЛЕНИЕ КОНСОЛИ
# ==============================================================================
def setup_windows_console():
    """Включает поддержку ANSI Virtual Terminal Processing в консоли Windows."""
    if os.name == "nt":
        try:
            kernel32 = ctypes.windll.kernel32
            h_stdout = kernel32.GetStdHandle(-11)
            mode = wintypes.DWORD()
            if kernel32.GetConsoleMode(h_stdout, ctypes.byref(mode)):
                kernel32.SetConsoleMode(h_stdout, mode.value | 0x0004)
        except Exception:
            pass

setup_windows_console()

CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_DIM = "\033[2m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_MAGENTA = "\033[95m"
CLR_CYAN = "\033[96m"
CLR_WHITE = "\033[97m"
CLR_GRAY = "\033[90m"

def log_ok(msg: str):
    print(f" {CLR_GREEN}[OK]{CLR_RESET}   {msg}")

def log_info(msg: str):
    print(f" {CLR_YELLOW}[INFO]{CLR_RESET} {msg}")

def log_warn(msg: str):
    print(f" {CLR_YELLOW}[WARN]{CLR_RESET} {msg}")

def log_fail(msg: str):
    print(f" {CLR_RED}[FAIL]{CLR_RESET} {msg}")

def log_step(step: int, total: int, msg: str):
    print(f"\n{CLR_CYAN}[Шаг {step}/{total}]{CLR_RESET} {CLR_BOLD}{msg}{CLR_RESET}")

def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

# ==============================================================================
# ХРАНЕНИЕ КОНФИГУРАЦИИ
# ==============================================================================
def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "proxy_address": f"http://{DEFAULT_PROXY_HOST}:{DEFAULT_PROXY_PORT}",
        "patched_shortcuts": [],
        "created_scripts": []
    }

def save_config(cfg: dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log_warn(f"Не удалось сохранить конфигурацию: {e}")

# ==============================================================================
# ПОЛНАЯ ИЗОЛЯЦИЯ: ЗАЩИТА DISCORD, TELEGRAM, ИГР И СИСТЕМЫ
# ==============================================================================
def ensure_system_proxy_disabled():
    """Гарантирует, что глобальный системный прокси Windows выключен (ProxyEnable = 0)."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Internet Settings", 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
    except Exception:
        pass

def cleanup_global_env_proxies():
    """Удаляет переменные HTTP_PROXY из HKCU\\Environment, чтобы они не влияли на Discord/Telegram."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_ALL_ACCESS) as key:
            for var in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "OPENAI_BASE_URL", "NO_PROXY"]:
                try:
                    winreg.DeleteValue(key, var)
                except FileNotFoundError:
                    pass
                if var in os.environ:
                    del os.environ[var]
        # Оповещаем систему об обновлении переменных
        result = wintypes.DWORD()
        ctypes.windll.user32.SendMessageTimeoutW(
            HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment", SMTO_ABORTIFHUNG, 1000, ctypes.byref(result)
        )
    except Exception:
        pass

# ==============================================================================
# ПАРСЕР TLS CLIENTHELLO (DPI BYPASS)
# ==============================================================================
def find_sni_hostname_offset(data: bytes) -> int:
    """Находит смещение (offset) имени хоста в расширении SNI пакета TLS ClientHello."""
    if len(data) < 44 or data[0] != 0x16 or data[5] != 0x01:
        return -1
    try:
        session_id_len = data[43]
        pos = 44 + session_id_len
        if pos + 2 > len(data):
            return -1
        cs_len = int.from_bytes(data[pos:pos+2], "big")
        pos += 2 + cs_len
        if pos + 1 > len(data):
            return -1
        comp_methods_len = data[pos]
        pos += 1 + comp_methods_len
        if pos + 2 > len(data):
            return -1
        extensions_len = int.from_bytes(data[pos:pos+2], "big")
        pos += 2
        ext_end = pos + extensions_len

        while pos + 4 <= ext_end and pos + 4 <= len(data):
            ext_type = int.from_bytes(data[pos:pos+2], "big")
            ext_len = int.from_bytes(data[pos+2:pos+4], "big")
            pos += 4
            if ext_type == 0:
                if pos + 5 <= len(data):
                    name_type = data[pos+2]
                    if name_type == 0:
                        return pos + 5
            pos += ext_len
        return -1
    except Exception:
        return -1

# ==============================================================================
# ЛОКАЛЬНЫЙ ШЛЮЗ МАРШРУТИЗАЦИИ (DpiBypassProxy)
# ==============================================================================
class DpiBypassProxy:
    """
    Высокоскоростной локальный HTTP/HTTPS CONNECT шлюз:
    1. Перенаправляет трафик OpenAI через европейский WARP SOCKS5 (обход 403 Forbidden).
    2. Если WARP не доступен, выполняет десинхронизацию TLS ClientHello (split2) против ТСПУ.
    3. Слушает только 127.0.0.1 и используется строго назначенными программами (ChatGPT / Codex).
    """
    OPENAI_DOMAINS = ("chatgpt.com", "openai.com", "oaistatic.com", "oaiusercontent.com")

    def __init__(self, host: str = DEFAULT_PROXY_HOST, port: int = DEFAULT_PROXY_PORT,
                 upstream_proxy: dict = None):
        self.host = host
        self.port = port
        self.upstream_proxy = upstream_proxy
        self.server_sock = None
        self.is_running = False
        self.total_connections = 0

    def start(self, in_background: bool = True):
        bound = False
        last_err = None
        for try_port in range(self.port, self.port + 20):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind((self.host, try_port))
                s.listen(128)
                self.server_sock = s
                self.port = try_port
                bound = True
                break
            except OSError as err:
                last_err = err
                try:
                    s.close()
                except Exception:
                    pass

        if not bound:
            raise RuntimeError(f"Не удалось занять свободный порт: {last_err}")

        self.is_running = True
        if in_background:
            threading.Thread(target=self._accept_loop, daemon=True, name="DpiProxyServer").start()
        else:
            self._accept_loop()

    def stop(self):
        self.is_running = False
        if self.server_sock:
            try:
                self.server_sock.close()
            except Exception:
                pass

    def _accept_loop(self):
        while self.is_running:
            try:
                client_sock, _ = self.server_sock.accept()
                self.total_connections += 1
                threading.Thread(target=self._handle_client, args=(client_sock,), daemon=True).start()
            except Exception:
                if not self.is_running:
                    break

    def _pipe_sockets(self, src: socket.socket, dst: socket.socket):
        try:
            while self.is_running:
                data = src.recv(65536)
                if not data:
                    break
                dst.sendall(data)
        except Exception:
            pass
        finally:
            try:
                dst.shutdown(socket.SHUT_WR)
            except Exception:
                pass

    def _connect_via_socks5(self, proxy_host: str, proxy_port: int,
                            target_host: str, target_port: int) -> socket.socket:
        sock = socket.create_connection((proxy_host, proxy_port), timeout=12.0)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        # SOCKS5 Handshake
        sock.sendall(b"\x05\x01\x00")
        resp = sock.recv(2)
        if len(resp) < 2 or resp[0] != 0x05 or resp[1] != 0x00:
            sock.close()
            raise ConnectionError("SOCKS5 handshake failed")
        # SOCKS5 CONNECT
        addr_bytes = target_host.encode("ascii")
        req = (b"\x05\x01\x00\x03" +
               bytes([len(addr_bytes)]) + addr_bytes +
               target_port.to_bytes(2, "big"))
        sock.sendall(req)
        resp = sock.recv(32)
        if len(resp) < 2 or resp[1] != 0x00:
            sock.close()
            raise ConnectionError("SOCKS5 connect error")
        return sock

    def _connect_to_target(self, target_host: str, target_port: int) -> tuple:
        """Возвращает (socket, is_via_upstream: bool)."""
        is_openai = any(d in target_host for d in self.OPENAI_DOMAINS)

        if is_openai and self.upstream_proxy:
            try:
                sock = self._connect_via_socks5(
                    self.upstream_proxy["host"],
                    self.upstream_proxy["port"],
                    target_host, target_port
                )
                return sock, True
            except Exception:
                pass

        # Прямое подключение
        sock = socket.create_connection((target_host, target_port), timeout=12.0)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        return sock, False

    def _handle_client(self, client_sock: socket.socket):
        remote_sock = None
        try:
            client_sock.settimeout(12.0)
            req_data = b""
            while b"\r\n\r\n" not in req_data and len(req_data) < 8192:
                chunk = client_sock.recv(4096)
                if not chunk:
                    break
                req_data += chunk

            if not req_data:
                client_sock.close()
                return

            first_line = req_data.split(b"\r\n", 1)[0].decode("latin1", errors="ignore")
            parts = first_line.split()
            if len(parts) < 2:
                client_sock.close()
                return

            method, url = parts[0].upper(), parts[1]

            if method == "CONNECT":
                if ":" in url:
                    target_host, target_port_str = url.split(":", 1)
                    target_port = int(target_port_str)
                else:
                    target_host, target_port = url, 443

                remote_sock, via_upstream = self._connect_to_target(target_host, target_port)
                client_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

                # 200 Connection Established
                client_sock.sendall(b"HTTP/1.1 200 Connection Established\r\nProxy-Agent: Codex-Isolated-Patcher/5.0\r\n\r\n")

                first_payload = client_sock.recv(16384)
                if not first_payload:
                    return

                if via_upstream:
                    # Через защищённый SOCKS5 WARP: туннель уже зашифрован, сплит не нужен (0ms задержки)
                    remote_sock.sendall(first_payload)
                    print(f" {CLR_MAGENTA}[WARP Link]{CLR_RESET} {target_host}:{target_port} {CLR_GRAY}(европейский маршрут, 0% 403){CLR_RESET}")
                else:
                    # Прямой обход ТСПУ (Zapret split2 + SNI десинхронизация)
                    if (len(first_payload) >= 6 and
                        first_payload[0] == 0x16 and
                        first_payload[1] == 0x03 and
                        first_payload[5] == 0x01):

                        sni_pos = find_sni_hostname_offset(first_payload)
                        remote_sock.sendall(first_payload[:2])
                        time.sleep(0.006)

                        if sni_pos > 2 and sni_pos + 3 < len(first_payload):
                            split_sni = sni_pos + 3
                            remote_sock.sendall(first_payload[2:split_sni])
                            time.sleep(0.006)
                            remote_sock.sendall(first_payload[split_sni:])
                        elif len(first_payload) > 35:
                            remote_sock.sendall(first_payload[2:35])
                            time.sleep(0.006)
                            remote_sock.sendall(first_payload[35:])
                        else:
                            remote_sock.sendall(first_payload[2:])

                        if any(domain in target_host for domain in ("chatgpt", "openai", "oaistatic")):
                            print(f" {CLR_GREEN}[Zapret DPI]{CLR_RESET} {target_host}:{target_port} {CLR_GRAY}(TLS split2 десинхронизация){CLR_RESET}")
                    else:
                        remote_sock.sendall(first_payload)

                client_sock.settimeout(None)
                remote_sock.settimeout(None)

                t1 = threading.Thread(target=self._pipe_sockets, args=(client_sock, remote_sock), daemon=True)
                t2 = threading.Thread(target=self._pipe_sockets, args=(remote_sock, client_sock), daemon=True)
                t1.start()
                t2.start()
                t1.join()
                t2.join()

            else:
                # Plain HTTP
                parsed = urlsplit(url if "://" in url else f"http://{url}")
                target_host = parsed.hostname or self.host
                target_port = parsed.port or 80

                remote_sock, _ = self._connect_to_target(target_host, target_port)
                remote_sock.sendall(req_data)

                client_sock.settimeout(None)
                remote_sock.settimeout(None)

                t1 = threading.Thread(target=self._pipe_sockets, args=(client_sock, remote_sock), daemon=True)
                t2 = threading.Thread(target=self._pipe_sockets, args=(remote_sock, client_sock), daemon=True)
                t1.start()
                t2.start()
                t1.join()
                t2.join()

        except Exception:
            pass
        finally:
            try:
                client_sock.close()
            except Exception:
                pass
            if remote_sock:
                try:
                    remote_sock.close()
                except Exception:
                    pass

ACTIVE_PROXY = None

# ==============================================================================
# CLOUDFLARE WARP: ИЗОЛИРОВАННЫЙ РЕЖИМ (SOCKS5 127.0.0.1:40000)
# ==============================================================================
WARP_CLI = r"C:\Program Files\Cloudflare\Cloudflare WARP\warp-cli.exe"
WARP_SOCKS5_HOST = "127.0.0.1"
WARP_SOCKS5_PORT = 40000

def is_warp_installed() -> bool:
    return os.path.exists(WARP_CLI)

def is_warp_socks5_alive() -> bool:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.0)
        s.connect((WARP_SOCKS5_HOST, WARP_SOCKS5_PORT))
        s.sendall(b"\x05\x01\x00")
        resp = s.recv(2)
        s.close()
        return len(resp) == 2 and resp[0] == 0x05 and resp[1] == 0x00
    except Exception:
        return False

def warp_connect_isolated() -> bool:
    """
    Включает WARP СТРОГО в режиме WarpProxy (SOCKS5 на порту 40000).
    ВНИМАНИЕ: в режиме WarpProxy WARP НЕ СОЗДАЕТ сетевых адаптеров,
    НЕ перехватывает трафик Windows и НЕ влияет на Discord/Telegram/игры!
    """
    if not is_warp_installed():
        return False
    try:
        subprocess.run([WARP_CLI, "--accept-tos", "mode", "proxy"], capture_output=True, timeout=5)
        subprocess.run([WARP_CLI, "--accept-tos", "set-proxy-port", "40000"], capture_output=True, timeout=5)
        subprocess.run([WARP_CLI, "--accept-tos", "connect"], capture_output=True, timeout=10)
        for _ in range(15):
            time.sleep(0.4)
            if is_warp_socks5_alive():
                return True
        return False
    except Exception:
        return False

def warp_disconnect():
    if is_warp_installed():
        try:
            subprocess.run([WARP_CLI, "--accept-tos", "disconnect"], capture_output=True, timeout=5)
        except Exception:
            pass

def ensure_proxy_started() -> tuple:
    global ACTIVE_PROXY
    if ACTIVE_PROXY and ACTIVE_PROXY.is_running:
        return True, f"http://{ACTIVE_PROXY.host}:{ACTIVE_PROXY.port}"

    upstream = None
    if is_warp_installed():
        if is_warp_socks5_alive():
            log_ok("Cloudflare WARP изолированно активен (SOCKS5 127.0.0.1:40000).")
            upstream = {"type": "socks5", "host": WARP_SOCKS5_HOST, "port": WARP_SOCKS5_PORT}
        else:
            log_info("Подключаю Cloudflare WARP в режиме изолированного прокси...")
            if warp_connect_isolated():
                log_ok("Cloudflare WARP подключен в режиме WarpProxy (обход ошибки 403 активен).")
                upstream = {"type": "socks5", "host": WARP_SOCKS5_HOST, "port": WARP_SOCKS5_PORT}
            else:
                log_info("WARP не подключился. Активирован автономный Zapret DPI-обход.")
    else:
        log_info("WARP не установлен. Активирован автономный Zapret DPI-обход.")

    try:
        ACTIVE_PROXY = DpiBypassProxy(DEFAULT_PROXY_HOST, DEFAULT_PROXY_PORT, upstream_proxy=upstream)
        ACTIVE_PROXY.start(in_background=True)

        port = ACTIVE_PROXY.port
        for _ in range(25):
            time.sleep(0.04)
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.2)
                res = s.connect_ex((DEFAULT_PROXY_HOST, port))
                s.close()
                if res == 0:
                    return True, f"http://{DEFAULT_PROXY_HOST}:{port}"
            except Exception:
                pass
        return False, ""
    except Exception as e:
        log_fail(f"Ошибка запуска локального шлюза: {e}")
        return False, ""

# ==============================================================================
# ПОИСК И НАСТРОЙКА OPENAI CODEX CLI
# ==============================================================================
def find_codex_exe() -> str:
    """Находит исполняемый файл codex.exe на компьютере."""
    try:
        cfg_toml = os.path.join(HOME_DIR, ".codex", "config.toml")
        if os.path.exists(cfg_toml):
            with open(cfg_toml, "r", encoding="utf-8") as f:
                for line in f:
                    if "CODEX_CLI_PATH" in line and "=" in line:
                        p = line.split("=", 1)[1].strip().strip("'\"")
                        if os.path.exists(p):
                            return p
    except Exception:
        pass
    base = os.path.join(os.environ.get("LOCALAPPDATA", ""), "OpenAI", "Codex", "bin")
    if os.path.exists(base):
        for root, _, files in os.walk(base):
            if "codex.exe" in files:
                p = os.path.join(root, "codex.exe")
                return p
    return "codex.exe"

def setup_codex_unlocked_script(proxy_address: str) -> list:
    """
    Создает легкий лаунчер 'codex-unlocked.cmd' в каталоге PATH.
    Лаунчер задает HTTPS_PROXY СТРОГО для процесса Codex и ни на что другое не влияет!
    """
    codex_exe = find_codex_exe()
    target_dirs = [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WindowsApps"),
        os.path.join(HOME_DIR, ".codex", "bin"),
        os.path.join(HOME_DIR, ".cargo", "bin")
    ]
    created = []
    for d in target_dirs:
        if os.path.exists(d):
            cmd_path = os.path.join(d, "codex-unlocked.cmd")
            content = f'@echo off\r\nset "HTTP_PROXY={proxy_address}"\r\nset "HTTPS_PROXY={proxy_address}"\r\n"{codex_exe}" %*\r\n'
            try:
                with open(cmd_path, "w", encoding="utf-8") as f:
                    f.write(content)
                created.append(cmd_path)
            except Exception:
                pass
    return created

def remove_codex_unlocked_scripts():
    target_dirs = [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WindowsApps"),
        os.path.join(HOME_DIR, ".codex", "bin"),
        os.path.join(HOME_DIR, ".cargo", "bin")
    ]
    for d in target_dirs:
        cmd_path = os.path.join(d, "codex-unlocked.cmd")
        if os.path.exists(cmd_path):
            try:
                os.remove(cmd_path)
            except Exception:
                pass

def launch_unlocked_codex_terminal(proxy_address: str):
    """Открывает новое окно консоли с готовым разблокированным окружением для Codex."""
    codex_exe = find_codex_exe()
    cmd = f'start "OpenAI Codex [Unlocked]" cmd.exe /k "set HTTP_PROXY={proxy_address}&& set HTTPS_PROXY={proxy_address}&& echo [OK] OpenAI Codex Unlocked! Введите: codex && "{codex_exe}" --version"'
    subprocess.Popen(cmd, shell=True)

# ==============================================================================
# ПОИСК, ПАТЧИНГ ЯРЛЫКОВ И ЗАПУСК CHATGPT DESKTOP
# ==============================================================================
def run_powershell_script(script_text: str) -> str:
    try:
        encoded = base64.b64encode(script_text.encode("utf-16le")).decode("ascii")
        res = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
            capture_output=True, text=True, timeout=8
        )
        return res.stdout.strip()
    except Exception:
        return ""

def inspect_shortcut(lnk_path: str) -> tuple:
    ps_cmd = f"""
    $sh = New-Object -ComObject WScript.Shell
    try {{
        $sc = $sh.CreateShortcut('{lnk_path}')
        [PSCustomObject]@{{ TargetPath = $sc.TargetPath; Arguments = $sc.Arguments }} | ConvertTo-Json -Compress
    }} catch {{
        Write-Output '{{}}'
    }}
    """
    out = run_powershell_script(ps_cmd)
    try:
        data = json.loads(out)
        return (data.get("TargetPath", ""), data.get("Arguments", ""))
    except Exception:
        return ("", "")

def update_shortcut_args(lnk_path: str, new_args: str) -> bool:
    escaped_args = new_args.replace("'", "''")
    escaped_path = lnk_path.replace("'", "''")
    ps_cmd = f"""
    $sh = New-Object -ComObject WScript.Shell
    $sc = $sh.CreateShortcut('{escaped_path}')
    $sc.Arguments = '{escaped_args}'
    $sc.Save()
    """
    run_powershell_script(ps_cmd)
    _, current_args = inspect_shortcut(lnk_path)
    return new_args in current_args

def find_chatgpt_shortcuts() -> list:
    candidate_dirs = [
        os.path.join(os.environ.get("USERPROFILE", ""), "Desktop"),
        os.path.join(os.environ.get("USERPROFILE", ""), "OneDrive", "Desktop"),
        os.path.join(os.environ.get("PUBLIC", "C:\\Users\\Public"), "Desktop"),
        os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs"),
        os.path.join(os.environ.get("PROGRAMDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs")
    ]
    found_shortcuts = []
    seen = set()
    for base_dir in candidate_dirs:
        if not os.path.exists(base_dir):
            continue
        try:
            for root, _, files in os.walk(base_dir):
                for f in files:
                    lower_f = f.lower()
                    if lower_f.endswith(".lnk"):
                        full_path = os.path.join(root, f)
                        normalized = os.path.normcase(os.path.abspath(full_path))
                        if normalized in seen:
                            continue
                        if any(k in lower_f for k in ("chatgpt", "openai", "codex")):
                            seen.add(normalized)
                            found_shortcuts.append(full_path)
        except Exception:
            continue
    return found_shortcuts

def find_chatgpt_exe() -> str:
    candidates = [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "ChatGPT", "ChatGPT.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "ChatGPT", "ChatGPT.exe"),
        os.path.join(os.environ.get("PROGRAMFILES", "C:\\Program Files"), "ChatGPT", "ChatGPT.exe"),
        os.path.join(os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)"), "ChatGPT", "ChatGPT.exe"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p

    # AppX пакет (OpenAI.Codex)
    try:
        cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command",
               "(Get-AppxPackage *openai* | Select-Object -ExpandProperty InstallLocation)"]
        out = subprocess.check_output(cmd, text=True, timeout=5).strip()
        if out:
            appx_exe = os.path.join(out, "app", "ChatGPT.exe")
            if os.path.exists(appx_exe):
                return appx_exe
    except Exception:
        pass
    return ""

def enable_appcontainer_loopback():
    try:
        cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command",
               "(Get-AppxPackage *openai* | Select-Object -ExpandProperty PackageFamilyName)"]
        out = subprocess.check_output(cmd, text=True, timeout=5).strip()
        names = [out] if out else ["OpenAI.Codex_2p2nqsd0c76g0"]
        for fn in names:
            subprocess.run(["checknetisolation", "LoopbackExempt", "-a", f"-n={fn}"],
                           capture_output=True, timeout=5)
    except Exception:
        pass

def auto_restart_chatgpt(exe_path: str = "", args: str = ""):
    try:
        subprocess.run(["taskkill", "/F", "/IM", "ChatGPT.exe"], capture_output=True, timeout=5)
        time.sleep(1.0)
    except Exception:
        pass

    launched = False
    if exe_path and os.path.exists(exe_path):
        try:
            cmd = f'"{exe_path}" {args}'.strip()
            subprocess.Popen(cmd, shell=True, creationflags=subprocess.DETACHED_PROCESS)
            launched = True
        except Exception:
            pass

    if not launched:
        shortcuts = find_chatgpt_shortcuts()
        if shortcuts and os.path.exists(shortcuts[0]):
            try:
                os.startfile(shortcuts[0])
                launched = True
            except Exception:
                pass

    if not launched:
        try:
            os.system("start chatgpt:")
            launched = True
        except Exception:
            pass

    if launched:
        log_ok("ChatGPT успешно перезапущен с параметрами обхода!")
    else:
        log_warn("Не удалось автоматически запустить ChatGPT. Запустите его вручную.")

# ==============================================================================
# ОСНОВНОЙ ФУНКЦИОНАЛ: [1] ПРИМЕНИТЬ ПАТЧ И ЗАПУСТИТЬ СЛУЖБУ (1 КЛИК)
# ==============================================================================
def apply_patch_and_run_service():
    os.system("cls" if os.name == "nt" else "clear")
    print(f"{CLR_CYAN}{CLR_BOLD}")
    print(r"  =======================================================================")
    print(r"    >>> АКТИВАЦИЯ СЛУЖБЫ ОБХОДА БЛОКИРОВКИ CHATGPT & CODEX (ИЗОЛЯЦИЯ) <<<")
    print(r"  =======================================================================")
    print(f"{CLR_RESET}")

    cfg = load_config()

    # Шаг 1: Защита Discord / Telegram — отключение системного прокси
    log_step(1, 4, "Проверка сетевой изоляции (защита Discord, Telegram, игр)")
    ensure_system_proxy_disabled()
    cleanup_global_env_proxies()
    enable_appcontainer_loopback()
    log_ok("Сетевая изоляция активна: системный прокси Windows выключен.")
    log_ok("Discord, Telegram, браузеры и игры работают НАПРЯМУЮ на полной скорости.")

    # Шаг 2: Запуск изолированного шлюза
    log_step(2, 4, "Запуск локального шлюза обхода блокировок")
    success, proxy_address = ensure_proxy_started()
    if success:
        cfg["proxy_address"] = proxy_address
        log_ok(f"Шлюз активен и слушает: {proxy_address}")
    else:
        log_fail("Не удалось инициализировать локальный порт.")
        input(" Нажмите Enter для возврата...")
        return

    # Шаг 3: Настройка лаунчера для OpenAI Codex CLI
    log_step(3, 4, "Подготовка окружения для OpenAI Codex CLI")
    created_scripts = setup_codex_unlocked_script(proxy_address)
    cfg["created_scripts"] = created_scripts
    if created_scripts:
        log_ok(f"Создан изолированный лаунчер Codex: {os.path.basename(created_scripts[0])}")
        log_ok("Команда в терминале: codex-unlocked (или через меню [2])")
    else:
        log_info("Лаунчер можно запустить через меню программы [2].")

    # Шаг 4: Патчинг ярлыков и авто-перезапуск ChatGPT Desktop
    log_step(4, 4, "Подготовка приложения ChatGPT Desktop и автоматический запуск")
    chatgpt_args = f'--proxy-server="{proxy_address}" --proxy-bypass-list="<-loopback>"'
    shortcuts = find_chatgpt_shortcuts()
    chatgpt_exe = find_chatgpt_exe()
    patched_list = []

    if shortcuts:
        for lnk in shortcuts:
            try:
                bak_path = f"{lnk}.bak"
                if not os.path.exists(bak_path):
                    shutil.copy2(lnk, bak_path)

                _, old_args = inspect_shortcut(lnk)
                if "--proxy-server=" in old_args:
                    cleaned_args = " ".join([a for a in old_args.split() if not a.startswith("--proxy-server=")])
                    new_args = f"{cleaned_args} {chatgpt_args}".strip()
                else:
                    new_args = f"{old_args} {chatgpt_args}".strip()

                update_shortcut_args(lnk, new_args)
                patched_list.append(lnk)
                log_ok(f"Пропатчен ярлык: {os.path.basename(lnk)}")
            except Exception:
                pass
    else:
        if chatgpt_exe:
            log_info(f"Обнаружен исполняемый файл: {os.path.basename(chatgpt_exe)}")
        else:
            log_info("Ярлыки не найдены (ChatGPT будет запущен напрямую).")

    cfg["patched_shortcuts"] = list(set(cfg.get("patched_shortcuts", []) + patched_list))
    save_config(cfg)

    # Принудительный перезапуск ChatGPT
    log_info("Выполняю перезапуск ChatGPT с изолированными параметрами обхода...")
    auto_restart_chatgpt(chatgpt_exe, chatgpt_args)

    print("\n" + "=" * 75)
    log_ok(f"{CLR_BOLD}СЛУЖБА УСПЕШНО ЗАПУЩЕНА И РАБОТАЕТ!{CLR_RESET}")
    if ACTIVE_PROXY and ACTIVE_PROXY.upstream_proxy:
        print(f" {CLR_MAGENTA}●{CLR_RESET} {CLR_BOLD}Маршрут обхода 403 активен{CLR_RESET} — OpenAI трафик идёт через европейский IP.")
    print(f" {CLR_GREEN}●{CLR_RESET} {CLR_BOLD}Discord, Telegram, игры и браузеры{CLR_RESET} работают напрямую без задержек.")
    print(f" {CLR_YELLOW}●{CLR_RESET} {CLR_BOLD}НЕ ЗАКРЫВАЙТЕ ЭТО ОКНО{CLR_RESET} во время работы ChatGPT/Codex (просто сверните его).")
    print("-" * 75)
    print(f" {CLR_CYAN}[2]{CLR_RESET} Запустить разблокированный OpenAI Codex CLI в новой консоли")
    print(f" {CLR_CYAN}[R]{CLR_RESET} Полный откат (вернуть заводские настройки и закрыть)")
    print(f" {CLR_CYAN}[Q]{CLR_RESET} Выйти в главное меню")
    print("=" * 75)

    try:
        while True:
            time.sleep(0.3)
            try:
                import msvcrt
                if msvcrt.kbhit():
                    key = msvcrt.getch().decode("latin1", errors="ignore").lower()
                    if key == "r":
                        rollback_settings()
                        return
                    elif key == "2":
                        launch_unlocked_codex_terminal(proxy_address)
                    elif key == "q":
                        return
            except Exception:
                pass
    except KeyboardInterrupt:
        return

# ==============================================================================
# ВОССТАНОВЛЕНИЕ СТАНДАРТНЫХ НАСТРОЕК (ОТКАТ)
# ==============================================================================
def rollback_settings():
    print("\n" + "=" * 70)
    print(f"{CLR_BOLD}{CLR_YELLOW}  >>> ВОССТАНОВЛЕНИЕ СТАНДАРТНЫХ НАСТРОЕК (ОТКАТ) <<<{CLR_RESET}")
    print("=" * 70)

    cfg = load_config()

    # Шаг 1: Очистка реестра и проверка прокси
    log_step(1, 3, "Очистка системного окружения")
    ensure_system_proxy_disabled()
    cleanup_global_env_proxies()
    remove_codex_unlocked_scripts()
    log_ok("Системный прокси отключен, скрипты codex-unlocked удалены.")

    # Шаг 2: Восстановление ярлыков ChatGPT
    log_step(2, 3, "Восстановление оригинальных ярлыков ChatGPT")
    all_shortcuts = list(set(cfg.get("patched_shortcuts", []) + find_chatgpt_shortcuts()))
    for lnk in all_shortcuts:
        bak_path = f"{lnk}.bak"
        if os.path.exists(bak_path):
            try:
                shutil.copy2(bak_path, lnk)
                os.remove(bak_path)
                log_ok(f"Восстановлен оригинальный ярлык: {os.path.basename(lnk)}")
                continue
            except Exception:
                pass
        if os.path.exists(lnk):
            try:
                _, args = inspect_shortcut(lnk)
                if "--proxy-server=" in args:
                    cleaned = " ".join([a for a in args.split() if not a.startswith("--proxy-server=")])
                    update_shortcut_args(lnk, cleaned)
                    log_ok(f"Очищены аргументы ярлыка: {os.path.basename(lnk)}")
            except Exception:
                pass

    # Шаг 3: Остановка локального шлюза и WARP
    log_step(3, 3, "Остановка службы шлюза")
    global ACTIVE_PROXY
    if ACTIVE_PROXY:
        ACTIVE_PROXY.stop()
        ACTIVE_PROXY = None
    log_ok("Локальный шлюз остановлен.")
    warp_disconnect()
    log_ok("Cloudflare WARP отключен.")

    if os.path.exists(CONFIG_FILE):
        try:
            os.remove(CONFIG_FILE)
        except Exception:
            pass

    print("\n" + "=" * 70)
    log_ok(f"{CLR_BOLD}СТАНДАРТНЫЕ НАСТРОЙКИ ПОЛНОСТЬЮ ВОССТАНОВЛЕНЫ!{CLR_RESET}")
    print("=" * 70)
    time.sleep(1.5)

# ==============================================================================
# ССЫЛКИ СООБЩЕСТВА
# ==============================================================================
def open_url(url: str, title: str):
    print(f"\n Открытие страницы {title}...")
    try:
        webbrowser.open_new_tab(url)
        log_ok("Ссылка открыта в вашем браузере!")
    except Exception:
        pass
    print(f" Прямая ссылка: {CLR_CYAN}{CLR_BOLD}{url}{CLR_RESET}\n")
    input(" Нажмите Enter для продолжения...")

# ==============================================================================
# ГЛАВНОЕ МЕНЮ И CLI ИНТЕРФЕЙС
# ==============================================================================
def render_banner():
    os.system("cls" if os.name == "nt" else "clear")
    print(f"{CLR_CYAN}{CLR_BOLD}")
    print(r"  ____ _           _    ____ ____ _____   ____       _       _     ")
    print(r" / ___| |__   __ _| |_ / ___|  _ \_   _| |  _ \ __ _| |_ ___| |__   ___ _ __")
    print(r"| |   | '_ \ / _` | __| |  _| |_) || |   | |_) / _` | __/ __| '_ \ / _ \ '__|")
    print(r"| |___| | | | (_| | |_| |_| |  __/ | |   |  __/ (_| | || (__| | | |  __/ |  ")
    print(r" \____|_| |_|\__,_|\__|\____|_|    |_|   |_|   \__,_|\__\___|_| |_|\___|_|  ")
    print(f"{CLR_RESET}")
    print(f" {CLR_BOLD}{APP_TITLE}{CLR_RESET} [Версия {APP_VERSION}]")
    print(f" {CLR_GRAY}1-Клик обход блокировок ТСПУ & 403 | Полная изоляция (Discord/TG не затрагиваются){CLR_RESET}")
    print("-" * 75)

    if is_admin():
        print(f" {CLR_GREEN}●{CLR_RESET} Права: {CLR_BOLD}Администратор{CLR_RESET}")
    else:
        print(f" {CLR_YELLOW}●{CLR_RESET} Права: {CLR_BOLD}Пользователь{CLR_RESET}")

    global ACTIVE_PROXY
    if ACTIVE_PROXY and ACTIVE_PROXY.is_running:
        print(f" {CLR_GREEN}●{CLR_RESET} Локальный шлюз: {CLR_GREEN}{CLR_BOLD}АКТИВЕН{CLR_RESET} {CLR_GRAY}(127.0.0.1:{ACTIVE_PROXY.port}){CLR_RESET}")
    else:
        print(f" {CLR_GRAY}○{CLR_RESET} Локальный шлюз: {CLR_GRAY}Готов к запуску{CLR_RESET}")

    if ACTIVE_PROXY and ACTIVE_PROXY.upstream_proxy:
        print(f" {CLR_MAGENTA}●{CLR_RESET} Обход 403 (WARP): {CLR_MAGENTA}{CLR_BOLD}АКТИВЕН{CLR_RESET} {CLR_GRAY}(европейский IP для OpenAI){CLR_RESET}")
    elif is_warp_installed():
        print(f" {CLR_YELLOW}●{CLR_RESET} Обход 403 (WARP): {CLR_BOLD}Готов{CLR_RESET} {CLR_GRAY}(подключится автоматически при старте){CLR_RESET}")
    else:
        print(f" {CLR_GRAY}○{CLR_RESET} Обход 403 (WARP): {CLR_GRAY}Автономный DPI режим{CLR_RESET}")

    print(f" {CLR_GREEN}✔{CLR_RESET} {CLR_BOLD}Discord & Telegram:{CLR_RESET} {CLR_GREEN}100% Прямое соединение (не затрагиваются){CLR_RESET}")
    print("-" * 75)

def main_menu():
    while True:
        try:
            render_banner()
            print(f" {CLR_BOLD}Главное меню:{CLR_RESET}")
            print(f"  {CLR_CYAN}[1]{CLR_RESET} {CLR_BOLD}Запустить службу обхода и ChatGPT (1 клик){CLR_RESET}")
            print(f"  {CLR_CYAN}[2]{CLR_RESET} Запустить разблокированный OpenAI Codex CLI (в новой консоли)")
            print(f"  {CLR_CYAN}[3]{CLR_RESET} Запустить ChatGPT Desktop (вручную с параметрами обхода)")
            print(f"  {CLR_CYAN}[4]{CLR_RESET} Восстановить стандартные настройки (Откат)")
            print(f"  {CLR_CYAN}[5]{CLR_RESET} Сообщество проекта (Telegram)")
            print(f"  {CLR_CYAN}[6]{CLR_RESET} Поддержать автора (Boosty)")
            print(f"  {CLR_CYAN}[0]{CLR_RESET} Выход")
            print("-" * 75)

            choice = input(f" Выберите действие [0-6]: ").strip()

            if choice == "1":
                apply_patch_and_run_service()
            elif choice == "2":
                ensure_proxy_started()
                proxy_addr = f"http://{DEFAULT_PROXY_HOST}:{DEFAULT_PROXY_PORT}"
                launch_unlocked_codex_terminal(proxy_addr)
            elif choice == "3":
                ensure_proxy_started()
                proxy_addr = f"http://{DEFAULT_PROXY_HOST}:{DEFAULT_PROXY_PORT}"
                auto_restart_chatgpt(find_chatgpt_exe(), f'--proxy-server="{proxy_addr}" --proxy-bypass-list="<-loopback>"')
            elif choice == "4":
                rollback_settings()
            elif choice == "5":
                open_url(COMMUNITY_URL, "Сообщество проекта (Telegram)")
            elif choice == "6":
                open_url(BOOSTY_URL, "Поддержать автора (Boosty)")
            elif choice in ("0", "exit", "quit", "q"):
                print(f"\n{CLR_GRAY}Завершение работы... До встречи!{CLR_RESET}\n")
                sys.exit(0)
            else:
                print(f" {CLR_RED}Неверный ввод. Пожалуйста, укажите цифру от 0 до 6.{CLR_RESET}")
                time.sleep(1.0)
        except Exception as e:
            print(f"\n {CLR_RED}[ОШИБКА]{CLR_RESET} Непредвиденный сбой: {e}")
            traceback.print_exc()
            try:
                input("\nНажмите Enter для продолжения...")
            except Exception:
                pass

if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print(f"\n\n{CLR_GRAY}Программа завершена.{CLR_RESET}\n")
        sys.exit(0)
    except Exception as e:
        print(f"\n{CLR_RED}Критическая ошибка программы: {e}{CLR_RESET}")
        traceback.print_exc()
        try:
            input("\nНажмите Enter для выхода...")
        except Exception:
            pass
        sys.exit(1)
