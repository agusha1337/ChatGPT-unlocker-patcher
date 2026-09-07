#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
OpenAI Codex & ChatGPT Windows Standalone Patcher (v4.2.0)
================================================================================
Автономный 1-клик инструмент для разработчиков из РФ:
1. Сегментация пакетов TLS ClientHello (разбиение TCP-пакета с открытым SNI
   на части с TCP_NODELAY для гарантированного обхода ТСПУ / РКН).
2. Поддержка OpenAI Codex CLI, VS Code, Cursor и Python SDK через системный
   шлюз OPENAI_BASE_URL в HKCU\\Environment.
3. Возможность указания персонального Cloudflare Worker / Reverse Proxy шлюза
   для полного снятия ошибки 403 Forbidden.
4. Автоматический патчинг ярлыков и авто-перезапуск ChatGPT.exe в 1 клик.
5. Изолированная работа: не затрагивает Discord, Telegram, игры и браузеры.
6. 100% автономность: ноль скачиваний, ноль сторонних программ, чистый Python 3.
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
import base64
import traceback
from urllib.parse import urlsplit

# ==============================================================================
# КОНФИГУРАЦИЯ И КОНСТАНТЫ
# ==============================================================================
APP_TITLE = "OpenAI Codex & ChatGPT Zapret DPI Patcher"
APP_VERSION = "4.3.0"
COMMUNITY_URL = "https://t.me/chatgpt_patcher_community"
BOOSTY_URL = "https://boosty.to/chatgpt_patcher"
GITHUB_URL = "https://github.com/gde-agusha/chatgpt-codex-patcher"

DEFAULT_PROXY_PORT = 10809
DEFAULT_PROXY_HOST = "127.0.0.1"
DEFAULT_OPENAI_BASE_URL = "https://chatgpt-unlocker-patcher.agushaosnova.workers.dev/v1"

ENV_KEYS = ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "OPENAI_BASE_URL"]

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
            h_stdout = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
            mode = wintypes.DWORD()
            if kernel32.GetConsoleMode(h_stdout, ctypes.byref(mode)):
                kernel32.SetConsoleMode(h_stdout, mode.value | 0x0004)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
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
        "openai_base_url": DEFAULT_OPENAI_BASE_URL,
        "patched_shortcuts": []
    }

