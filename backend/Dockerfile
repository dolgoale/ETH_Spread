# Dockerfile для Backend
FROM python:3.11-slim

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Установка рабочей директории
WORKDIR /app

# Копирование файла зависимостей
COPY requirements.txt .

# Установка Python зависимостей
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копирование исходного кода проекта
COPY . .

# Создание директории для логов
RUN mkdir -p /app/logs

# Открытие порта для веб-сервера
EXPOSE 8000

# Команда по умолчанию
CMD ["python", "main.py"]




