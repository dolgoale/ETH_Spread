# ETH Spread Monitor - Новая архитектура (Backend + Frontend)

## Структура проекта

Проект теперь разделен на два независимых приложения:

- **backend/** - Python FastAPI сервер
- **frontend/** - React + TypeScript + Material-UI приложение

## Backend

### Установка зависимостей

```bash
cd backend
pip install -r requirements.txt
```

### Настройка

Создайте файл `.env` в корне папки `backend`:

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

### Запуск

```bash
cd backend
python main.py
```

Backend будет доступен на http://localhost:8000

## Frontend

### Установка зависимостей

```bash
cd frontend
npm install
```

### Настройка

Создайте файл `.env` в корне папки `frontend`:

```env
REACT_APP_API_URL=http://localhost:8000
```

### Запуск в режиме разработки

```bash
cd frontend
npm start
```

Frontend откроется на http://localhost:3000

### Сборка для продакшена

```bash
cd frontend
npm run build
```

Собранные файлы будут в папке `frontend/build/`

## Возможности

### Frontend

- **Мониторинг** - главная страница с таблицей активов (ETH, BTC, SOL)
  - Real-time обновление данных через WebSocket
  - Отображение спредов, funding rate, доходности
  - Цветовая индикация прибыльности
  
- **Настройки** - страница для изменения параметров мониторинга
  - Порог спреда
  - История funding rate
  - Интервал мониторинга
  - Порог доходности
  - Капитал и плечо

### Backend API

- `GET /api/all-instruments` - данные по всем трем активам (ETH, BTC, SOL)
- `GET /api/instruments/{instrument}` - данные по конкретному активу
- `GET /api/config` - получить конфигурацию
- `PUT /api/config` - обновить конфигурацию
- `WS /ws/instruments` - WebSocket для real-time обновлений

## Технологии

### Backend
- Python 3.8+
- FastAPI
- WebSocket
- ByBit API (pybit)
- Telegram Bot API

### Frontend
- React 19
- TypeScript
- Material-UI (MUI)
- React Router
- Axios
- WebSocket

## Разработка

### Backend

Backend поддерживает горячую перезагрузку конфигурации через веб-интерфейс.

### Frontend

В режиме разработки используется прокси для избежания проблем с CORS:
- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- Прокси настроен в `package.json`

## Деплой

### Backend

1. Установите зависимости
2. Настройте `.env`
3. Запустите `python main.py`

### Frontend

1. Соберите проект: `npm run build`
2. Разместите содержимое `build/` на веб-сервере (nginx, Apache)
3. Настройте переменную окружения `REACT_APP_API_URL` для продакшена

### Docker (опционально)

Можно использовать существующие Docker файлы из корня проекта, обновив пути к backend.

