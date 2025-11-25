#!/bin/bash

# Скрипт для пересборки и перезапуска Docker контейнеров в режиме разработки

echo "🐳 Пересборка и перезапуск Docker контейнеров (DEV режим)..."

# Проверка наличия .env файла
if [ ! -f ".env" ]; then
    echo "⚠️  Внимание: файл .env не найден!"
    echo "Создайте .env файл с необходимыми переменными окружения"
    exit 1
fi

# Остановка и удаление старых контейнеров
echo "🛑 Остановка старых контейнеров..."
docker-compose -f docker-compose.new-dev.yml down

# Сборка новых образов
echo "🔨 Сборка backend образа..."
docker-compose -f docker-compose.new-dev.yml build --no-cache backend

# Запуск контейнеров
echo "🚀 Запуск контейнеров..."
docker-compose -f docker-compose.new-dev.yml up -d

# Проверка статуса
echo ""
echo "📊 Статус контейнеров:"
docker-compose -f docker-compose.new-dev.yml ps

echo ""
echo "✅ Готово!"
echo ""
echo "🌐 Приложение доступно по адресам:"
echo "   Frontend: http://localhost:3000"
echo "   Backend:  http://localhost:8000"
echo ""
echo "📝 Просмотр логов:"
echo "   Backend:  docker-compose -f docker-compose.new-dev.yml logs -f backend"
echo "   Frontend: docker-compose -f docker-compose.new-dev.yml logs -f frontend"
echo ""
echo "🛑 Остановка:"
echo "   docker-compose -f docker-compose.new-dev.yml down"

