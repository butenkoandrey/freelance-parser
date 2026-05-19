# ---- Этап 1: сборка зависимостей Python ----
FROM python:3.10-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# ---- Этап 2: финальный образ ----
FROM python:3.10-slim
WORKDIR /app

# Устанавливаем Chrome, Node.js, Java и утилиты
RUN apt-get update && apt-get install -y \
    wget gnupg unzip curl \
    openjdk-17-jre-headless \
    nodejs \
    && wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list \
    && apt-get update && apt-get install -y google-chrome-stable \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Копируем Python-пакеты из builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Копируем код приложения
COPY . .

# Скачиваем FlareSolverr (бинарник для Linux x64) и распаковываем
RUN curl -L https://github.com/FlareSolverr/FlareSolverr/releases/download/v3.3.10/flaresolverr_linux_x64.tar.gz -o /tmp/flaresolverr.tar.gz \
    && tar -xzf /tmp/flaresolverr.tar.gz -C /app \
    && chmod +x /app/flaresolverr \
    && rm /tmp/flaresolverr.tar.gz

# Создаём entrypoint-скрипт для запуска обоих сервисов
RUN printf '#!/bin/bash\n\
# Запускаем FlareSolverr в фоне\n\
/app/flaresolverr --port=8191 --host=0.0.0.0 &\n\
FLARE_PID=$!\n\
echo "FlareSolverr запущен с PID $FLARE_PID"\n\
# Ждём инициализации\n\
sleep 8\n\
# Запускаем Gunicorn\n\
gunicorn app:app --bind 0.0.0.0:10000\n\
' > /entrypoint.sh && chmod +x /entrypoint.sh

EXPOSE 10000 8191
CMD ["/entrypoint.sh"]
