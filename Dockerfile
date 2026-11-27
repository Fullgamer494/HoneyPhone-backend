FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production

WORKDIR /app

COPY pyproject.toml alembic.ini LICENSE ./
COPY alembic ./alembic
COPY src ./src

RUN pip install --no-cache-dir . \
    && useradd --system --uid 10001 --create-home honeyphone

USER 10001:10001

EXPOSE 8000

CMD ["sh", "-c", "alembic -c /app/alembic.ini upgrade head && uvicorn honeyphone.main:app --app-dir /app/src --host 0.0.0.0 --port 8000"]
