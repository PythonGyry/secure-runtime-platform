# Додавання застосунків (apps) до платформи

Як додати новий скрипт/застосунок у платформу, зібрати його, підключити до існуючих ліцензій і що імпортувати з платформи.

---

## Хто перевіряє ліцензію

**Перевірку ліцензії робить клієнт (bootstrap), а не апка.**

Перед тим як завантажити й запустити твій код, клієнт:

1. Запитує у користувача ліцензійний ключ (якщо ще не збережений).
2. Відправляє на сервер запит перевірки (ключ + HWID пристрою).
3. Отримує маніфест і завантажує зашифрований runtime-пакет **тільки якщо** ліцензія валідна і прив’язана до цього пристрою.
4. Розшифровує пакет і викликає `run_runtime(context_payload)` — тобто твій код уже запускається в «дозволеному» середовищі.

Тому **в апці не обов’язково** писати перевірку ліцензії: без валідного ключа твій код взагалі не виконається. Мінімальна апка — лише `run_runtime(context)` і своя логіка.

---

## Перевірка ліцензії всередині апки (опційно)

Якщо потрібно **додатково** перевіряти ліцензію вже під час роботи апки (наприклад, періодично, перед важливою дією або після тривалого простою), можна викликати той самий API, що й клієнт:

- **Endpoint:** `POST {server_base_url}/api/v1/license/check`
- **Тіло (JSON):** `license_key`, `hwid`, `app`, `channel` — усі ці значення є в `context_payload`, який платформа передала в `run_runtime`.
- **Відповідь:** `{"valid": true}` або `{"valid": false, "message": "..."}`.

Приклад (всередині апки):

```python
import requests

def check_license_from_app(context_payload: dict) -> bool | None:
    """Повертає True якщо ліцензія валідна, False якщо ні, None якщо помилка мережі."""
    url = f"{context_payload['server_base_url'].rstrip('/')}/api/v1/license/check"
    try:
        r = requests.post(
            url,
            json={
                "license_key": context_payload["license_key"],
                "hwid": context_payload["hwid"],
                "app": "my_tool",   # твій app_id
                "channel": "stable",
            },
            timeout=10,
        )
        if r.status_code != 200:
            return False
        return bool(r.json().get("valid"))
    except Exception:
        return None
```

- **`True`** — ключ дійсний, можна продовжувати роботу.
- **`False`** — ключ недійсний або заблокований; можна показати повідомлення і закрити апку.
- **`None`** — мережа недоступна; за бажанням можна дати grace period або попросити перевірити підключення.

Підсумок: базова перевірка — це вже справа клієнта; у апці перевірку робити не обов’язково. Якщо хочеш перевіряти ліцензію ще й у апці — використовуй `POST /api/v1/license/check` з даними з контексту.

---

## 1. Структура папки апки

Кожен застосунок — це **папка** в `runtime_logic/apps/<app_id>/`. Ім'я папки = **app_id** (латиницею, без пробілів), наприклад `wishlist`, `my_tool`.

Мінімальна структура:

```
runtime_logic/apps/
└── <app_id>/                    # наприклад my_tool
    ├── __init__.py              # порожній або мінімальний
    ├── icon.ico                 # опційно — іконка для клієнта
    ├── README.md                # опційно
    └── src/
        ├── __init__.py
        └── entrypoints/
            ├── __init__.py
            └── runtime_entry.py   # обов'язкова точка входу
```

У `runtime_entry.py` має бути **функція** з сигнатурою:

```python
def run_runtime(context_payload: dict) -> None:
    ...
```

Її викликає платформа після перевірки ліцензії та розпакування runtime-пакета. Інший код апки може лежати в `src/app/` або будь-де під `src/` — головне, щоб модуль з entrypoint імпортувався як `runtime_logic.apps.<app_id>.src.entrypoints.runtime_entry`.

---

## 2. Контракт: що передає платформа в апку

Платформа передає в `run_runtime(context_payload)` один аргумент — словник **context** з такими полями:

| Ключ | Опис |
|------|------|
| `license_key` | Ліцензійний ключ (рядок). |
| `hwid` | Ідентифікатор пристрою (прив’язка ліцензії). |
| `server_base_url` | Базовий URL бекенду (наприклад `http://127.0.0.1:8000`). |
| `server_salt` | Сіль сервера (для крипто). |
| `runtime_data_dir` | Шлях до папки даних runtime (зберігати свої файли/БД тут). |
| `legacy_base_dir` | Шлях до «legacy» бази (якщо потрібна міграція). |
| `icon_path` | Шлях до іконки апки (або `None`). |
| `app_version` | Версія апки з маніфесту (рядок). |

