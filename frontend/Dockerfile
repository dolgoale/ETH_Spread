# Multi-stage build для Frontend

# Stage 1: Build
FROM node:20-alpine AS builder

WORKDIR /app

# Копирование package.json и package-lock.json
COPY package*.json ./

# Установка зависимостей
RUN npm install

# Копирование исходного кода
COPY . .

# Установка переменных окружения для production сборки
ENV NODE_ENV=production
ENV REACT_APP_API_URL=""
ENV REACT_APP_WS_URL=""

# Сборка приложения
RUN npm run build

# Stage 2: Production
FROM nginx:alpine

# Копирование собранного приложения
COPY --from=builder /app/build /usr/share/nginx/html

# Копирование конфигурации nginx
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Открытие порта
EXPOSE 80

# Запуск nginx
CMD ["nginx", "-g", "daemon off;"]

