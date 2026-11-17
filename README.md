# HoneyPhone API

API FastAPI 0.3.0 con Pydantic, SQLAlchemy 2, psycopg 3 y Alembic. Este repositorio contiene el servicio, PostgreSQL local, el contrato OpenAPI y herramientas de desarrollo.

## Preparar entorno

Desde la raíz de este repositorio:

    cp .env.example .env
    python3 -m venv .venv
    .venv/bin/pip install -e '.[test]'

Si ya existe .env, no lo sobrescribas. Inicia PostgreSQL y aplica las migraciones:

    docker compose --env-file .env -f infra/compose.yaml up -d db
    .venv/bin/alembic -c alembic.ini upgrade head

El servicio PostgreSQL usa 127.0.0.1:5433.

## Iniciar API

    .venv/bin/uvicorn honeyphone.main:app --app-dir src --host 127.0.0.1 --port 8000

Swagger está en http://127.0.0.1:8000/docs y el estado en http://127.0.0.1:8000/healthz.

## Rutas P0

- GET /healthz
- POST /api/v1/network-checks
- GET /api/v1/network-checks con filtro, cursor y límite hasta 50
- GET /api/v1/network-checks/{check_id}
- DELETE /api/v1/network-checks/{check_id}

POST conserva idempotencia por check_id. Reutilizar el ID con contenido distinto produce conflicto. contracts/openapi.yaml contiene el contrato operativo y los ejemplos. Ejecuta scripts/sync-openapi.py al cambiar rutas o modelos.

## Persistencia y seguridad

Alembic 0001 crea las tablas base; 0002 añade network_label y wifi_metrics. Las migraciones son la fuente ejecutable del esquema.

La API no tiene autenticación. En esta entrega escucha solo en 127.0.0.1 y no debe exponerse a una interfaz de red. No guarda SSID/BSSID, ubicación, IP completa del teléfono ni credenciales.
