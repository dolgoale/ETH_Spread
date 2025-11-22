# Централизованная система авторизации на сервере

## Архитектура

Авторизация вынесена на уровень сервера и управляется централизованно через Nginx и отдельный сервис `auth_service`.

```
┌─────────────────────────────────────────────────────────┐
│                    Nginx (Reverse Proxy)                │
│  - Маршрутизация запросов                               │
│  - Централизованная авторизация через auth_request      │
└──────────────────┬──────────────────────────────────────┘
                   │
        ┌──────────┴──────────┐
        │                     │
┌───────▼────────┐   ┌────────▼─────────┐
│  auth_service  │   │  Проекты         │
│  (порт 9000)   │   │  - ETH_Spread    │
│                │   │  - Другие...    │
└────────────────┘   └──────────────────┘
```

## Расположение на сервере

- **auth_service**: `/root/auth_service/`
- **Проекты**: `/root/{project_name}/`

## Управление авторизацией

### Добавление нового проекта

1. Создайте конфигурацию Nginx для нового домена/поддомена
2. Добавьте блоки авторизации из `auth_service/nginx_auth_config.conf`
3. Настройте `proxy_pass` на порт вашего проекта
4. Добавьте пользователей через админ-панель: `https://aadolgov.com/admin`

### Управление пользователями

Админ-панель доступна по адресу: `https://aadolgov.com/admin`

Через API:
```bash
# Добавить пользователя к домену
curl -X POST https://aadolgov.com/api/admin/domains/{domain}/users \
  -H "Cookie: session=..." \
  -d '{"user_identifier": "dolgoal"}'

# Удалить пользователя
curl -X DELETE https://aadolgov.com/api/admin/domains/{domain}/users/{user}
```

## Конфигурация Nginx

Для каждого проекта добавьте в конфигурацию Nginx:

```nginx
# Проверка авторизации
location = /auth/check {
    internal;
    proxy_pass http://127.0.0.1:9000/auth/check;
    proxy_pass_request_body off;
    proxy_set_header Content-Length "";
    proxy_set_header X-Original-URI $request_uri;
    proxy_set_header Host $host;
    proxy_set_header Cookie $http_cookie;
}

# Проксирование запросов к auth_service
location /auth/ {
    proxy_pass http://127.0.0.1:9000;
    proxy_set_header Host $host;
    proxy_set_header Cookie $http_cookie;
    proxy_redirect off;
    proxy_buffering off;
}

# Защита основного контента
location / {
    auth_request /auth/check;
    error_page 401 = @auth_required;
    
    proxy_pass http://127.0.0.1:8000;  # Порт вашего проекта
}

location @auth_required {
    return 302 https://$host/auth/login?redirect=$request_uri;
}
```

## Запуск auth_service

```bash
cd /root/auth_service
docker compose up -d
```

## Логи

```bash
# Логи auth_service
docker compose -f /root/auth_service/docker-compose.yml logs -f

# Логи Nginx
tail -f /var/log/nginx/{domain}.error.log
```

## Преимущества централизованной авторизации

1. ✅ Единая точка управления пользователями
2. ✅ Один сервис авторизации для всех проектов
3. ✅ Упрощенное управление доступом
4. ✅ Легкое добавление новых проектов
5. ✅ Централизованное логирование

