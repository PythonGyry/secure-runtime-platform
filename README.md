# Secure Runtime Platform

Платформа для ліцензування та безпечної доставки застосунків кінцевим користувачам.

## Що це

Система складається з:

- **Backend** — сервер ліцензій, маніфестів і пакетів
- **Bootstrap-клієнт** — легкий завантажувач, який перевіряє ліцензію і завантажує runtime
- **Runtime-пакети** — зашифровані архіви з логікою застосунків
- **Admin-панель** — веб-інтерфейс для управління ліцензіями та релізами

Користувач отримує один клієнт (Windows: `.exe`, Linux: бінар без розширення). Після введення ліцензійного ключа клієнт завантажує актуальну версію програми з сервера. Логіка не зберігається в статичному exe — оновлення без перевипуску клієнта.

## Документація

- [ARCHITECTURE.md](ARCHITECTURE.md) — структура проекту, платформа та застосунки
- [ADDING_APPS.md](ADDING_APPS.md) — як додавати апки, підключати ключі, що імпортувати
- [DEPLOY.md](DEPLOY.md) — деплой на Linux: доступ на сервер, nginx, HTTPS, вигрузка збірки з Windows
- [SECURITY.md](SECURITY.md) — модель безпеки, шифрування, захист даних

## Швидкий старт

1. Встановити залежності:
  ```bash
   python -m pip install -r backend/requirements.txt
   python -m pip install -r client/requirements.txt
  ```
2. Зібрати runtime-пакет і запустити сервер:
  ```bash
   python manager.py build -a wishlist -v 1.0.0
   python manager.py admin -p <пароль>
   python manager.py run
  ```
3. Відкрити адмін-панель: [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)
4. Створити ліцензію в панелі
5. Запустити клієнт: `python client/src/main.py` або зібраний клієнт: `dist/<name>.exe` (Windows), `./dist/<name>` (Linux)

## Збірка на Linux

- **Backend і runtime-пакети** — ті самі команди: `python manager.py build -a wishlist -v 1.0.0`, `python manager.py run`.
- **Cython** — потрібен gcc: `apt install build-essential` (Debian/Ubuntu) або аналог. Збірка через `manager.py client` або вручну: `bash client/build_cython.sh`.
- **Bootstrap-клієнт** — `python manager.py client -n wishlist_bootstrap` створює `dist/wishlist_bootstrap` (без .exe). Потрібні: `pip install -r client/requirements-build.txt` (pyinstaller, cython).
- **Скрипт "перезапуск + очистка кешу"** — `bash fix_client_decrypt.sh` (аналог `fix_client_decrypt.bat` на Windows).

## Сервер на Linux, збірка на Windows (вигрузка апки)

Якщо backend крутиться на **Linux**, а збираєте на **Windows** і потрібно вигрузити пакети та отримати .exe під ваш сервер:

1. Налаштуйте `deploy_config.json` (скопіюйте з `deploy_config.example.json`): host, user, path, server_url.
2. Встановіть для вигрузки: `pip install -r scripts/requirements-deploy.txt` (paramiko).
3. Одна команда — збірка пакетів, збірка .exe з URL сервера, вигрузка на сервер:

```bash
python manager.py deploy --build --build-client --server-url https://your-server.com
```

Пакети потраплять у `backend/packages/` на сервері, .exe буде в `dist/` і одразу підключатиметься до вказаного URL. Детально: [scripts/README.md](scripts/README.md#deploy--вигрузка-на-linux-сервер-з-windows).

**Як додати нову апку з Windows на сервер**, щоб вона грузилась у клієнт у runtime: збери її (`manager.py build -a <app_id> -v 1.0.0`), вигрузи пакети (`manager.py deploy --build`), на сервері в адмінці натисни **Releases → Sync Packages** (або перезапусти backend). Далі створи/вкажи ліцензію для цієї апки. Детально: [ADDING_APPS.md](ADDING_APPS.md#7-додавання-апок-з-windows-на-linux-сервер-щоб-грузились-в-клієнт-у-runtime).

## Основні команди


| Команда                              | Опис                                      |
| ------------------------------------ | ----------------------------------------- |
| `manager.py list`                    | Список доступних застосунків              |
| `manager.py build -a <app> -v <ver>` | Збірка runtime-пакета                     |
| `manager.py client -n <name>`        | Збірка bootstrap-клієнта (exe на Windows, бінар на Linux); --server-url для підключення до Linux-сервера |
| `manager.py deploy [--build] [--build-client] [--server-url URL]` | Вигрузка пакетів на Linux-сервер (з Windows), опціонально збірка та exe |
| `manager.py full -a <app> -v <ver>`  | Повна перезбірка (clean + build + client) |
| `manager.py run`                     | Запуск backend                            |


## Структура проекту

```
├── backend/      # FastAPI, ліцензії, API, пакети
├── client/       # Bootstrap loader (PyInstaller → exe)
├── admin/        # HTML/CSS/JS адмін-панель
├── shared/       # Спільна криптографія та контракти
├── runtime_logic/
│   ├── apps/     # Застосунки (наприклад wishlist)
│   └── build_tools/  # Збірка runtime-пакетів
└── manager.py    # CLI для збірки та запуску
```

## Ключові особливості

- **Ліцензія + пристрій** — ключ прив’язується до HWID
- **Шифрування** — runtime-пакети та локальні дані зашифровані
- **Оновлення** — нова версія через сервер без перевипуску exe
- **Відкликання** — ліцензію можна відключити, runtime перевіряє її періодично

