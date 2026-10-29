FROM python:3.12-slim-bookworm

ARG CHROME_VERSION=156.0.8078.73
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CHROME_BINARY=/opt/chrome/chrome-linux64/chrome \
    CHROMEDRIVER=/usr/local/bin/chromedriver \
    PORT=7000

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates fonts-liberation libasound2 libatk-bridge2.0-0 libatk1.0-0 \
    libcairo2 libcups2 libdbus-1-3 libdrm2 libexpat1 libgbm1 libglib2.0-0 libgtk-3-0 libnspr4 \
    libnss3 libpango-1.0-0 libvulkan1 libx11-6 libxcb1 libxcomposite1 \
    libxdamage1 libxext6 libxfixes3 libxkbcommon0 libxrandr2 \
    && rm -rf /var/lib/apt/lists/*
COPY tools/install_browser.py /tmp/install_browser.py
RUN python /tmp/install_browser.py --version "$CHROME_VERSION" \
    && rm /tmp/install_browser.py \
    && "$CHROME_BINARY" --version && chromedriver --version

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home app
COPY app.py scraper.py summarizer.py ./
COPY templates ./templates
USER app
EXPOSE 7000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7000/health', timeout=3)"
CMD ["gunicorn", "--bind", "0.0.0.0:7000", "--workers", "1", "--threads", "2", "--timeout", "120", "--access-logfile", "-", "app:app"]
