# Архитектура развертывания проекта ETH_Spread

## Общая концепция

Проект использует следующую архитектуру развертывания:

```
Локальная разработка (Docker)
    ↓
Git репозиторий (GitHub)
    ↓
Автоматическое развертывание
    ↓
Удаленный сервер (Docker в продакшене)
```

## Компоненты архитектуры

### 1. Локальная разработка

**Местоположение**: Локальный компьютер

**Инструменты**:
- Docker Desktop
- Docker Compose (режим разработки)

**Файлы конфигурации**:
- `docker-compose.dev.yml` - конфигурация для разработки
- `Dockerfile` - образ приложения

**Особенности**:
- Код монтируется в контейнер (read-write)
- Изменения видны сразу без пересборки образа
- Логи доступны локально

**Команды**:
```bash
# Запуск в режиме разработки
docker-compose -f docker-compose.dev.yml up -d

# Просмотр логов
docker-compose -f docker-compose.dev.yml logs -f

# Остановка
docker-compose -f docker-compose.dev.yml down
```

### 2. Git репозиторий

**Местоположение**: GitHub (https://github.com/dolgoale/ETH_Spread.git)

**Ветка**: `main`

**Процесс работы**:
1. Изменения кода на локальной машине
2. Коммит изменений: `git commit -m "описание"`
3. Отправка в GitHub: `git push origin main`
4. Автоматическое развертывание на сервере

### 3. Удаленный сервер (Продакшен)

**Сервер**: 194.87.46.14 (aadolgov)

**Компоненты**:
- Docker Engine 29.0.2
- Docker Compose v2.40.3
- Nginx (reverse proxy)
- Webhook сервер для автоматического развертывания

**Файлы конфигурации**:
- `docker-compose.prod.yml` - конфигурация для продакшена
- `/root/ETH_Spread/deploy.sh` - скрипт автоматического развертывания
- `/root/webhook-server.py` - webhook сервер для GitHub

## Процесс развертывания

### Автоматическое развертывание (через Webhook)

1. **Push в Git**: Вы отправляете изменения в GitHub
2. **GitHub Webhook**: GitHub отправляет POST запрос на webhook сервер
3. **Webhook обработка**: Сервер проверяет, что это push в main ветку
4. **Автоматический деплой**: Запускается скрипт `/root/ETH_Spread/deploy.sh`
5. **Обновление кода**: Скрипт обновляет код из Git
6. **Сборка образа**: Docker пересобирает образ с новым кодом
7. **Перезапуск**: Контейнер перезапускается с новым образом

### Ручное развертывание

На удаленном сервере можно запустить развертывание вручную:

```bash
ssh aadolgov
cd /root/ETH_Spread
./deploy.sh
```

## Настройка файлов

### Локально

**docker-compose.dev.yml** - для разработки:
- Монтирование кода (read-write)
- Переменные окружения из `.env`
- Логи на хосте

### На сервере (продакшен)

**docker-compose.prod.yml** - для продакшена:
- Код внутри Docker образа (без монтирования)
- Переменные окружения из `.env`
- Только данные монтируются (логи, config.json)

## Файл .env

Файл `.env` должен быть настроен на сервере в `/root/ETH_Spread/.env`:

```env
# ByBit API Configuration
BYBIT_API_KEY=your_api_key_here
BYBIT_API_SECRET=your_api_secret_here
BYBIT_TESTNET=false

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# Monitoring Configuration
SPREAD_THRESHOLD_PERCENT=0.5
FUNDING_RATE_HISTORY_DAYS=30
MONITORING_INTERVAL_SECONDS=5

# Web Server Configuration
WEB_SERVER_HOST=0.0.0.0
WEB_SERVER_PORT=8000

# Symbol Configuration
PERPETUAL_SYMBOL=ETHUSDT
FUTURES_SYMBOLS=ETHUSDT-26DEC25,ETHUSDT-26JUN26,ETHUSDT-25SEP26
```

**Важно**: Файл `.env` НЕ коммитится в Git (в `.gitignore`), поэтому его нужно создать вручную на сервере.

## Webhook настройка

### Настройка в GitHub

1. Перейдите в настройки репозитория: Settings → Webhooks
2. Добавьте новый webhook:
   - Payload URL: `http://webhook.aadolgov.com/webhook/deploy`
   - Content type: `application/json`
   - Secret: (установите секретный ключ)
   - Events: `Just the push event`
   - Active: ✓

### Настройка на сервере

1. Обновите секретный ключ в `/etc/systemd/system/webhook-deploy.service`
2. Перезапустите сервис: `systemctl restart webhook-deploy`

## Ручное развертывание

Если webhook не настроен или нужно развернуть вручную:

```bash
# На удаленном сервере
ssh aadolgov
cd /root/ETH_Spread
git pull origin main
./deploy.sh
```

## Мониторинг

### Логи развертывания

```bash
# Логи скрипта развертывания
ssh aadolgov "tail -f /root/ETH_Spread/deploy.log"

# Логи Docker контейнера
ssh aadolgov "docker compose -f /root/ETH_Spread/docker-compose.prod.yml logs -f"

# Логи webhook сервера
ssh aadolgov "journalctl -u webhook-deploy -f"
```

### Статус контейнеров

```bash
ssh aadolgov "cd /root/ETH_Spread && docker compose -f docker-compose.prod.yml ps"
```

## Преимущества архитектуры

1. **Изоляция**: Разработка и продакшен изолированы
2. **Автоматизация**: Развертывание происходит автоматически при push в Git
3. **Версионирование**: Все изменения отслеживаются в Git
4. **Безопасность**: Код в продакшене находится внутри Docker образа
5. **Откат**: Легко вернуться к предыдущей версии через Git

## Следующие шаги

1. Настроить файл `.env` на сервере
2. Настроить GitHub webhook
3. Протестировать процесс развертывания
4. Запустить проект в продакшене

