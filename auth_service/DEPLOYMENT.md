# Инструкция по развертыванию Auth Service

## Шаг 1: Создание OAuth приложения в Yandex

1. Перейдите на https://oauth.yandex.ru/
2. Нажмите "Зарегистрировать новое приложение"
3. Заполните форму:
   - **Название**: Auth Service для aadolgov.com
   - **Платформы**: Web-сервисы
   - **Redirect URI**: `https://aadolgov.com/auth/callback`
4. Сохраните **ID приложения** (Client ID) и **Пароль** (Client Secret)

## Шаг 2: Получение вашего Yandex ID

1. Перейдите на https://yandex.ru/support/id/profile.html
2. Ваш Yandex ID будет указан в URL или в настройках профиля
3. Или используйте API: после авторизации через OAuth, ваш ID будет в ответе

## Шаг 3: Настройка на сервере

### 3.1. Клонирование/копирование проекта

```bash
cd /root
git clone <your-repo> auth_service
# или скопируйте папку auth_service на сервер
cd auth_service
```

### 3.2. Создание .env файла

```bash
cp .env.example .env
nano .env
```

Заполните следующие параметры:

```env
YANDEX_CLIENT_ID=ваш_client_id_из_шага_1
YANDEX_CLIENT_SECRET=ваш_client_secret_из_шага_1
YANDEX_REDIRECT_URI=https://aadolgov.com/auth/callback

# Сгенерируйте случайный секретный ключ:
# python3 -c "import secrets; print(secrets.token_urlsafe(32))"
SECRET_KEY=ваш_случайный_секретный_ключ

ADMIN_YANDEX_ID=ваш_yandex_id_из_шага_2
```

### 3.3. Запуск сервиса

```bash
chmod +x deploy.sh
./deploy.sh
```

Проверьте, что сервис запущен:

```bash
curl http://localhost:9000/health
# Должен вернуть: {"status":"ok"}
```

## Шаг 4: Настройка Nginx

### 4.1. Для основного домена aadolgov.com

Отредактируйте `/etc/nginx/sites-available/aadolgov.com`:

```nginx
server {
    server_name aadolgov.com www.aadolgov.com;
    
    # ... существующие настройки SSL ...
    
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

    # Защита основного контента
    location / {
        auth_request /auth/check;
        error_page 401 = @auth_required;
        
        root /var/www/aadolgov.com;
        index index.html index.htm;
        try_files $uri $uri/ =404;
    }
}
```

### 4.2. Для поддомена BBSpreads.aadolgov.com

Отредактируйте `/etc/nginx/sites-available/BBSpreads.aadolgov.com`:

```nginx
server {
    server_name BBSpreads.aadolgov.com;
    
    # ... существующие настройки SSL ...
    
    # Авторизация через auth_service (те же блоки что выше)
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

    # Защита основного контента
    location / {
        auth_request /auth/check;
        error_page 401 = @auth_required;
        
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

### 4.3. Проверка и перезагрузка Nginx

```bash
# Проверка конфигурации
nginx -t

# Перезагрузка
systemctl reload nginx
```

## Шаг 5: Добавление пользователей

### 5.1. Через админ-панель

1. Откройте в браузере: `https://aadolgov.com/admin`
2. Войдите через Yandex ID (должен быть указан как ADMIN_YANDEX_ID)
3. Добавьте пользователей к нужным доменам

### 5.2. Через API

```bash
# Добавить пользователя к домену
curl -X POST "https://aadolgov.com/api/admin/domains/aadolgov.com/users/YANDEX_ID" \
  -H "Cookie: auth_session=YOUR_SESSION_TOKEN"

# Получить список пользователей домена
curl "https://aadolgov.com/api/admin/domains/aadolgov.com/users" \
  -H "Cookie: auth_session=YOUR_SESSION_TOKEN"
```

### 5.3. Прямое редактирование базы данных

База данных находится в `/root/auth_service/data/users_db.json`:

```json
{
  "domains": {
    "aadolgov.com": {
      "users": ["yandex_id_1", "yandex_id_2"],
      "description": "Основной домен"
    },
    "BBSpreads.aadolgov.com": {
      "users": ["yandex_id_3"],
      "description": "Поддомен для BBSpreads"
    }
  }
}
```

После редактирования перезапустите контейнер:

```bash
cd /root/auth_service
docker compose restart
```

## Шаг 6: Проверка работы

1. Откройте `https://aadolgov.com` - должно перенаправить на авторизацию
2. Войдите через Yandex ID
3. Если ваш ID в списке пользователей - будет доступ
4. Если нет - увидите сообщение "Доступ запрещен"

## Устранение неполадок

### Сервис не запускается

```bash
cd /root/auth_service
docker compose logs
```

### Ошибка авторизации

Проверьте:
- Правильность YANDEX_CLIENT_ID и YANDEX_CLIENT_SECRET
- Redirect URI в Yandex OAuth совпадает с YANDEX_REDIRECT_URI в .env
- SSL сертификат валиден

### Пользователь не может войти

1. Проверьте, что Yandex ID пользователя добавлен в базу данных
2. Проверьте логи: `docker compose logs -f`
3. Проверьте cookie в браузере (должна быть `auth_session`)

### Nginx возвращает 502

Проверьте, что auth_service запущен:

```bash
curl http://localhost:9000/health
```

Если не работает, проверьте логи:

```bash
cd /root/auth_service
docker compose logs
```

