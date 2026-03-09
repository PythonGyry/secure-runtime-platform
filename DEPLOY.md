# Деплой на Linux-сервер

Покрокова інструкція: що потрібно на сервері, який доступ створити, як викласти збірку апки і запустити платформу.

---

## 1. Що потрібно мати

- **Linux-сервер** (VPS або виділений) з публічним IP. Підходить Ubuntu 20.04/22.04, Debian 11/12 тощо.
- **Домен**, який вказує на IP сервера (A-запис). Наприклад: `app.mydomain.com` → IP сервера.
- **Доступ по SSH** до сервера (логін + пароль або SSH-ключ).
- Локально (зазвичай **Windows**): репо платформи, Python для збірки клієнта та вигрузки пакетів.

---

## 2. Доступ на сервері: що створити

### 2.1 SSH-користувач

- Можна використовувати **root** або окремого користувача (наприклад `deploy`).
- Якщо створюєте окремого користувача:
  ```bash
  sudo adduser deploy
  sudo usermod -aG sudo deploy   # якщо потрібні права на встановлення пакетів
  ```
- Рекомендовано: **SSH-ключ** замість пароля. На своїй машині:
  ```bash
  ssh-keygen -t ed25519 -f ~/.ssh/deploy_key -N ""
  ssh-copy-id -i ~/.ssh/deploy_key.pub deploy@your-server.com
  ```
  Далі підключатися: `ssh -i ~/.ssh/deploy_key deploy@your-server.com`.

### 2.2 Шлях до проекту на сервері

Усі файли платформи мають лежати в **одній директорії**, наприклад:

- `/home/deploy/secure-runtime-platform` або
- `/opt/secure-runtime-platform`

Цей шлях потрібен для:
- клонування репо / копіювання файлів;
- вигрузки пакетів з Windows у `path/backend/packages/`;
- запуску backend: `python manager.py run` з цієї директорії.

Підсумок: потрібні **host** (або IP), **user**, **path** — саме вони потрапляють у `deploy_config.json` і в команду `manager.py deploy`.

---

## 3. Підготовка сервера (перший раз)

Підключіться по SSH і виконайте кроки нижче.

### 3.1 Встановити Python та залежності

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git
```

Переконайтесь, що `python3 --version` ≥ 3.10.

### 3.2 Клонувати репо (або завантажити код)

```bash
cd /home/deploy
git clone https://github.com/PythonGyry/secure-runtime-platform.git
cd secure-runtime-platform
```

(Або створіть директорію вручну і скопіюйте файли — головне, щоб структура проекту була та сама: `backend/`, `client/`, `admin/`, `shared/`, `manager.py` тощо.)

### 3.3 Віртуальне середовище та залежності backend

```bash
cd /home/deploy/secure-runtime-platform
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
```

Backend не потребує клієнта чи збірки exe на сервері — тільки `backend/requirements.txt`.

### 3.4 Створити адміна та дані

```bash
python manager.py admin -p "ВашНадійнийПароль"
```

Це створить/оновить адміна і файл `backend/data/admin_bootstrap.json`. Базу ліцензій backend створить сам при першому запуску.

### 3.5 Перевірка backend локально

```bash
python manager.py run
```

У браузері відкрийте `http://IP_СЕРВЕРА:8000/admin/`. Якщо сторінка адмінки відкривається — backend працює. Зупиніть (Ctrl+C) — далі налаштуємо nginx і HTTPS, щоб backend слухав лише localhost.

---

## 4. Nginx + HTTPS (доступ по домену)

Backend має слухати лише **127.0.0.1:8000**. Зовнішній доступ — тільки через nginx по HTTPS.

### Варіант A: один скрипт (рекомендовано)

На сервері, з кореня проекту:

```bash
cd /home/deploy/secure-runtime-platform
export DOMAIN=app.mydomain.com
sudo bash deploy/setup-nginx-certbot.sh
```

