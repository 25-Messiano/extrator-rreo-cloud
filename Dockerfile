FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TESSERACT_LANG=por+eng
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    tesseract-ocr \
    tesseract-ocr-por \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt
COPY . .
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD-SHELL python -c "import os,urllib.request; urllib.request.urlopen('http://localhost:%s/_stcore/health' % os.getenv('PORT','8501'), timeout=5)" || exit 1
CMD ["sh", "-c", "streamlit run app.py --server.address=0.0.0.0 --server.port=${PORT:-8501} --server.headless=true"]
