FROM python:3.11-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    DISPLAY=:99 \
    PYTHONUNBUFFERED=1 \
    BROWSER_PROFILE_DIR=/browser-data/profile \
    BROWSER_EXECUTABLE_PATH=/usr/bin/chromium

RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium xvfb x11-utils fluxbox x11vnc novnc websockify \
    fonts-liberation fonts-noto-color-emoji ca-certificates dbus-x11 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY browser-agent/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app /app/app
COPY browser-agent/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8010 6080
ENTRYPOINT ["/entrypoint.sh"]