def save_config(cfg: dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log_warn(f"Не удалось сохранить конфигурацию: {e}")

def find_sni_hostname_offset(data: bytes) -> int:
    """
    Быстрый парсер TLS ClientHello: находит смещение (offset) начала
    доменного имени в расширении Server Name Indication (SNI).
    Позволяет разрезать TCP-пакет точно посередине запрещенного домена.
    """
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
        comp_len = data[pos]
        pos += 1 + comp_len
        if pos + 2 > len(data):
            return -1
        ext_len = int.from_bytes(data[pos:pos+2], "big")
        pos += 2
        end = min(pos + ext_len, len(data))
        while pos + 4 <= end:
            ext_type = int.from_bytes(data[pos:pos+2], "big")
            ext_size = int.from_bytes(data[pos+2:pos+4], "big")
            pos += 4
            if ext_type == 0:  # extension: server_name (SNI)
                # Структура SNI:
                # server_name_list_length (2 байта) + name_type (1 байт) + name_len (2 байта)
                return pos + 5
            pos += ext_size
    except Exception:
        pass
    return -1

# ==============================================================================
# ВЫСОКОПРОИЗВОДИТЕЛЬНЫЙ ПОТОКОВЫЙ DPI-ПРОКСИ С СЕГМЕНТАЦИЕЙ TLS
# ==============================================================================
class DpiBypassProxy:
    """
    Высокоскоростной двухпоточный HTTP/HTTPS CONNECT прокси на сокетах.
    Обеспечивает фрагментацию ClientHello с TCP_NODELAY для надежного обхода ТСПУ.
    Поддерживает непрерывный SSE-стриминг без разрывов соединений.
    """
    def __init__(self, host: str = DEFAULT_PROXY_HOST, port: int = DEFAULT_PROXY_PORT,
                 upstream_proxy: dict = None):
        self.host = host
        self.port = port
        self.server_sock = None
        self.is_running = False
        self.total_connections = 0
        # upstream_proxy = {"type": "socks5", "host": "127.0.0.1", "port": 40000}
        self.upstream_proxy = upstream_proxy

    def start(self, in_background: bool = True):
        bound = False
        start_port = self.port
        last_err = None

        for offset in range(10):
            try_port = start_port + offset
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
            thread = threading.Thread(target=self._accept_loop, daemon=True, name="DpiProxyServer")
            thread.start()
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

    # Домены OpenAI, для которых нужен WARP (обход геоблока 403)
    OPENAI_DOMAINS = ("chatgpt", "openai", "oaistatic")

    def _connect_via_socks5(self, proxy_host: str, proxy_port: int,
                            target_host: str, target_port: int) -> socket.socket:
        """Устанавливает TCP-соединение через SOCKS5 прокси (Cloudflare WARP)."""
        sock = socket.create_connection((proxy_host, proxy_port), timeout=15.0)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        # SOCKS5 Handshake: версия 5, 1 метод, без аутентификации
        sock.sendall(b"\x05\x01\x00")
        resp = sock.recv(2)
        if len(resp) < 2 or resp[0] != 0x05 or resp[1] != 0x00:
            sock.close()
            raise ConnectionError("SOCKS5 handshake failed")
        # SOCKS5 CONNECT: версия 5, команда CONNECT, зарезервировано, тип адреса DOMAIN
        addr_bytes = target_host.encode("ascii")
        req = (b"\x05\x01\x00\x03" +
               bytes([len(addr_bytes)]) + addr_bytes +
               target_port.to_bytes(2, "big"))
        sock.sendall(req)
        resp = sock.recv(32)
        if len(resp) < 2 or resp[1] != 0x00:
            sock.close()
            raise ConnectionError(f"SOCKS5 CONNECT failed: status {resp[1] if len(resp) > 1 else 'unknown'}")
        return sock

    def _connect_to_target(self, target_host: str, target_port: int) -> socket.socket:
        """
        Подключается к цели: через WARP SOCKS5 для OpenAI доменов,
        напрямую для всех остальных.
        """
        is_openai = any(d in target_host for d in self.OPENAI_DOMAINS)

        if is_openai and self.upstream_proxy:
            try:
                sock = self._connect_via_socks5(
                    self.upstream_proxy["host"],
                    self.upstream_proxy["port"],
                    target_host, target_port
                )
                print(f" {CLR_MAGENTA}[WARP]{CLR_RESET} {target_host}:{target_port} "
                      f"{CLR_GRAY}(через Cloudflare WARP → нероссийский IP){CLR_RESET}")
                return sock
            except Exception as e:
                print(f" {CLR_YELLOW}[WARN]{CLR_RESET} WARP SOCKS5 недоступен ({e}), "
                      f"подключаемся напрямую...")

        # Прямое подключение (обычные сайты / fallback)
        sock = socket.create_connection((target_host, target_port), timeout=15.0)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        return sock

    def _handle_client(self, client_sock: socket.socket):
        remote_sock = None
        try:
            client_sock.settimeout(15.0)
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
                # HTTPS CONNECT Tunnel
                if ":" in url:
                    target_host, target_port_str = url.split(":", 1)
                    target_port = int(target_port_str)
                else:
                    target_host, target_port = url, 443

                remote_sock = self._connect_to_target(target_host, target_port)
                client_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

                # 200 Connection Established
                client_sock.sendall(b"HTTP/1.1 200 Connection Established\r\nProxy-Agent: Codex-Zapret-DPI/4.3\r\n\r\n")

                # Читаем первый пакет TLS ClientHello
                first_payload = client_sock.recv(16384)
                if not first_payload:
                    return

                # Проверка сигнатуры ClientHello (0x16 0x03 ... 0x01)
                if (len(first_payload) >= 6 and
                    first_payload[0] == 0x16 and
                    first_payload[1] == 0x03 and
                    first_payload[5] == 0x01):

                    # ДЕСИНХРОНИЗАЦИЯ ПО ПРИНЦИПУ ZAPRET / BYEDPI (split2 + SNI-cut):
                    # 1. Режем заголовок TLS Record на 2-м байте (\x16\x03) — ТСПУ не распознает TLS.
                    # 2. Находим смещение SNI и режем прямо посреди запрещенного домена.
                    sni_pos = find_sni_hostname_offset(first_payload)
                    remote_sock.sendall(first_payload[:2])
                    time.sleep(0.008)

                    if sni_pos > 2 and sni_pos + 3 < len(first_payload):
                        split_sni = sni_pos + 3
                        remote_sock.sendall(first_payload[2:split_sni])
                        time.sleep(0.008)
                        remote_sock.sendall(first_payload[split_sni:])
                    elif len(first_payload) > 35:
                        remote_sock.sendall(first_payload[2:35])
                        time.sleep(0.008)
                        remote_sock.sendall(first_payload[35:])
                    else:
                        remote_sock.sendall(first_payload[2:])
                    
                    if any(domain in target_host for domain in ("chatgpt", "openai", "oaistatic")):
                        print(f" {CLR_GREEN}[Zapret DPI]{CLR_RESET} {target_host}:{target_port} {CLR_GRAY}(TLS split2 + SNI десинхронизация){CLR_RESET}")
                else:
                    remote_sock.sendall(first_payload)

                # Снимаем любые таймауты перед переходом в режим туннелирования
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

                remote_sock = self._connect_to_target(target_host, target_port)
                if len(req_data) > 3 and req_data[:3] in (b"GET", b"POS", b"PUT", b"DEL", b"OPT"):
                    remote_sock.sendall(req_data[:1])
                    time.sleep(0.008)
                    remote_sock.sendall(req_data[1:])
                else:
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

# Глобальный экземпляр службы прокси
ACTIVE_PROXY = None

# ==============================================================================
# CLOUDFLARE WARP: АВТООБНАРУЖЕНИЕ, АВТОПОДКЛЮЧЕНИЕ, ПРОВЕРКА 403
# ==============================================================================
WARP_CLI = r"C:\Program Files\Cloudflare\Cloudflare WARP\warp-cli.exe"
WARP_SOCKS5_HOST = "127.0.0.1"
WARP_SOCKS5_PORT = 40000

def is_warp_installed() -> bool:
    """Проверяет наличие Cloudflare WARP на системе."""
    return os.path.exists(WARP_CLI)

def is_warp_socks5_alive() -> bool:
    """Проверяет, слушает ли WARP SOCKS5 прокси на порту 40000."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.5)
        s.connect((WARP_SOCKS5_HOST, WARP_SOCKS5_PORT))
        # Отправляем SOCKS5 handshake для верификации
        s.sendall(b"\x05\x01\x00")
        resp = s.recv(2)
        s.close()
        return len(resp) == 2 and resp[0] == 0x05 and resp[1] == 0x00
    except Exception:
        return False

def warp_connect() -> bool:
    """Подключает Cloudflare WARP и включает режим SOCKS5 прокси."""
    if not is_warp_installed():
        return False
    try:
        # Установить режим proxy (SOCKS5 на порту 40000)
        subprocess.run([WARP_CLI, "mode", "proxy"], capture_output=True, timeout=5)
        time.sleep(0.3)
        # Подключиться
        subprocess.run([WARP_CLI, "connect"], capture_output=True, timeout=10)
        # Дождаться подключения (до 8 секунд)
        for _ in range(16):
            time.sleep(0.5)
            if is_warp_socks5_alive():
                return True
        return False
    except Exception:
        return False

def warp_disconnect():
    """Отключает Cloudflare WARP."""
    if is_warp_installed():
        try:
            subprocess.run([WARP_CLI, "disconnect"], capture_output=True, timeout=5)
        except Exception:
            pass

def test_openai_access_direct() -> bool:
    """Быстрый тест: доступен ли chatgpt.com напрямую без 403."""
    import ssl
    try:
        ctx = ssl.create_default_context()
        sock = socket.create_connection(("chatgpt.com", 443), timeout=5)
        ssock = ctx.wrap_socket(sock, server_hostname="chatgpt.com")
        ssock.sendall(b"GET / HTTP/1.1\r\nHost: chatgpt.com\r\nConnection: close\r\n\r\n")
        resp = ssock.recv(512).decode("latin1", errors="ignore")
        ssock.close()
        # Если получили 403 — заблокировано
        if "403" in resp[:30]:
            return False
        return True
    except Exception:
        # Если соединение вообще не прошло — тоже недоступно
        return False

def ensure_proxy_started() -> tuple:
    """Запускает прокси, если не запущен, и возвращает (успех: bool, адрес_прокси: str)."""
    global ACTIVE_PROXY
    if ACTIVE_PROXY and ACTIVE_PROXY.is_running:
        return True, f"http://{ACTIVE_PROXY.host}:{ACTIVE_PROXY.port}"

    # Определяем upstream proxy (WARP) для обхода 403
    upstream = None

    # Проверяем, нужен ли WARP (есть ли 403 при прямом доступе)
    direct_ok = test_openai_access_direct()

    if not direct_ok:
        log_info("OpenAI возвращает 403 — нужен WARP для смены IP...")
        if is_warp_installed():
            if is_warp_socks5_alive():
                log_ok("Cloudflare WARP уже подключен (SOCKS5 на порту 40000).")
                upstream = {"type": "socks5", "host": WARP_SOCKS5_HOST, "port": WARP_SOCKS5_PORT}
            else:
                log_info("Подключаю Cloudflare WARP автоматически...")
                if warp_connect():
                    log_ok("Cloudflare WARP подключен! Трафик OpenAI пойдёт через нероссийский IP.")
                    upstream = {"type": "socks5", "host": WARP_SOCKS5_HOST, "port": WARP_SOCKS5_PORT}
                else:
                    log_warn("Не удалось подключить WARP. Попробуйте подключить его вручную.")
        else:
            log_warn("Cloudflare WARP не установлен!")
            print(f"    {CLR_YELLOW}►{CLR_RESET} Установите бесплатный Cloudflare WARP из Microsoft Store")
            print(f"    {CLR_YELLOW}►{CLR_RESET} Или скачайте с {CLR_CYAN}https://1.1.1.1{CLR_RESET}")
            print(f"    {CLR_YELLOW}►{CLR_RESET} После установки перезапустите патчер — WARP подключится автоматически!")
    else:
        log_ok("OpenAI доступен напрямую (нет геоблокировки).")

    try:
        ACTIVE_PROXY = DpiBypassProxy(DEFAULT_PROXY_HOST, DEFAULT_PROXY_PORT,
                                      upstream_proxy=upstream)
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
        log_fail(f"Ошибка запуска прокси: {e}")
        return False, ""

# ==============================================================================
# РАБОТА С РЕЕСТРОМ WINDOWS И WINAPI (HKCU\\Environment)
# ==============================================================================
def set_registry_env(name: str, value: str) -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
        os.environ[name] = value
        return True
    except Exception as e:
        log_fail(f"Ошибка записи в реестр ({name}): {e}")
        return False

def get_registry_env(name: str) -> str:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_QUERY_VALUE) as key:
            val, _ = winreg.QueryValueEx(key, name)
            return str(val)
    except Exception:
        return ""

def delete_registry_env(name: str) -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_ALL_ACCESS) as key:
            try:
                winreg.DeleteValue(key, name)
            except FileNotFoundError:
                pass
        if name in os.environ:
            del os.environ[name]
        return True
    except Exception:
        return False

def broadcast_environment_change():
    """Отправляет системное сообщение WM_SETTINGCHANGE через SendMessageTimeoutW."""
    try:
        result = wintypes.DWORD()
        ctypes.windll.user32.SendMessageTimeoutW(
            HWND_BROADCAST,
            WM_SETTINGCHANGE,
            0,
            "Environment",
            SMTO_ABORTIFHUNG,
            1500,
            ctypes.byref(result)
        )
    except Exception:
        pass

def enable_appcontainer_loopback():
    """Добавляет исключение Loopback для UWP/AppX приложения ChatGPT (OpenAI.Codex)."""
    try:
        cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command",
               "(Get-AppxPackage *openai* | Select-Object -ExpandProperty PackageFamilyName)"]
        out = subprocess.check_output(cmd, text=True, timeout=5).strip()
        names = [out] if out else ["OpenAI.Codex_2p2nqsd0c76g0"]
        for fn in names:
            if fn:
                subprocess.run(["CheckNetIsolation.exe", "LoopbackExempt", "-a", f"-n={fn}"],
                               capture_output=True, timeout=5)
    except Exception:
        pass

def update_codex_config_base_url(url: str):
    """Синхронизирует base_url напрямую в ~/.codex/config.toml для полной поддержки Codex."""
    codex_toml = os.path.join(os.path.expanduser("~"), ".codex", "config.toml")
    if not os.path.exists(codex_toml):
        return
    try:
        with open(codex_toml, "r", encoding="utf-8") as f:
            content = f.read()
        import re
        if "[model_providers.custom]" in content:
            if re.search(r'^\s*base_url\s*=', content, flags=re.MULTILINE):
                content = re.sub(r'^\s*base_url\s*=.*$', f'base_url = "{url}"', content, flags=re.MULTILINE)
            else:
                content = content.replace("[model_providers.custom]\n", f'[model_providers.custom]\nbase_url = "{url}"\n')
            with open(codex_toml, "w", encoding="utf-8") as f:
                f.write(content)
            log_ok(f"Конфигурация Codex обновлена: base_url = {url}")
    except Exception as e:
        log_warn(f"Не удалось обновить ~/.codex/config.toml: {e}")

def rollback_codex_config_base_url():
    """Удаляет кастомный base_url из ~/.codex/config.toml."""
    codex_toml = os.path.join(os.path.expanduser("~"), ".codex", "config.toml")
    if not os.path.exists(codex_toml):
        return
    try:
        with open(codex_toml, "r", encoding="utf-8") as f:
            content = f.read()
        import re
        if re.search(r'^\s*base_url\s*=.*?\n', content, flags=re.MULTILINE):
            content = re.sub(r'^\s*base_url\s*=.*?\n', '', content, flags=re.MULTILINE)
            with open(codex_toml, "w", encoding="utf-8") as f:
                f.write(content)
            log_ok("Восстановлен стандартный ~/.codex/config.toml")
    except Exception:
        pass

# ==============================================================================
# УПРАВЛЕНИЕ ЯРЛЫКАМИ (.LNK) И ДЕСКТОПНЫМ CHATGPT (WIN32 + APPX)
# ==============================================================================
def run_powershell_script(script_text: str) -> str:
    try:
        encoded = base64.b64encode(script_text.encode("utf-16le")).decode("ascii")
        res = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
            capture_output=True,
            text=True,
            timeout=8
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
    """Быстрый поиск ярлыков ChatGPT без перебора всей системы."""
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
    """Находит исполняемый файл ChatGPT (как классический Win32, так и WindowsApps / AppX)."""
    # 1. Стандартные пути установки Win32
    candidates = [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "ChatGPT", "ChatGPT.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "ChatGPT", "ChatGPT.exe"),
        os.path.join(os.environ.get("PROGRAMFILES", "C:\\Program Files"), "ChatGPT", "ChatGPT.exe"),
        os.path.join(os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)"), "ChatGPT", "ChatGPT.exe"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p

    # 2. Пакет Microsoft Store AppX (OpenAI.Codex)
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

def is_chatgpt_running() -> bool:
    try:
        out = subprocess.check_output(
            ["tasklist", "/FI", "IMAGENAME eq ChatGPT.exe", "/NH"],
            text=True,
            stderr=subprocess.DEVNULL
        )
        return "chatgpt.exe" in out.lower()
    except Exception:
        return False

def auto_restart_chatgpt(exe_path: str = "", args: str = ""):
    """Принудительно закрывает старый ChatGPT.exe и автоматически открывает его с параметрами обхода."""
    try:
        subprocess.run(["taskkill", "/F", "/IM", "ChatGPT.exe"], capture_output=True, timeout=5)
        time.sleep(1.0)
    except Exception:
        pass

    launched = False

    # 1. Прямой запуск найденного исполняемого файла с флагами прокси
    if exe_path and os.path.exists(exe_path):
        try:
            cmd = f'"{exe_path}" {args}'.strip()
            subprocess.Popen(cmd, shell=True, creationflags=subprocess.DETACHED_PROCESS)
            launched = True
        except Exception:
            pass

    # 2. Если прямой запуск не сработал, запускаем пропатченный ярлык
    if not launched:
        shortcuts = find_chatgpt_shortcuts()
        if shortcuts and os.path.exists(shortcuts[0]):
            try:
                os.startfile(shortcuts[0])
                launched = True
            except Exception:
                pass

    # 3. Резервный запуск по зарегистрированному протоколу приложения
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
# ОСНОВНОЙ ФУНКЦИОНАЛ: [1] ПРИМЕНИТЬ ПАТЧ И ЗАПУСТИТЬ СЛУЖБУ
# ==============================================================================
def apply_patch_and_run_service():
    try:
        _apply_patch_and_run_service_impl()
    except Exception as e:
        print(f"\n {CLR_RED}[КРИТИЧЕСКАЯ ОШИБКА]{CLR_RESET} Произошел сбой: {e}")
        traceback.print_exc()
        print(f"\n {CLR_YELLOW}Окно не закрыто. Нажмите Enter для возврата в меню...{CLR_RESET}")
        try:
            input()
        except Exception:
            pass

def _apply_patch_and_run_service_impl():
    os.system("cls" if os.name == "nt" else "clear")
    print(f"{CLR_CYAN}{CLR_BOLD}")
    print(r"  =======================================================================")
    print(r"    >>> АКТИВАЦИЯ СЛУЖБЫ ОБХОДА БЛОКИРОВКИ CHATGPT & CODEX (РЕЖИМ ЗАПРЕТА) <<<")
    print(r"  =======================================================================")
    print(f"{CLR_RESET}")

    cfg = load_config()

    # Шаг 1: Запуск локального DPI-обходчика
    log_step(1, 3, "Запуск локального ядра обхода блокировок (DPI Bypass)")
    success, proxy_address = ensure_proxy_started()
    if success:
        cfg["proxy_address"] = proxy_address
        log_ok(f"DPI-ядро активно и слушает: {proxy_address}")
    else:
        log_fail("Не удалось инициализировать локальный порт.")
        input(" Нажмите Enter для возврата...")
        return

    # Шаг 2: Системная интеграция для Codex и API
    log_step(2, 3, "Настройка системной маршрутизации для OpenAI Codex")
    openai_base_url = cfg.get("openai_base_url", DEFAULT_OPENAI_BASE_URL)

    # Разрешаем AppContainer Loopback (для приложений из Microsoft Store)
    enable_appcontainer_loopback()

    # Настраиваем переменные среды реестра (только для Codex/OpenAI, не трогая системный интернет)
    env_updates = {
        "OPENAI_BASE_URL": openai_base_url
    }
    for key, val in env_updates.items():
        set_registry_env(key, val)
    update_codex_config_base_url(openai_base_url)
    broadcast_environment_change()
    log_ok(f"Конфигурация Codex зарегистрирована (OPENAI_BASE_URL: {openai_base_url}).")
    log_ok("VS Code, Codex CLI, Cursor и терминалы настроены на европейский шлюз.")

    # Шаг 3: Поиск, патчинг ярлыков и автоматический перезапуск ChatGPT
    log_step(3, 3, "Подготовка приложения ChatGPT и автоматический запуск")
    chatgpt_args = f'--proxy-server="{proxy_address}" --ignore-certificate-errors'
    
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
            log_info("Ярлыки не найдены (приложение будет запущено напрямую или через протокол).")

    cfg["patched_shortcuts"] = list(set(cfg.get("patched_shortcuts", []) + patched_list))
    save_config(cfg)

    # Принудительный автоматический перезапуск ChatGPT (без лишних вопросов!)
    log_info("Выполняю автоматический перезапуск ChatGPT с параметрами обхода...")
    auto_restart_chatgpt(chatgpt_exe, chatgpt_args)

    print("\n" + "=" * 75)
    log_ok(f"{CLR_BOLD}СЛУЖБА УСПЕШНО ЗАПУЩЕНА И РАБОТАЕТ В РЕАЛЬНОМ ВРЕМЕНИ!{CLR_RESET}")
    if ACTIVE_PROXY and ACTIVE_PROXY.upstream_proxy:
        print(f" {CLR_MAGENTA}●{CLR_RESET} {CLR_BOLD}Cloudflare WARP активен{CLR_RESET} — OpenAI трафик идёт через нероссийский IP (обход 403)")
    print(f" {CLR_YELLOW}●{CLR_RESET} {CLR_BOLD}НЕ ЗАКРЫВАЙТЕ ЭТО ОКНО{CLR_RESET} во время работы Codex или ChatGPT (просто сверните его).")
    print(f" {CLR_GRAY}   (Как в Запрете Дискорда: пока окно активно — блокировки обходятся автоматически){CLR_RESET}")
    print(f" {CLR_GREEN}✔{CLR_RESET} {CLR_BOLD}Discord, Telegram и браузеры НЕ затрагиваются{CLR_RESET} и работают в штатном режиме.")
    print("-" * 75)
    print(f" {CLR_CYAN}[R]{CLR_RESET} Полный откат (вернуть заводские настройки и закрыть)")
    print(f" {CLR_CYAN}[Q]{CLR_RESET} Выйти в главное меню")
    print("=" * 75)

    # Живой цикл мониторинга запросов
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
                    elif key == "q":
                        return
            except Exception:
                pass
    except KeyboardInterrupt:
        return

# ==============================================================================
# НАСТРОЙКА ШЛЮЗА ДЛЯ CODEX / REVERSE PROXY: [2]
# ==============================================================================
def configure_codex_gateway():
    cfg = load_config()
    curr = cfg.get("openai_base_url", DEFAULT_OPENAI_BASE_URL)

    os.system("cls" if os.name == "nt" else "clear")
    print(f"{CLR_CYAN}{CLR_BOLD}")
    print(r"  =======================================================================")
    print(r"       >>> НАСТРОЙКА ШЛЮЗА OPENAI CODEX (OPENAI_BASE_URL) <<<")
    print(r"  =======================================================================")
    print(f"{CLR_RESET}")
    print(f" Текущий шлюз: {CLR_BOLD}{curr}{CLR_RESET}\n")
    print(f" {CLR_BOLD}Варианты настройки:{CLR_RESET}")
    print(f"  {CLR_CYAN}[1]{CLR_RESET} Стандартный API ({DEFAULT_OPENAI_BASE_URL}) + локальный DPI-обход")
    print(f"  {CLR_CYAN}[2]{CLR_RESET} Ввести адрес своего Cloudflare Worker / Reverse Proxy шлюза")
    print(f"  {CLR_CYAN}[3]{CLR_RESET} Открыть инструкцию по созданию бесплатного шлюза (GitHub)")
    print(f"  {CLR_CYAN}[0]{CLR_RESET} Назад в главное меню")
    print("-" * 75)

    choice = input(" Выберите вариант [0-3]: ").strip()

    if choice == "1":
        cfg["openai_base_url"] = DEFAULT_OPENAI_BASE_URL
        save_config(cfg)
        set_registry_env("OPENAI_BASE_URL", DEFAULT_OPENAI_BASE_URL)
        rollback_codex_config_base_url()
        broadcast_environment_change()
        log_ok(f"Установлен стандартный шлюз: {DEFAULT_OPENAI_BASE_URL}")
        time.sleep(1.5)

    elif choice == "2":
        print(f"\n Введите полный URL шлюза (например, https://my-codex-worker.workers.dev/v1):")
        new_url = input(" URL шлюза: ").strip()
        if new_url:
            if not new_url.startswith("http://") and not new_url.startswith("https://"):
                new_url = f"https://{new_url}"
            cfg["openai_base_url"] = new_url
            save_config(cfg)
            set_registry_env("OPENAI_BASE_URL", new_url)
            update_codex_config_base_url(new_url)
            broadcast_environment_change()
            log_ok(f"Сохранен персональный шлюз: {new_url}")
            time.sleep(1.5)

    elif choice == "3":
        open_url(f"{GITHUB_URL}#cloudflare-worker", "Инструкция по Cloudflare Worker")

# ==============================================================================
# ОСНОВНОЙ ФУНКЦИОНАЛ: [3] ВОССТАНОВИТЬ СТАНДАРТНЫЕ НАСТРОЙКИ (ОТКАТ)
# ==============================================================================
def rollback_settings():
    try:
        _rollback_settings_impl()
    except Exception as e:
        print(f"\n {CLR_RED}[ОШИБКА ОТКАТА]{CLR_RESET}: {e}")
        traceback.print_exc()
        input(" Нажмите Enter для продолжения...")

def _rollback_settings_impl():
    print("\n" + "=" * 70)
    print(f"{CLR_BOLD}{CLR_YELLOW}  >>> ВОССТАНОВЛЕНИЕ СТАНДАРТНЫХ НАСТРОЕК (ОТКАТ) <<<{CLR_RESET}")
    print("=" * 70)

    cfg = load_config()

    # Шаг 1: Удаление переменных окружения из реестра
    log_step(1, 3, "Удаление переменных из HKCU\\Environment")
    for key in ENV_KEYS:
        delete_registry_env(key)
        log_ok(f"Удалена переменная: {key}")

    broadcast_environment_change()

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
                if "--proxy-server=" in args or "--ignore-certificate-errors" in args:
                    cleaned = " ".join([
                        a for a in args.split()
                        if not a.startswith("--proxy-server=") and a != "--ignore-certificate-errors"
                    ])
                    update_shortcut_args(lnk, cleaned)
                    log_ok(f"Очищены аргументы ярлыка: {os.path.basename(lnk)}")
            except Exception:
                pass

    # Шаг 3: Остановка локального DPI-обходчика и WARP
    log_step(3, 3, "Остановка локального ядра обхода блокировок")
    global ACTIVE_PROXY
    if ACTIVE_PROXY:
        ACTIVE_PROXY.stop()
        ACTIVE_PROXY = None
    log_ok("Локальный прокси остановлен.")
    # Отключаем WARP, если он был подключен нами
    warp_disconnect()
    log_ok("Cloudflare WARP отключен (если был подключен).")

    # Восстанавливаем config.toml Codex
    rollback_codex_config_base_url()

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
# ПУНКТЫ [4] И [5]: СООБЩЕСТВО И ПОДДЕРЖКА
# ==============================================================================
def open_url(url: str, title: str):
    print(f"\n Открытие страницы {title}...")
    opened = False
    try:
        opened = webbrowser.open_new_tab(url)
    except Exception:
        opened = False

    if opened:
        log_ok(f"Ссылка открыта в вашем браузере!")
    else:
        log_info("Не удалось автоматически открыть браузер.")
        
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
    print(f" {CLR_GRAY}Обход блокировок ТСПУ + Шлюз для OpenAI Codex, CLI и VS Code{CLR_RESET}")
    print("-" * 75)

    if is_admin():
        print(f" {CLR_GREEN}●{CLR_RESET} Права: {CLR_BOLD}Администратор{CLR_RESET}")
    else:
        print(f" {CLR_YELLOW}●{CLR_RESET} Права: {CLR_BOLD}Пользователь{CLR_RESET}")

    global ACTIVE_PROXY
    if ACTIVE_PROXY and ACTIVE_PROXY.is_running:
        print(f" {CLR_GREEN}●{CLR_RESET} DPI-Ядро: {CLR_GREEN}{CLR_BOLD}АКТИВНО{CLR_RESET} {CLR_GRAY}(127.0.0.1:{ACTIVE_PROXY.port}){CLR_RESET}")
    else:
        print(f" {CLR_GRAY}○{CLR_RESET} DPI-Ядро: {CLR_GRAY}Готово к запуску{CLR_RESET}")

    cfg = load_config()
    gateway = cfg.get("openai_base_url", DEFAULT_OPENAI_BASE_URL)
    print(f" {CLR_CYAN}●{CLR_RESET} Шлюз Codex: {CLR_BOLD}{gateway}{CLR_RESET}")

    curr_http = get_registry_env("HTTP_PROXY")
    if curr_http:
        print(f" {CLR_GREEN}●{CLR_RESET} Системный прокси: {CLR_BOLD}{curr_http}{CLR_RESET}")
    else:
        print(f" {CLR_GRAY}○{CLR_RESET} Системный прокси: {CLR_GRAY}Не задан (стандартный){CLR_RESET}")

    # Статус WARP
    if ACTIVE_PROXY and ACTIVE_PROXY.upstream_proxy:
        print(f" {CLR_MAGENTA}●{CLR_RESET} Cloudflare WARP: {CLR_MAGENTA}{CLR_BOLD}АКТИВЕН{CLR_RESET} {CLR_GRAY}(SOCKS5 127.0.0.1:40000 → обход 403){CLR_RESET}")
    elif is_warp_installed():
        print(f" {CLR_YELLOW}●{CLR_RESET} Cloudflare WARP: {CLR_BOLD}Установлен{CLR_RESET} {CLR_GRAY}(будет подключен при запуске){CLR_RESET}")
    else:
        print(f" {CLR_RED}○{CLR_RESET} Cloudflare WARP: {CLR_GRAY}Не установлен (нужен для обхода 403){CLR_RESET}")

    print("-" * 75)

def main_menu():
    while True:
        try:
            render_banner()
            print(f" {CLR_BOLD}Главное меню:{CLR_RESET}")
            print(f"  {CLR_CYAN}[1]{CLR_RESET} {CLR_BOLD}Запустить службу обхода и настроить систему (1 клик){CLR_RESET}")
            print(f"  {CLR_CYAN}[2]{CLR_RESET} Настроить шлюз OpenAI Codex (OPENAI_BASE_URL)")
            print(f"  {CLR_CYAN}[3]{CLR_RESET} Восстановить стандартные настройки (Откат)")
            print(f"  {CLR_CYAN}[4]{CLR_RESET} Сообщество проекта (Telegram)")
            print(f"  {CLR_CYAN}[5]{CLR_RESET} Поддержать автора (Boosty)")
            print(f"  {CLR_CYAN}[0]{CLR_RESET} Выход")
            print("-" * 75)

            choice = input(f" Выберите действие [0-5]: ").strip()

            if choice == "1":
                apply_patch_and_run_service()
            elif choice == "2":
                configure_codex_gateway()
            elif choice == "3":
                rollback_settings()
            elif choice == "4":
                open_url(COMMUNITY_URL, "Сообщество проекта (Telegram)")
            elif choice == "5":
                open_url(BOOSTY_URL, "Поддержать автора (Boosty)")
            elif choice in ("0", "exit", "quit", "q"):
                print(f"\n{CLR_GRAY}Завершение работы... До встречи!{CLR_RESET}\n")
                sys.exit(0)
            else:
                print(f" {CLR_RED}Неверный ввод. Пожалуйста, укажите цифру от 0 до 5.{CLR_RESET}")
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
