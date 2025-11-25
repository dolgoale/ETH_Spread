#!/bin/bash

# Скрипт для запуска проекта в режиме разработки

echo "🚀 Запуск ETH Spread Monitor..."

# Проверка, что мы в корне проекта
if [ ! -d "backend" ] || [ ! -d "frontend" ]; then
    echo "❌ Ошибка: запустите скрипт из корня проекта"
    exit 1
fi

# Функция для остановки процессов при выходе
cleanup() {
    echo ""
    echo "🛑 Остановка серверов..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    exit 0
}

trap cleanup SIGINT SIGTERM

# Запуск Backend
echo "📦 Запуск Backend..."
cd backend
python main.py &
BACKEND_PID=$!
cd ..

# Ждем запуска backend
sleep 3

# Запуск Frontend
echo "🎨 Запуск Frontend..."
cd frontend
npm start &
FRONTEND_PID=$!
cd ..

echo ""
echo "✅ Серверы запущены!"
echo "   Backend:  http://localhost:8000"
echo "   Frontend: http://localhost:3000"
echo ""
echo "Нажмите Ctrl+C для остановки"

# Ждем завершения
wait




