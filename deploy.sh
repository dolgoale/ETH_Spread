#!/bin/bash

# Скрипт для деплоя на удаленный сервер
# Использование: ./deploy.sh

set -e

echo "🚀 Начинаем деплой на удаленный сервер..."

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Проверяем, что мы в правильной директории
if [ ! -f "docker-compose.new.yml" ]; then
    echo -e "${RED}❌ Ошибка: docker-compose.new.yml не найден${NC}"
    echo "Запустите скрипт из корневой директории проекта"
    exit 1
fi

# Параметры сервера
SERVER="root@aadolgov.com"
PROJECT_DIR="/root/ETH_Spread"

echo -e "${YELLOW}📡 Подключаемся к серверу...${NC}"

# Выполняем команды на сервере
ssh $SERVER << 'ENDSSH'
set -e

echo "📂 Переходим в директорию проекта..."
cd /root/ETH_Spread

echo "🔄 Получаем последние изменения из Git..."
git pull origin main

echo "🛑 Останавливаем старые контейнеры..."
docker-compose -f docker-compose.new.yml down

echo "🏗️  Собираем новые образы..."
docker-compose -f docker-compose.new.yml build

echo "🚀 Запускаем контейнеры..."
docker-compose -f docker-compose.new.yml up -d

echo "⏳ Ожидаем запуска контейнеров..."
sleep 5

echo "📊 Проверяем статус контейнеров..."
docker-compose -f docker-compose.new.yml ps

echo "✅ Деплой завершен успешно!"
ENDSSH

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Деплой на сервер завершен успешно!${NC}"
    echo ""
    echo "🌐 Приложение доступно по адресу:"
    echo "   Frontend: http://bbspreads.aadolgov.com:8000"
    echo "   Backend API: http://bbspreads.aadolgov.com"
    echo ""
    echo "📝 Для просмотра логов на сервере:"
    echo "   ssh $SERVER 'cd $PROJECT_DIR && docker-compose -f docker-compose.new.yml logs -f'"
else
    echo -e "${RED}❌ Ошибка при деплое на сервер${NC}"
    exit 1
fi

