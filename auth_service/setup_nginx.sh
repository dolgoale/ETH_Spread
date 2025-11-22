#!/bin/bash
# Скрипт для настройки Nginx с авторизацией

set -e

DOMAIN=$1
NGINX_CONFIG="/etc/nginx/sites-available/${DOMAIN}"

if [ -z "$DOMAIN" ]; then
    echo "Использование: $0 <domain>"
    echo "Пример: $0 aadolgov.com"
    exit 1
fi

if [ ! -f "$NGINX_CONFIG" ]; then
    echo "❌ Конфигурация Nginx для $DOMAIN не найдена: $NGINX_CONFIG"
    exit 1
fi

echo "🔧 Настройка Nginx для $DOMAIN..."

# Создаем резервную копию
cp "$NGINX_CONFIG" "${NGINX_CONFIG}.backup.$(date +%Y%m%d_%H%M%S)"

# Проверяем, не добавлена ли уже авторизация
if grep -q "auth_request /auth/check" "$NGINX_CONFIG"; then
    echo "⚠️  Авторизация уже настроена для $DOMAIN"
    exit 0
fi

# Добавляем конфигурацию авторизации
cat >> "$NGINX_CONFIG" << 'EOF'

    # Авторизация через auth_service
    location = /auth/check {
        internal;
        proxy_pass http://localhost:9000/auth/check;
        proxy_pass_request_body off;
        proxy_set_header Content-Length "";
        proxy_set_header X-Original-URI $request_uri;
        proxy_set_header X-Original-Method $request_method;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /auth/ {
        proxy_pass http://localhost:9000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cookie_path / /;
    }

    location /api/admin/ {
        proxy_pass http://localhost:9000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cookie_path / /;
    }

    location @auth_required {
        return 302 https://$host/auth/login?redirect=$request_uri;
    }
EOF

# Модифицируем основной location для добавления auth_request
# Это требует более сложной логики, поэтому делаем вручную
echo ""
echo "⚠️  ВАЖНО: Необходимо вручную добавить в блок location / следующее:"
echo ""
echo "    auth_request /auth/check;"
echo "    error_page 401 = @auth_required;"
echo ""
echo "Пример:"
echo "    location / {"
echo "        auth_request /auth/check;"
echo "        error_page 401 = @auth_required;"
echo "        # ваш существующий код (proxy_pass, try_files и т.д.)"
echo "    }"
echo ""

# Проверка конфигурации
if nginx -t; then
    echo "✅ Конфигурация Nginx валидна"
    echo "🔄 Перезагрузите Nginx: sudo systemctl reload nginx"
else
    echo "❌ Ошибка в конфигурации Nginx"
    echo "Восстановите из резервной копии если необходимо"
    exit 1
fi

