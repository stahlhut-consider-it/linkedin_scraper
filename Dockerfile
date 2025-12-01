FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000 \
    DISPLAY=:99 \
    CHROME_BIN=/usr/bin/chromium

# System dependencies for Chromium + Xvfb
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      chromium \
      imagemagick \
      xvfb \
      xauth \
      libnss3 \
      libatk1.0-0 \
      libatk-bridge2.0-0 \
      libdrm2 \
      libgbm1 \
      libasound2 \
      libxkbcommon0 \
      libxss1 \
      libxcomposite1 \
      libxdamage1 \
      libxrandr2 \
      libgtk-3-0 \
      fonts-liberation \
      ca-certificates \
      dumb-init && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x docker/entrypoint.sh docker/capture_screenshot.sh

EXPOSE 8000

ENTRYPOINT ["dumb-init", "--"]
CMD ["docker/entrypoint.sh"]
