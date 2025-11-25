# Docker Setup - Новая архитектура

## Структура

Проект теперь состоит из двух Docker контейнеров:

1. **Backend** (`eth-spread-backend`) - Python FastAPI сервер на порту 8000
2. **Frontend** (`eth-spread-frontend`) - React приложение через Nginx на порту 80

## Быстрый запуск

### Продакшен режим

```bash
# Пересборка и запуск
./docker-rebuild.sh

# Или вручную
docker-compose -f docker-compose.new.yml build --no-cache
docker-compose -f docker-compose.new.yml up -d
```

Приложение будет доступно:
- **Frontend**: http://localhost (порт 80)
- **Backend API**: http://localhost:8000

### Режим разработки

```bash
# Пересборка и запуск
./docker-rebuild-dev.sh

# Или вручную
docker-compose -f docker-compose.new-dev.yml build --no-cache
docker-compose -f docker-compose.new-dev.yml up -d
```

Приложение будет доступно:
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000

## Управление контейнерами

### Просмотр статуса

```bash
docker-compose -f docker-compose.new.yml ps
```

### Просмотр логов

```bash
# Все логи
docker-compose -f docker-compose.new.yml logs -f

# Только backend
docker-compose -f docker-compose.new.yml logs -f backend

# Только frontend
docker-compose -f docker-compose.new.yml logs -f frontend
```

### Остановка

```bash
docker-compose -f docker-compose.new.yml down
```

### Перезапуск

```bash
docker-compose -f docker-compose.new.yml restart
```

### Полная очистка (с удалением образов)

```bash
docker-compose -f docker-compose.new.yml down --rmi all --volumes
```

## Конфигурация

### Переменные окружения

Создайте файл `.env` в корне проекта:

```env
# ByBit API
BYBIT_API_KEY=your_api_key
BYBIT_API_SECRET=your_api_secret
BYBIT_TESTNET=false

# Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Monitoring
SPREAD_THRESHOLD_PERCENT=0.5
FUNDING_RATE_HISTORY_DAYS=7
MONITORING_INTERVAL_SECONDS=5
RETURN_ON_CAPITAL_THRESHOLD=50.0
CAPITAL_USDT=50000
LEVERAGE=20

# Web Server
WEB_SERVER_HOST=0.0.0.0
WEB_SERVER_PORT=8000

# Symbols
PERPETUAL_SYMBOL=ETHUSDT
```

### Volumes

**Продакшен** (`docker-compose.new.yml`):
- `./logs:/app/logs` - логи backend

**Разработка** (`docker-compose.new-dev.yml`):
- `./backend/src:/app/src` - исходный код backend (hot-reload)
- `./frontend:/app` - исходный код frontend (hot-reload)
- `./logs:/app/logs` - логи

## Архитектура

```
┌─────────────────────────────────────────┐
│         Nginx (Frontend)                │
│         Port 80                         │
│  ┌──────────────────────────────────┐  │
│  │  React App (Static Files)        │  │
│  │  - Dashboard                     │  │
│  │  - Settings                      │  │
│  └──────────────────────────────────┘  │
│                                         │
│  Proxy /api/* → Backend:8000           │
│  Proxy /ws/*  → Backend:8000 (WebSocket)│
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│      Python Backend (FastAPI)           │
│      Port 8000                          │
│  ┌──────────────────────────────────┐  │
│  │  REST API                        │  │
│  │  - /api/all-instruments          │  │
│  │  - /api/config                   │  │
│  │  WebSocket                       │  │
│  │  - /ws/instruments               │  │
│  └──────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

## Особенности

### Frontend (Nginx)

- Статические файлы React приложения
- Gzip компрессия
- Кэширование статики (1 год)
- Проксирование API запросов к backend
- Поддержка React Router (SPA)
- WebSocket проксирование

### Backend (Python)

- FastAPI сервер
- WebSocket для real-time обновлений
- Мониторинг спредов ETH, BTC, SOL
- Telegram уведомления
- Healthcheck endpoint

## Healthcheck

Оба контейнера имеют healthcheck:

**Backend**: `curl -f http://localhost:8000/api/config`
**Frontend**: `curl -f http://localhost/`

Frontend запускается только после того, как backend станет healthy.

## Troubleshooting

### Backend не запускается

```bash
# Проверить логи
docker-compose -f docker-compose.new.yml logs backend

# Проверить переменные окружения
docker-compose -f docker-compose.new.yml exec backend env
```

### Frontend показывает ошибки API

```bash
# Проверить, что backend запущен
docker-compose -f docker-compose.new.yml ps

# Проверить логи nginx
docker-compose -f docker-compose.new.yml logs frontend

# Проверить конфигурацию nginx
docker-compose -f docker-compose.new.yml exec frontend cat /etc/nginx/conf.d/default.conf
```

### Пересборка после изменений

```bash
# Остановить контейнеры
docker-compose -f docker-compose.new.yml down

# Пересобрать с очисткой кэша
docker-compose -f docker-compose.new.yml build --no-cache

# Запустить
docker-compose -f docker-compose.new.yml up -d
```

## Миграция со старой версии

1. Остановите старый контейнер:
   ```bash
   docker-compose down
   ```

2. Запустите новую версию:
   ```bash
   ./docker-rebuild.sh
   ```

3. Откройте http://localhost в браузере

Старые файлы (`main.py`, `src/` в корне) больше не используются.
Новые файлы находятся в `backend/` и `frontend/`.




