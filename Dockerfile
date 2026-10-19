FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    SORA_SESSION_DB_PATH=/tmp/sora_sessions.db

WORKDIR /app

# Create non-root runtime user
RUN groupadd -r sora && useradd -r -g sora sora

COPY requirements.txt pyproject.toml README.md ./
COPY sora_agent ./sora_agent
COPY app.py ./app.py
COPY tests ./tests

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e . && \
    chown -R sora:sora /app

USER sora

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
