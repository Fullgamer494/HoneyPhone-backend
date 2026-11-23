# HoneyPhone API

API FastAPI 0.4.1 con Pydantic, SQLAlchemy 2, psycopg 3 y Alembic. Este repositorio contiene el servicio, PostgreSQL local, el contrato OpenAPI y herramientas de desarrollo.

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

## Cuentas y autenticación

La API ofrece registro, inicio de sesión con contraseña o Google, consulta y eliminación de la cuenta autenticada. Las revisiones, dispositivos y sesiones/eventos del señuelo requieren un token Bearer; `/healthz`, registro e inicio de sesión son públicos. Las instalaciones se asocian con la primera cuenta que las registra y las consultas solo devuelven datos de instalaciones propias. `DELETE /api/v1/auth/me` elimina la cuenta y sus instalaciones asociadas.

Para correo y contraseña, la contraseña se guarda con scrypt; nunca se guarda en texto claro. Para Google, el servidor verifica el ID token contra `GOOGLE_CLIENT_IDS`. Usa como audiencia el ID del cliente OAuth de tipo Web; la app Android solicita el ID token con ese mismo cliente. No guardes el JSON de OAuth ni su `client_secret` en el repositorio o APK.

En producción define `AUTH_SECRET_KEY` con un secreto aleatorio de al menos 32 caracteres y `GOOGLE_CLIENT_IDS` con los IDs de cliente autorizados separados por comas. En EC2, usa un archivo `.env` con permisos restringidos y rota el secreto con cuidado: invalidará las sesiones activas. La migración `0004_accounts` crea usuarios y asocia la instalación a una cuenta. Los registros previos quedan intactos y se hacen visibles cuando la app registra su instalación después de iniciar sesión.

El inicio de sesión no depende de SES. La verificación de correo y la recuperación de contraseña requieren configurar envío transaccional y todavía no están implementadas.

## Rutas de la API

- `GET /healthz`
- `POST /api/v1/auth/register`, `POST /api/v1/auth/login`, `POST /api/v1/auth/google`
- `GET /api/v1/auth/me`, `DELETE /api/v1/auth/me`
- `POST /api/v1/network-checks`, `GET /api/v1/network-checks` con filtros, cursor y límite hasta 50
- `GET /api/v1/network-checks/{check_id}`, `DELETE /api/v1/network-checks/{check_id}`
- `POST /api/v1/devices`, `GET /api/v1/devices`, `GET/PATCH/DELETE /api/v1/devices/{installation_id}`
- `POST/GET /api/v1/honeypot/sessions`
- `POST/GET /api/v1/honeypot/sessions/{session_id}/events`

Las rutas de cuentas salvo registro/login/Google, y todas las rutas de revisiones, dispositivos y señuelo, requieren token Bearer. POST de revisiones conserva idempotencia por `check_id`; reutilizar el ID con contenido distinto produce conflicto. `contracts/openapi.yaml` documenta la interfaz y los ejemplos. Ejecuta `scripts/sync-openapi.py` al cambiar rutas o modelos.

## Persistencia y seguridad

Alembic 0001 crea las tablas base; 0002 añade network_label y wifi_metrics. Las migraciones son la fuente ejecutable del esquema.

`/healthz` permanece público para la comprobación de disponibilidad. Las rutas de datos y dispositivos requieren autenticación. No guarda SSID/BSSID, ubicación, IP completa del teléfono ni contraseñas sin hash.

## Pruebas de integración

Instala las dependencias con `.venv/bin/pip install -e '.[test]'`. Las pruebas requieren una API en ejecución y una base PostgreSQL desechable cuyo nombre comience con `honeyphone_verify_`; se niegan a usar otra base. Define `HP_TEST_BASE_URL` con la URL de esa API y `DATABASE_URL` con la conexión directa a esa misma base, aplica las migraciones y ejecuta `.venv/bin/pytest -q`. Las pruebas crean y eliminan registros para comprobar persistencia, idempotencia, validación y revocación de dispositivos.
