# Docker инструкции для ETH_Spread

## Описание

Этот проект настроен для работы в Docker контейнере, что позволяет:
- Изолированную среду разработки
- Единообразную работу на разных платформах
- Простое развертывание

## Требования

- Docker 20.10 или выше
- Docker Compose 2.0 или выше
- Файл `.env` с настройками (см. раздел Конфигурация)

## Структура Docker файлов

- `Dockerfile` - образ для разработки и продакшена
- `docker-compose.yml` - конфигурация для продакшена
- `docker-compose.dev.yml` - конфигурация для разработки (read-write монтирование)
- `.dockerignore` - файлы и директории, исключенные из контекста сборки

## Быстрый старт

### 1. Подготовка

Убедитесь, что у вас есть файл `.env` в корне проекта:

```bash
# Если файла .env нет, создайте его на основе .env.example
cp .env.example .env

# Отредактируйте .env файл и заполните необходимые переменные
# BYBIT_API_KEY, BYBIT_API_SECRET, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
```

### 2. Сборка образа

```bash
# Сборка образа
docker-compose build

# Или для разработки
docker-compose -f docker-compose.dev.yml build
```

### 3. Запуск контейнера

```bash
# Запуск в режиме продакшена
docker-compose up -d

# Запуск в режиме разработки (read-write монтирование)
docker-compose -f docker-compose.dev.yml up -d

# Запуск с выводом логов в консоль (без фона)
docker-compose up
```

### 4. Просмотр логов

```bash
# Логи контейнера
docker-compose logs -f eth-spread

# Последние 100 строк логов
docker-compose logs --tail=100 eth-spread

# Или для dev версии
docker-compose -f docker-compose.dev.yml logs -f eth-spread
```

### 5. Остановка контейнера

```bash
# Остановка
docker-compose down

# Остановка с удалением томов
docker-compose down -v

# Для dev версии
docker-compose -f docker-compose.dev.yml down
```

## Разработка в Docker

### Режим разработки (docker-compose.dev.yml)

Этот режим настроен для активной разработки:

- **Read-write монтирование** - изменения в коде на хосте сразу видны в контейнере
- **Переменная окружения `PYTHONUNBUFFERED=1`** - логи выводятся в реальном времени
- **Логи сохраняются** в `./logs` и `./eth_spread_monitor.log`

```bash
# Запуск в режиме разработки
docker-compose -f docker-compose.dev.yml up -d

# Просмотр логов в реальном времени
docker-compose -f docker-compose.dev.yml logs -f

# Перезапуск после изменений в requirements.txt
docker-compose -f docker-compose.dev.yml up -d --build
```

### Изменение кода

1. Измените код на хосте (например, в `src/`)
2. Перезапустите контейнер для применения изменений:

```bash
docker-compose -f docker-compose.dev.yml restart eth-spread
```

Или просто остановите и запустите снова:

```bash
docker-compose -f docker-compose.dev.yml down
docker-compose -f docker-compose.dev.yml up -d
```

### Установка новых зависимостей

Если вы добавили новые зависимости в `requirements.txt`:

1. Пересоберите образ:
```bash
docker-compose -f docker-compose.dev.yml build
```

2. Перезапустите контейнер:
```bash
docker-compose -f docker-compose.dev.yml up -d
```

## Доступ к приложению

После запуска контейнера приложение будет доступно:

- **Веб-интерфейс**: http://localhost:8000
- **API Config**: http://localhost:8000/api/config
- **API Data**: http://localhost:8000/api/data
- **WebSocket**: ws://localhost:8000/ws

## Работа с контейнером

### Выполнение команд в контейнере

```bash
# Войти в контейнер (bash)
docker-compose exec eth-spread bash

# Выполнить команду
docker-compose exec eth-spread python -c "import sys; print(sys.version)"

# Проверить установленные пакеты
docker-compose exec eth-spread pip list

# Просмотр переменных окружения
docker-compose exec eth-spread env
```

### Просмотр статуса контейнера

```bash
# Статус контейнеров
docker-compose ps

# Детальная информация
docker inspect eth-spread-app

# Использование ресурсов
docker stats eth-spread-app
```

## Отладка

### Проблемы с запуском

1. **Проверьте логи**:
```bash
docker-compose logs eth-spread
```

2. **Проверьте, что порт 8000 свободен**:
```bash
# На macOS/Linux
lsof -i :8000

# На Windows
netstat -ano | findstr :8000
```

3. **Проверьте файл .env**:
```bash
# Убедитесь, что файл существует и заполнен
cat .env
```

### Проблемы с переменными окружения

Убедитесь, что файл `.env` существует и содержит все необходимые переменные:

```bash
# Проверить переменные в контейнере
docker-compose exec eth-spread env | grep BYBIT
docker-compose exec eth-spread env | grep TELEGRAM
```

### Пересборка образа

Если возникают проблемы, попробуйте пересобрать образ без кеша:

```bash
docker-compose build --no-cache
docker-compose up -d
```

## Производственное развертывание

Для продакшена используйте `docker-compose.yml`:

```bash
# Сборка
docker-compose build

# Запуск
docker-compose up -d

# Проверка статуса
docker-compose ps

# Логи
docker-compose logs -f eth-spread
```

**Важные отличия продакшен версии**:
- Исходный код монтируется в режиме `read-only`
- Более строгие настройки безопасности
- Оптимизированные настройки логирования

## Полезные команды

```bash
# Очистка неиспользуемых образов и контейнеров
docker system prune -a

# Очистка только остановленных контейнеров
docker container prune

# Просмотр использования диска
docker system df

# Остановить все контейнеры проекта
docker-compose down

# Перезапустить конкретный сервис
docker-compose restart eth-spread
```

## Структура томов

Следующие директории и файлы монтируются из хоста в контейнер:

- `./src` → `/app/src` - исходный код
- `./config.py` → `/app/config.py` - конфигурация
- `./main.py` → `/app/main.py` - точка входа
- `./logs` → `/app/logs` - директория логов
- `./config.json` → `/app/config.json` - динамическая конфигурация
- `./eth_spread_monitor.log` → `/app/eth_spread_monitor.log` - файл логов

## Troubleshooting

### Контейнер не запускается

1. Проверьте логи: `docker-compose logs eth-spread`
2. Убедитесь, что `.env` файл существует и корректно заполнен
3. Проверьте, что порт 8000 не занят другим приложением

### Веб-интерфейс не доступен

1. Проверьте, что контейнер запущен: `docker-compose ps`
2. Проверьте логи контейнера
3. Убедитесь, что порт правильно проброшен: `docker-compose port eth-spread 8000`

### Изменения в коде не применяются

1. Убедитесь, что вы используете `docker-compose.dev.yml` для разработки
2. Перезапустите контейнер: `docker-compose restart eth-spread`
3. Проверьте, что файлы правильно смонтированы: `docker-compose exec eth-spread ls -la /app/src`

## Дополнительная информация

- Подробная архитектура проекта: `ARCHITECTURE.md`
- Основная документация: `README.md`
- Конфигурация: `.env` и `config.json`

