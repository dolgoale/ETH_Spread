# Auth Service - Сервис авторизации через Yandex ID

Сервис авторизации для сайтов aadolgov.com и его поддоменов с поддержкой отдельных списков пользователей для каждого домена.

## Возможности

- Авторизация через Yandex ID (OAuth 2.0)
- Управление списками пользователей для каждого домена/поддомена
- Сессии с защитой от подделки
- API для управления пользователями (только для администратора)
- Интеграция с Nginx через auth_request

## Установка

### 1. Создание OAuth приложения в Yandex

1. Перейдите на https://oauth.yandex.ru/
2. Создайте новое приложение
3. Укажите Redirect URI: `https://aadolgov.com/auth/callback`
4. Сохраните Client ID и Client Secret

### 2. Настройка переменных окружения

Скопируйте `.env.example` в `.env` и заполните:

```bash
cp .env.example .env
```

Заполните следующие параметры:
- `YANDEX_CLIENT_ID` - ID приложения из Yandex OAuth
- `YANDEX_CLIENT_SECRET` - Secret приложения из Yandex OAuth
- `YANDEX_REDIRECT_URI` - URI для callback (обычно `https://aadolgov.com/auth/callback`)
- `SECRET_KEY` - Секретный ключ для подписи сессий (сгенерируйте случайную строку)
- `ADMIN_YANDEX_ID` - Ваш Yandex ID для доступа к админ-панели

### 3. Запуск через Docker

```bash
docker compose up -d
```

Сервис будет доступен на порту 9000.

## Использование

### Авторизация пользователя

Пользователь переходит на `/auth/login` на нужном домене. После авторизации через Yandex ID, пользователь будет перенаправлен обратно на домен с установленной сессией.

### Проверка авторизации

Для проверки авторизации используйте endpoint `/auth/check`:

```bash
curl https://aadolgov.com/auth/check
```

### Получение информации о пользователе

```bash
curl https://aadolgov.com/auth/user
```

### Выход

```bash
GET /auth/logout
```

## API для управления пользователями (только для администратора)

Все API требуют авторизации и прав администратора.

### Получить список всех доменов

```bash
GET /api/admin/domains
```

### Получить список пользователей домена

```bash
GET /api/admin/domains/{domain}/users
```

### Добавить пользователя к домену

```bash
POST /api/admin/domains/{domain}/users/{yandex_id}
```

### Удалить пользователя из домена

```bash
DELETE /api/admin/domains/{domain}/users/{yandex_id}
```

### Добавить новый домен

```bash
POST /api/admin/domains/{domain}
```

## Интеграция с Nginx

Для защиты сайтов через авторизацию, настройте Nginx с использованием `auth_request`:

```nginx
location / {
    auth_request /auth/check;
    auth_request_set $user $upstream_http_x_user;
    
    # Если не авторизован, перенаправляем на логин
    error_page 401 = @auth_required;
}

location @auth_required {
    return 302 https://$host/auth/login?redirect=$request_uri;
}

location = /auth/check {
    internal;
    proxy_pass http://localhost:9000/auth/check;
    proxy_pass_request_body off;
    proxy_set_header Content-Length "";
    proxy_set_header X-Original-URI $request_uri;
    proxy_set_header X-Original-Method $request_method;
    proxy_set_header Host $host;
}
```

## Структура базы данных

База данных хранится в `/app/data/users_db.json`:

```json
{
  "domains": {
    "aadolgov.com": {
      "users": ["yandex_id_1", "yandex_id_2"],
      "description": "Основной домен"
    },
    "bbspreads.aadolgov.com": {
      "users": ["yandex_id_3"],
      "description": "Поддомен для BBSpreads"
    }
  }
}
```

## Безопасность

- Сессии подписываются с использованием HMAC-SHA256
- Cookie установлены с флагами HttpOnly и Secure
- Проверка доступа пользователя к домену при каждой авторизации
- Админ-панель доступна только администратору

