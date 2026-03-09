# Деплой: nginx + HTTPS (ваш домен)

Домен має вказувати на IP сервера. Далі — тільки HTTPS, HTTP редіректиться на HTTPS.

## Швидкий варіант (один скрипт)

Перед запуском відредагуйте в скрипті `DOMAIN="your-domain.com"` або встановіть змінну: `export DOMAIN=your-domain.com`

```bash
cd /path/to/secure-runtime-platform
sudo bash deploy/setup-nginx-certbot.sh
```

Скрипт:
1. Встановить `nginx` та `certbot` (python3-certbot-nginx)
2. Скопіює конфіг nginx у `/etc/nginx/sites-available/<DOMAIN>`
3. Увімкне сайт і перезапустить nginx
4. Запустить certbot для домену (запитає email для Let's Encrypt)
5. Certbot отримає сертифікат і налаштує редірект HTTP → HTTPS

Після цього:
- Відкрийте https://your-domain.com (адмінка: /admin/)
- У адмін-панелі встановіть **Client Bootstrap URL**: `https://your-domain.com`
- Backend має працювати на тому ж сервері: `python manager.py run` (порт 8000)

## Ручне налаштування

### 1. Встановити пакети

```bash
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx
```

### 2. Підключити конфіг nginx

Відредагуйте `deploy/nginx-secure-runtime-platform.conf`: замініть `server_name` на ваш домен. Потім:

```bash
sudo cp deploy/nginx-secure-runtime-platform.conf /etc/nginx/sites-available/your-domain.com
sudo ln -sf /etc/nginx/sites-available/your-domain.com /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default   # якщо потрібен тільки цей сайт
sudo nginx -t && sudo systemctl reload nginx
```

### 3. Отримати сертифікат і увімкнути редірект на HTTPS

```bash
sudo certbot --nginx -d your-domain.com --redirect --agree-tos -m your@email.com
```

Параметр `--redirect` — усі запити по HTTP будуть перенаправлені на HTTPS.

### 4. Перезавантажити nginx

```bash
sudo systemctl reload nginx
```

## Перевірка

- HTTP: `http://your-domain.com` → має редіректити на `https://...`
- HTTPS: `https://your-domain.com` — відкривається сайт
- Адмінка: `https://your-domain.com/admin/`

## Оновлення сертифіката

Let's Encrypt видає сертифікати на 90 днів. Certbot додає cron/systemd timer для продовження. Перевірити вручну:

```bash
sudo certbot renew --dry-run
```

## Backend

Має слухати лише localhost (порт 8000), щоб зовні був доступ тільки через nginx:

```bash
python manager.py run
```

У `manager.py` вже використовується `--host 127.0.0.1 --port 8000`.
