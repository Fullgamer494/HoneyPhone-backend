# Conexión local del Samsung A56 con la API

## Iniciar PostgreSQL y la API

Desde la raíz del proyecto:

    docker compose --env-file .env.example -f infra/compose.yaml up -d db
    backend/.venv/bin/alembic -c backend/alembic.ini upgrade head
    backend/.venv/bin/uvicorn honeyphone.main:app --app-dir backend/src --host 127.0.0.1 --port 8000

Comprueba la API con:

    curl http://127.0.0.1:8000/healthz

Swagger está disponible en http://127.0.0.1:8000/docs.

## Conectar por USB

Con el teléfono conectado, desbloqueado y autorizado para depuración USB:

    adb devices
    adb reverse tcp:8081 tcp:8000
    adb reverse --list

La app debug envía a http://127.0.0.1:8081/api/v1/. Repite adb reverse tras desconectar o reiniciar el teléfono. El repositorio Android incluye scripts/usb-reverse.sh; también puedes ejecutar adb reverse tcp:8081 tcp:8000 directamente.

La conexión de API por USB es independiente de la Wi-Fi que la app observa. No uses 10.0.2.2 en el teléfono físico; esa dirección se reserva para emuladores.

## Seguridad local

La API no tiene autenticación; debe escuchar en 127.0.0.1. El manifest principal y release bloquean HTTP cleartext. La excepción de debug se limita a localhost y 127.0.0.1. No abras el puerto de la API a la LAN ni a Internet.

## Diagnóstico

| Síntoma | Revisión |
|---|---|
| Connection refused | API arriba en puerto 8000 y túnel adb reverse activo |
| No aparece el dispositivo | Depuración USB, autorización RSA, cable y adb devices |
| Cleartext not permitted | Configuración de red de la variante debug y URL loopback |
| 422 | Campos/enums del payload frente a OpenAPI |
| 409 | UUID ya usado con un payload diferente |
| 503 en healthz | Salud PostgreSQL, configuración local y migraciones |
| Swagger funciona y la app no | Base URL /api/v1/, permiso INTERNET y puente USB |
