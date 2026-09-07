# OpenAI Codex & ChatGPT Isolated Patcher (Windows)

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%2F%2011-0078D6.svg)](https://microsoft.com/windows)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Zero Downloads](https://img.shields.io/badge/Zero--Downloads-100%25%20Standalone-brightgreen.svg)]()
[![No Discord/TG Impact](https://img.shields.io/badge/Discord%20%26%20TG-100%25%20Untouched-brightgreen.svg)]()

Автономная утилита в 1 клик для разработчиков и пользователей из России: обеспечивает стабильную работу **OpenAI Codex** (CLI, VS Code, Cursor) и десктопного приложения **ChatGPT**.

---

## Главные преимущества v5.0.0 (Isolated Edition)

1. **ПОЛНАЯ СЕТЕВАЯ ИЗОЛЯЦИЯ**:
   * **Discord, Telegram, Steam, браузеры и игры НЕ ЗАТРАГИВАЮТСЯ!**
   * Системный прокси Windows (`ProxyEnable`) отключен.
   * Глобальные переменные `HTTP_PROXY` не засоряют систему.
2. **ChatGPT Desktop**:
   * Маршрутизируется изолированно через аргументы запуска (`--proxy-server="http://127.0.0.1:10809" --proxy-bypass-list="<-loopback>"`).
   * Автоматически находит ярлыки, патчит их и перезапускает приложение.
3. **OpenAI Codex CLI & VS Code**:
   * Создает изолированный лаунчер `codex-unlocked`, который задает переменные прокси **СТРОГО** для процесса Codex.
   * Можно запустить разблокированную консоль прямо из меню программы (кнопка `[2]`).
4. **100% РАБОТА И ОБХОД ОШИБКИ 403**:
   * Автоматическая бесшовная интеграция с изолированным режимом Cloudflare WARP (`WarpProxy` на порту 40000). В этом режиме WARP не создает сетевых адаптеров и пускает через европейский IP **только трафик OpenAI**, сохраняя ваш пинг в играх и звонках.
   * Автономный Zapret DPI-байпас (`split2` + SNI десинхронизация) для обхода фильтров ТСПУ.
5. **0 лишних действий**: нажал **`[1]`** — и всё работает.

---

## Быстрый старт (для пользователей)

1. Скачайте **`ChatGPT_Patcher.exe`** (~10 МБ).
2. Запустите файл и нажмите **`[1]`**:
   - Локальный шлюз активируется на `127.0.0.1:10809`.
   - Десктопный ChatGPT автоматически перезапустится с параметрами обхода.
   - Будет создан изолированный лаунчер `codex-unlocked`.
3. Просто сверните окно консоли и пользуйтесь ChatGPT и Кодексом!

> **Важно:** Не закрывайте окно во время работы (просто сверните). Для полного возврата заводских настроек нажмите **`[R]`** или **`[4]`** (Откат).

---

## Использование OpenAI Codex CLI

После активации службы (`[1]`) вы можете использовать Codex в любом терминале (PowerShell, CMD, терминал VS Code):

```powershell
codex-unlocked "Напиши функцию на Python"
```

Или выберите в меню программы пункт **`[2]`**, чтобы сразу открыть разблокированную консоль!

---

## Сборка из исходников

```powershell
# Клонировать репозиторий
git clone https://github.com/agusha1337/ChatGPT-unlocker-patcher.git
cd ChatGPT-unlocker-patcher

# Сборка единого .exe через PyInstaller
python -m PyInstaller --noconfirm --clean ChatGPT_Patcher.spec
```
Собранный исполняемый файл появится в папке `dist/ChatGPT_Patcher.exe`.

---

## Лицензия

Распространяется под свободной лицензией MIT.
