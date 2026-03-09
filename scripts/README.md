# Scripts

Скрипти для збірки та підтримки платформи.

## manager.py

Головний CLI для управління платформою. Запускати з кореня проекту.

```bash
python manager.py list
python manager.py build -a wishlist -v 1.0.7
python manager.py build -a app1 -a app2 -v 1.0.0
python manager.py build --all -v 1.0.8
python manager.py client -n myapp_bootstrap
python manager.py clean [--full]
python manager.py full -a wishlist -v 1.0.7
python manager.py admin -p <пароль>
python manager.py db reset
python manager.py run
```

## deploy — вигрузка на Linux-сервер (з Windows)

Якщо платформа крутиться на **Linux**, а збірку робите на **Windows**, щоб отримати .exe і викласти пакети на сервер:

1. На Windows: клонувати репо, встановити залежності (backend, client, client/requirements-build.txt, `pip install -r scripts/requirements-deploy.txt` для paramiko).
2. Налаштувати доступ до сервера: скопіювати `deploy_config.example.json` в `deploy_config.json` (не комітити) і вказати `host`, `user`, `path`, за бажанням `key_path` або `password`, `server_url` (наприклад `https://your-server.com`).
3. З кореня проекту запустити одну команду:

```bash
python manager.py deploy --build --build-client --server-url https://your-server.com
```

(Якщо `deploy_config.json` заповнений, достатньо `python manager.py deploy --build --build-client`.)

Що відбувається:
- **--build** — збирає runtime-пакети (`manager.py build -a wishlist -v 1.0.0`).
- **--build-client** — збирає .exe клієнт з вшитим URL сервера (клієнт одразу підключається до вашого Linux-сервера).
- Вигрузка папки `backend/packages/` на сервер по SFTP у вказаний `path/backend/packages/`.

Після вигрузки на сервері backend підхопить нові пакети; у адмінці переконайтесь, що **Client Bootstrap URL** = ваш `server_url`. Готовий .exe лежить у `dist/` — його можна роздавати користувачам.

Без --build / --build-client: тільки вигрузка вже зібраних пакетів (наприклад, якщо збирали раніше).

**Нова апка з Windows на сервер:** додай код у `runtime_logic/apps/<app_id>/`, збери `python manager.py build -a <app_id> -v 1.0.0`, потім `python manager.py deploy --build`. На сервері в адмінці (Releases) натисни **Sync Packages** (або перезапусти backend). Після цього створи/вкажи ліцензію для цієї апки — клієнт зможе завантажувати її в runtime. Детально: [ADDING_APPS.md](../ADDING_APPS.md#7-додавання-апок-з-windows-на-linux-сервер-щоб-грузились-в-клієнт-у-runtime).

```bash
python scripts/deploy_to_server.py --host my.server.com --user root --path /path/to/secure-runtime-platform --build --build-client --server-url https://my.server.com
```

Або через змінні: `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_PATH`, `DEPLOY_PASSWORD`, `DEPLOY_SERVER_URL`.

## rebuild.py

Повна перезбірка: clean + build + client. Делегує до `manager.py full`.

## Додавання нового застосунку

1. Створити `runtime_logic/apps/<app_id>/` зі структурою як у wishlist
2. Додати `entrypoints/runtime_entry.py` та `src/`
3. Збирати: `python manager.py build -a <app_id> -v 1.0.0`