Приклад використання контексту в апці:

```python
from pathlib import Path

def run_runtime(context_payload: dict) -> None:
    runtime_data_dir = Path(context_payload["runtime_data_dir"])
    license_key = context_payload["license_key"]
    # Створити БД, логи тощо в runtime_data_dir
    ...
```

---

## 3. Що імпортувати з платформи (shared)

Апка **не** імпортує модулі з `backend/` або `client/` — тільки з **`shared/`** і власні модулі з `runtime_logic.apps.<app_id>.*`.

Для шифрування локальних даних використовуй:

```python
from shared.crypto.runtime_crypto import (
    derive_fernet_key,
    encrypt_bytes,
    decrypt_bytes,
    sha256_bytes,
)
```

- **`derive_fernet_key(*parts, layer="")`** — отримати ключ Fernet з частин (наприклад `license_key`, `hwid`, `server_salt`) і опційного `layer`.
- **`encrypt_bytes(data, key=...)`** / **`decrypt_bytes(data, key=...)`** — шифрування/розшифрування байтів.
- **`sha256_bytes(data)`** — SHA256-хеш у hex.

Приклад ключа для локальної БД:

```python
key = derive_fernet_key(
    context_payload["license_key"],
    context_payload["hwid"],
    context_payload["server_salt"],
    layer="db",
)
```

Решта платформи (бекенд, клієнт) апці не потрібна — достатньо контексту та `shared.crypto`.

---

## 4. Збірка апки та поява в платформі

1. Поклади код апки в `runtime_logic/apps/<app_id>/` з обов’язковим `src/entrypoints/runtime_entry.py` і функцією `run_runtime(context_payload)`.

2. Збери runtime-пакет (це також реєструє реліз у БД платформи):

   ```bash
   python manager.py build -a <app_id> -v 1.0.0 -c stable
   ```

   Після цього:
   - у `backend/packages/` з’являться zip і manifest для цієї апки;
   - у БД з’явиться запис у `runtime_releases` для `<app_id>` / `stable` / `1.0.0`;
   - апка з’явиться в списку доступних у адмінці.

3. За потреби збери bootstrap exe з іконкою цієї апки:

   ```bash
   python manager.py client -a <app_id> -n MyToolBootstrap
   ```

   Іконка береться з `runtime_logic/apps/<app_id>/icon.ico`.

---

## 5. Підключення існуючих ключів до апки

Ліцензії в адмінці мають поле **доступ за апками і каналами** — `channel_access`. Це словник виду:

```json
{
  "wishlist": ["stable"],
  "my_tool": ["stable", "beta"]
}
```

- **Як додати нову апку до вже існуючого ключа**  
  В адмін-панелі: відкрити ліцензію → змінити `channel_access`, додавши ключ з іменем апки та списком каналів, наприклад `"my_tool": ["stable"]` → зберегти. Після цього цей ключ буде дійсний і для `my_tool` на каналі `stable`.

- **Як створити новий ключ тільки для однієї апки**  
  При створенні ліцензії вказати `channel_access` лише для цієї апки, наприклад `{"my_tool": ["stable"]}`.

- **Звідки клієнт знає, яку апку запускати**  
  За замовчуванням bootstrap питає сервер: для даного ключа повертається список дозволених апок (`apps`). Якщо є лише одна — її і завантажують; якщо кілька — зараз береться перша з списку (у майбутньому можна додати вибір у клієнті).

Підсумок: щоб **існуючий ключ** почав відкривати апку `my_tool`, достатньо в адмінці для цього ключа в `channel_access` додати `"my_tool": ["stable"]` (або інші канали, які ти зібрав для цієї апки).

---

## 6. Короткий чеклист для нової апки

1. Створити папку `runtime_logic/apps/<app_id>/` з `src/entrypoints/runtime_entry.py` і функцією `run_runtime(context_payload)`.
2. Використовувати в апці лише імпорти з `shared.*` та `runtime_logic.apps.<app_id>.*`.
3. Зібрати пакет: `python manager.py build -a <app_id> -v 1.0.0 -c stable`.
4. У адмін-панелі для потрібних ліцензій у `channel_access` додати `<app_id>: ["stable"]` (або інші канали).
5. За потреби зібрати клієнт з іконкою апки: `python manager.py client -a <app_id> -n MyAppBootstrap`.

Після цього користувач з відповідним ключем зможе запускати твою апку через той самий bootstrap (або окремий exe, зібраний з `-a <app_id>`).
