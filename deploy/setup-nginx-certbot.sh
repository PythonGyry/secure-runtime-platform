#!/bin/bash
# Налаштування nginx + certbot для вашого домену (тільки HTTPS).
# Перед запуском: встановіть DOMAIN=ваш-домен.com або відредагуйте нижче.
# Запускати з root або через sudo.

set -e
DOMAIN="${DOMAIN:-your-domain.com}"
NGINX_CONF="/etc/nginx/sites-available/${DOMAIN}"
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Встановлення nginx та certbot ==="
apt-get update
apt-get install -y nginx certbot python3-certbot-nginx

echo "=== Підготовка ACME challenge ==="
mkdir -p /var/www/html
chown -R www-data:www-data /var/www/html 2>/dev/null || true

echo "=== Копіювання конфігурації nginx ==="
if [ ! -f "$PROJECT_ROOT/deploy/nginx-secure-runtime-platform.conf" ]; then
    if [ -f "$PROJECT_ROOT/deploy/nginx-secure-runtime-platform.conf.example" ]; then
        sed "s/your-domain.com/${DOMAIN}/g" "$PROJECT_ROOT/deploy/nginx-secure-runtime-platform.conf.example" > "$PROJECT_ROOT/deploy/nginx-secure-runtime-platform.conf"
        echo "Створено nginx-secure-runtime-platform.conf з прикладу (server_name=$DOMAIN)."
    else
        echo "Помилка: не знайдено deploy/nginx-secure-runtime-platform.conf і .example. Створіть конфіг вручну."
        exit 1
    fi
fi
cp "$PROJECT_ROOT/deploy/nginx-secure-runtime-platform.conf" "$NGINX_CONF"
ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/ 2>/dev/null || true

# Видалити default site якщо він конфліктує за портом 80
if [ -f /etc/nginx/sites-enabled/default ]; then
    rm -f /etc/nginx/sites-enabled/default
fi

echo "=== Перевірка nginx ==="
nginx -t

echo "=== Перезапуск nginx ==="
systemctl reload nginx || systemctl start nginx

echo "=== Отримання SSL сертифіката (Let's Encrypt) ==="
if [ -n "$CERTBOT_EMAIL" ]; then
    certbot --nginx -d "$DOMAIN" --redirect --non-interactive --agree-tos -m "$CERTBOT_EMAIL"
else
    echo "Потрібна email для Let's Encrypt (відновлення, попередження)."
    read -r -p "Email: " EMAIL
    if [ -z "$EMAIL" ]; then
        echo "Запуск certbot без email (може бути обмеження)."
        certbot --nginx -d "$DOMAIN" --redirect --non-interactive --agree-tos --register-unsafely-without-email
    else
        certbot --nginx -d "$DOMAIN" --redirect --non-interactive --agree-tos -m "$EMAIL"
    fi
fi

echo "=== Перезавантаження nginx після certbot ==="
systemctl reload nginx

echo ""
echo "Готово. Сайт доступний тільки по HTTPS: https://${DOMAIN}"
echo "Переконайтесь, що backend запущено: python manager.py run"
echo "У адмін-панелі встановіть Client Bootstrap URL: https://${DOMAIN}"
echo ""
echo "Автооновлення сертифіката: certbot renew (cron уже налаштовується пакетом)."
