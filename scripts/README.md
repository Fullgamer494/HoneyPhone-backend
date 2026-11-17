# Herramientas de backend

Desde la raíz de este repositorio:

- sync-openapi.py actualiza contracts/openapi.yaml desde FastAPI y conserva marcadas como diseño las rutas P1 del señuelo.
- api-smoke.sh consulta /healthz y un historial DEMO; no reemplaza pruebas de escritura e idempotencia.

La variable API_BASE_URL permite cambiar el host de la API local para api-smoke.sh.
