# ---- Этап 1: сборка зависимостей Python ----
FROM python:3.10-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# ---- Этап 2: финальный образ ----
FROM python:3.10-slim
WORKDIR /app

# Копируем Python-пакеты из builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Копируем код приложения
COPY . .

# Устанавливаем необходимые системные пакеты
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        wget \
        gnupg \
        ca-certificates \
        unzip \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Установка Google Chrome
RUN curl -fsSL https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-linux-keyring.gpg && \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-linux-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends google-chrome-stable && \
    rm -rf /var/lib/apt/lists/*

# Скачиваем FlareSolverr
RUN curl -L https://github.com/FlareSolverr/FlareSolverr/releases/download/v3.3.10/flaresolverr_linux_x64.tar.gz -o /tmp/flaresolverr.tar.gz && \
    tar -xzf /tmp/flaresolverr.tar.gz -C /app && \
    chmod +x /app/flaresolverr && \
    rm /tmp/flaresolverr.tar.gz

# Создаём entrypoint-скрипт
RUN printf '#!/bin/bash\n\
/app/flaresolverr --port=8191 --host=0.0.0.0 &\n\
FLARE_PID=$!\n\
echo "FlareSolverr запущен с PID $FLARE_PID"\n\
sleep 8\n\
gunicorn app:app --bind 0.0.0.0:10000\n\
' > /entrypoint.sh && chmod +x /entrypoint.sh

EXPOSE 10000 8191
CMD ["/entrypoint.sh"]