Скрипт:
- встановить nginx та certbot;
- візьме конфіг з `deploy/nginx-secure-runtime-platform.conf.example` (якщо немає `.conf`), підставить `DOMAIN`;
- увімкне сайт і отримає SSL (Let's Encrypt);
- налаштує редірект HTTP → HTTPS.

Потрібно буде ввести email для Let's Encrypt (або задати `export CERTBOT_EMAIL=your@email.com` перед запуском).

### Варіант B: вручну

1. Встановити nginx і certbot:
   ```bash
   sudo apt install -y nginx certbot python3-certbot-nginx
   ```
2. Скопіювати приклад конфігу, підставити домен:
   ```bash
   cd /home/deploy/secure-runtime-platform
   sed 's/your-domain.com/app.mydomain.com/g' deploy/nginx-secure-runtime-platform.conf.example > deploy/nginx-secure-runtime-platform.conf
   sudo cp deploy/nginx-secure-runtime-platform.conf /etc/nginx/sites-available/app.mydomain.com
   sudo ln -sf /etc/nginx/sites-available/app.mydomain.com /etc/nginx/sites-enabled/
   sudo rm -f /etc/nginx/sites-enabled/default
   sudo nginx -t && sudo systemctl reload nginx
   ```
3. Отримати сертифікат і редірект на HTTPS:
   ```bash
   sudo certbot --nginx -d app.mydomain.com --redirect --agree-tos -m your@email.com
   sudo systemctl reload nginx
   ```

Після цього:
- `https://app.mydomain.com` — головна сторінка / API;
- `https://app.mydomain.com/admin/` — адмін-панель.

---

## 5. Запуск backend постійно

Backend має працювати у фоні. Два варіанти.

### Варіант A: screen / tmux (просто)

```bash
cd /home/deploy/secure-runtime-platform
source venv/bin/activate
screen -S backend
python manager.py run
# Відключитися: Ctrl+A, D. Підключитися знову: screen -r backend
```

У `manager.py run` вже використовується `--host 127.0.0.1 --port 8000` — зовні доступ лише через nginx.

### Варіант B: systemd (рекомендовано для продакшну)

Створіть юніт (замініть шляхи та користувача на свої):

```bash
sudo nano /etc/systemd/system/secure-runtime-backend.service
```

Вміст:

```ini
[Unit]
Description=Secure Runtime Platform Backend
After=network.target

[Service]
Type=simple
User=deploy
WorkingDirectory=/home/deploy/secure-runtime-platform
Environment="PATH=/home/deploy/secure-runtime-platform/venv/bin"
ExecStart=/home/deploy/secure-runtime-platform/venv/bin/python manager.py run
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Потім:

```bash
sudo systemctl daemon-reload
sudo systemctl enable secure-runtime-backend
sudo systemctl start secure-runtime-backend
sudo systemctl status secure-runtime-backend
```

Логи: `journalctl -u secure-runtime-backend -f`.

---

## 6. Збірка апки та вигрузка з Windows на сервер

Тут платформа **вже крутиться на Linux**, а збірку робите на **Windows** (exe для користувачів і пакети для backend).

### 6.1 Налаштування вигрузки (один раз)

У корені проекту на Windows створіть `deploy_config.json` (не комітити — він у `.gitignore`):

```json
{
  "host": "app.mydomain.com",
  "user": "deploy",
  "path": "/home/deploy/secure-runtime-platform",
  "key_path": "C:\\Users\\You\\.ssh\\deploy_key",
  "password": "",
  "server_url": "https://app.mydomain.com"
}
```

- **host** — домен або IP сервера (як підключатися по SSH).
- **user** — SSH-користувач.
- **path** — шлях до проекту на сервері (де лежать `backend/`, `manager.py` тощо).
- **key_path** — шлях до приватного SSH-ключа (якщо без пароля). Якщо використовуєте пароль — залиште порожнім і вкажіть `password` або задайте змінну середовища `DEPLOY_PASSWORD`.
- **server_url** — URL, на який клієнт (.exe) буде підключатися (має співпадати з тим, що в адмінці як Client Bootstrap URL).

Встановіть залежність для вигрузки:

```bash
pip install -r scripts/requirements-deploy.txt
```

(Потрібен **paramiko** для SFTP.)

### 6.2 Що робить deploy

Команда з кореня проекту (Windows):

```bash
python manager.py deploy --build --build-client --server-url https://app.mydomain.com
```

Якщо `deploy_config.json` заповнений, достатньо:

```bash
python manager.py deploy --build --build-client
```

- **--build** — збирає runtime-пакети: `manager.py build -a wishlist -v 1.0.0` (апка за замовчуванням `wishlist`, версія `1.0.0`). Результат: файли в `backend/packages/` (zip + json маніфести).
- **--build-client** — збирає .exe клієнта з вшитим `server_url` (клієнт одразу йде на ваш сервер). Потрібен **--server-url** (або він береться з `deploy_config.json`).
- Далі скрипт по **SFTP** вигружає вміст `backend/packages/` у каталог **path/backend/packages/** на сервері.

Після вигрузки backend на сервері підхопить нові файли (при наступному запиті або після **Sync Packages** в адмінці). Готовий .exe лежить у `dist/` на Windows — його можна роздавати користувачам.

### 6.3 Інша апка або версія

```bash
python manager.py deploy --build --build-client --app myapp --version 1.0.1 --server-url https://app.mydomain.com
```

На сервері в адмінці: **Releases → Sync Packages** (якщо пакети не з’явилися), потім створити/оновити ліцензію для цієї апки.

### 6.4 Тільки вигрузка (без збірки)

Якщо пакети вже зібрані локально:

```bash
python manager.py deploy
```

Передати host/user/path можна аргументами або через змінні: `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_PATH`, `DEPLOY_PASSWORD`, `DEPLOY_SERVER_URL`.

---

## 7. Після деплою: адмін-панель

1. Відкрийте **https://ваш-домен.com/admin/**.
2. Увійдіть (логін/пароль з `backend/data/admin_bootstrap.json` або той, що задали через `manager.py admin -p ...`).
3. Переконайтесь, що **Client Bootstrap URL** (або аналог у налаштуваннях) вказаний як **https://ваш-домен.com** — інакше клієнт не знайде сервер.
4. У **Releases** натисніть **Sync Packages**, якщо щойно вигружали нові пакети.
5. Створіть ліцензії для потрібних апок і видайте ключі користувачам.

---

## 8. Короткий чеклист

**На сервері (один раз):**
- [ ] SSH-доступ (користувач + пароль або ключ)
- [ ] Встановлено Python 3.10+, git
- [ ] Клоновано репо (або скопійовано код) у вибраний `path`
- [ ] `python3 -m venv venv`, `pip install -r backend/requirements.txt`
- [ ] `python manager.py admin -p ...`
- [ ] Nginx + certbot (скрипт або вручну), домен вказує на сервер
- [ ] Backend запущено (screen/tmux або systemd) на 127.0.0.1:8000

**На Windows (для кожної збірки/апки):**
- [ ] `deploy_config.json` з host, user, path, server_url (та key_path або password)
- [ ] `pip install -r scripts/requirements-deploy.txt`
- [ ] `python manager.py deploy --build --build-client --server-url https://...` (або з config)
- [ ] Роздати користувачам .exe з `dist/` та ліцензійні ключі з адмінки

**Детальніше:** [deploy/README.md](deploy/README.md) (nginx/certbot), [scripts/README.md](scripts/README.md) (deploy з Windows).
