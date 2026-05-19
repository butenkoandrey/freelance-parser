# --- Этап 1: Сборка зависимостей Python ---
FROM python:3.10-slim-bullseye AS builder
WORKDIR /app
# Копируем файл с зависимостями
COPY requirements.txt .
# Устанавливаем Python-пакеты в отдельную папку
RUN pip install --user --no-cache-dir -r requirements.txt

# --- Этап 2: Финальный образ ---
FROM python:3.10-slim-bullseye
WORKDIR /app
# Устанавливаем Java и Chrome для FlareSolverr
# Java требуется для работы js2py (одного из движков cloudscraper)
RUN apt-get update && apt-get install -y wget gnupg unzip curl openjdk-17-jre-headless \
    && wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list \
    && apt-get update && apt-get install -y google-chrome-stable \
    && apt-get clean && rm -rf /var/lib/apt/lists/*
# Копируем установленные Python-пакеты из предыдущего этапа
COPY --from=builder /root/.local /root/.local
# Копируем код приложения
COPY . .
# Устанавливаем FlareSolverr из официального Docker-образа
# Здесь используется синтаксис --from для копирования бинарного файла FlareSolverr
COPY --from=flaresolverr/flaresolverr:latest /app/flaresolverr /app/flaresolverr
# Делаем порт вашего Flask-приложения и порт FlareSolverr доступными
EXPOSE 10000 8191
# Устанавливаем переменную PATH для корректной работы Python-пакетов
ENV PATH=/root/.local/bin:$PATH
# Создаем скрипт для одновременного запуска двух сервисов
RUN echo '#!/bin/bash\n\
# Запускаем FlareSolverr в фоновом режиме и сохраняем его PID\n\
/app/flaresolverr &\n\
FLARE_PID=$!\n\
echo "FlareSolverr started with PID: $FLARE_PID"\n\
# Небольшая пауза, чтобы FlareSolverr успел инициализироваться\n\
sleep 5\n\
# Запускаем наше Gunicorn приложение (в нем мы будем использовать FLARESOLVERR_URL)\n\
gunicorn app:app --bind 0.0.0.0:10000\n\
' > /entrypoint.sh && chmod +x /entrypoint.sh
# Задаем команду по умолчанию при запуске контейнера
CMD ["/entrypoint.sh"]
