# OpenAI Codex & ChatGPT DPI Patcher (Windows)

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%2F%2011-0078D6.svg)](https://microsoft.com/windows)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Zero Downloads](https://img.shields.io/badge/Zero--Downloads-100%25%20Standalone-brightgreen.svg)]()

Автономная утилита в 1 клик для разработчиков и пользователей из России: обеспечивает стабильную работу **OpenAI Codex** (CLI, VS Code, Cursor) и десктопного приложения **ChatGPT**.

---

## Что решает эта программа?

В России при работе с сервисами OpenAI возникают сразу две проблемы:
1. **Блокировка ТСПУ / РКН**: DPI провайдеров глушит пакеты с открытым SNI (`api.openai.com`, `chatgpt.com`), разрывая соединение при TLS Handshake (`connection reset`, `tls handshake eof`).
2. **Блокировка 403 Forbidden со стороны OpenAI**: сервера OpenAI отклоняют запросы с российских IP-адресов.

### Наше решение:
* **Локальное ядро Zapret DPI Bypass (100% бесплатно, 0 рублей)**: встроенная десинхронизация TCP по алгоритму `split2` — дробит заголовок TLS Record на 2-м байте и разрезает запрещенный домен внутри SNI с `TCP_NODELAY`. ТСПУ не распознает трафик, и соединение проходит без покупки VPN и прокси!
* **Поддержка OpenAI Codex**: в 1 клик настраивает системные переменные `OPENAI_BASE_URL` и изолированный прокси в реестре Windows (`HKCU\Environment`) с рассылкой `WM_SETTINGCHANGE`. Все терминалы, Codex CLI и VS Code подхватывают настройки без перезагрузки.
* **Снятие 403 Forbidden**: возможность перенаправления запросов через бесплатный европейский Cloudflare Worker (шаблон [cloudflare_worker.js](cloudflare_worker.js) включен в репозиторий, до 100 000 запросов/день бесплатно без карт).
* **Авто-перезапуск ChatGPT Desktop**: находит установленный клиент (включая версию из Microsoft Store `OpenAI.Codex`), закрывает старый процесс и запускает с флагами прокси.
* **100% изоляция**: не вмешивается в трафик Discord (включая Запрет), Telegram, онлайн-игр и обычных браузеров.
* **0 скачиваний и 0 покупок**: никаких сторонних программ, платных подписок или платных прокси. Чистый standalone `.exe`.

---

## Быстрый старт (для пользователей)

1. Перейдите во вкладку [Releases](https://github.com/gde-agusha/chatgpt-codex-patcher/releases) и скачайте **`ChatGPT_Patcher.exe`** (~10 МБ).
2. Запустите файл и нажмите **`[1]`**:
   - Локальная служба активируется на `127.0.0.1:10809` (или свободном порту).
   - Системные переменные для Codex и VS Code применятся автоматически.
   - Десктопный ChatGPT автоматически перезапустится с параметрами обхода.
3. Просто сверните окно консоли и пользуйтесь Кодексом!

> **Важно:** Не закрывайте окно на крестик во время работы (просто сверните). Для возврата стандартных настроек системы нажмите **`[R]`** или **`[3]`** (Откат).

---

## Настройка OpenAI Codex (VS Code, Cursor, CLI)

### Использование через Codex CLI
После запуска программы с опцией `[1]` все терминалы автоматически используют настроенный `OPENAI_BASE_URL`:
```powershell
codex "Напиши функцию на Python"
```

### Использование в VS Code / Cursor
В настройках расширения OpenAI / Codex укажите:
* **Proxy**: `http://127.0.0.1:10809`
* **Base URL**: значение из утилиты (по умолчанию `https://api.openai.com/v1` или адрес вашего Cloudflare Worker).

---

## Как убрать ошибку 403 Forbidden (Свой Cloudflare Worker)

Если OpenAI блокирует ваш IP со статусом `403 Forbidden`, вы можете поднять собственный бесплатный шлюз за 1 минуту:

1. Зайдите на [dash.cloudflare.com](https://dash.cloudflare.com) ➔ **Workers & Pages** ➔ **Create Application**.
2. Вставьте код из файла [cloudflare_worker.js](cloudflare_worker.js) и нажмите **Deploy**.
3. Скопируйте полученную ссылку (например: `https://my-codex.workers.dev/v1`).
4. В `ChatGPT_Patcher.exe` выберите пункт **`[2]`** и вставьте эту ссылку.
5. Готово! Теперь все запросы Codex идут через европейские серверы Cloudflare без 403 ошибки.

---

## Сборка из исходников

```powershell
# Клонировать репозиторий
git clone https://github.com/gde-agusha/chatgpt-codex-patcher.git
cd chatgpt-codex-patcher

# Сборка единого .exe через PyInstaller
python -m PyInstaller --onefile --name "ChatGPT_Patcher" main.py
```
Собранный исполняемый файл появится в папке `dist/ChatGPT_Patcher.exe`.

---

## Лицензия

Проект распространяется под свободной лицензией [MIT](LICENSE).
