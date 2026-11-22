# Actualizar la API de HoneyPhone en EC2

Esta guía construye la imagen **en EC2** para evitar que Docker Desktop en la computadora tenga que descargar `python:3.12-slim`. Usa la instancia con IP pública `3.134.150.144` y conserva el Compose existente de EC2, incluido Caddy.

> Ejecuta cada bloque en el entorno indicado. No ejecutes `docker compose down -v`: eliminaría el volumen de PostgreSQL.

## 1. Empaquetar el backend en la computadora

Abre una terminal en la raíz del repositorio `HoneyPhone-backend`:

```bash
cd ~/Projects/honeyphone/HoneyPhone-backend

tar \
  --exclude=.git \
  --exclude=.venv \
  --exclude='__pycache__' \
  -czf /tmp/honeyphone-api-0.4.0.tar.gz .
```

Comprueba que se creó el archivo:

```bash
ls -lh /tmp/honeyphone-api-0.4.0.tar.gz
```

## 2. Copiar el archivo a EC2

En la computadora local:

```bash
scp -i ~/Projects/honeyphone/AWS/HoneyPhone.pem \
  /tmp/honeyphone-api-0.4.0.tar.gz \
  ubuntu@3.134.150.144:/tmp/
```

Si la clave SSH está en otra ruta o la IP pública cambió, ajusta esos valores.

## 3. Construir la imagen en EC2

Conéctate desde la computadora:

```bash
ssh -i ~/Projects/honeyphone/AWS/HoneyPhone.pem \
  ubuntu@3.134.150.144
```

En la terminal de EC2, extrae el código y construye la imagen:

```bash
mkdir -p /tmp/honeyphone-api-0.4.0

tar -xzf /tmp/honeyphone-api-0.4.0.tar.gz \
  -C /tmp/honeyphone-api-0.4.0

sudo docker build \
  -t honeyphone-api:0.4.0 \
  /tmp/honeyphone-api-0.4.0
```

La instancia necesita conexión a internet para descargar la imagen base y los paquetes de Python. Si el build falla por DNS o por una descarga vencida, vuelve a ejecutar el comando `docker build` en EC2.

## 4. Revisar la configuración de la API

En EC2, conserva los valores existentes de `DB_PASSWORD` y `AUTH_SECRET_KEY`. No los regeneres: cambiar `DB_PASSWORD` podría impedir conectar a la base existente, y cambiar `AUTH_SECRET_KEY` invalidaría las sesiones vigentes.

Abre el archivo de entorno:

```bash
sudo nano /opt/honeyphone/.env
```

Asegúrate de que existan estas variables:

```dotenv
DB_PASSWORD=valor_existente_de_la_base
AUTH_SECRET_KEY=valor_secreto_existente
GOOGLE_CLIENT_IDS=70591473922-uk7clkrg40kdue637mu4s7i1k43k677a.apps.googleusercontent.com
HONEYPHONE_API_IMAGE=honeyphone-api:0.4.0
```

`GOOGLE_CLIENT_IDS` debe contener el ID público del cliente OAuth de tipo **Web**. No pongas el `client_secret` ni el ID del cliente Android en esta variable. Si `HONEYPHONE_API_IMAGE` no se usa en el Compose actual, no hace falta añadirla.

Guarda en nano con **Ctrl+O**, Enter, y sal con **Ctrl+X**.

Comprueba qué imagen referencia el Compose:

```bash
grep -n 'image:' /opt/honeyphone/compose.yaml
```

Si el servicio `api` fija directamente `honeyphone-api:0.3.0`, edita el archivo:

```bash
sudo nano /opt/honeyphone/compose.yaml
```

Cambia solo esa referencia a:

```yaml
image: ${HONEYPHONE_API_IMAGE:-honeyphone-api:0.4.0}
```

Conserva los servicios, redes, volúmenes, puertos y configuración de Caddy actuales.

## 5. Actualizar solo la API

En EC2, valida el Compose y recrea el servicio de API:

```bash
sudo docker compose \
  --env-file /opt/honeyphone/.env \
  -f /opt/honeyphone/compose.yaml \
  config --quiet

sudo docker compose \
  --env-file /opt/honeyphone/.env \
  -f /opt/honeyphone/compose.yaml \
  up -d api
```

La imagen ejecuta las migraciones Alembic al iniciar la API.

### Si la API se reinicia por `AUTH_SECRET_KEY`

Si los logs dicen `AUTH_SECRET_KEY must be a random secret of at least 32 characters in production`, actualiza la variable en `/opt/honeyphone/.env`. Este comando genera una clave nueva y la escribe sin imprimirla:

```bash
sudo python3 - <<'PY'
from pathlib import Path
import secrets

path = Path("/opt/honeyphone/.env")
lines = path.read_text().splitlines()
key_line = f"AUTH_SECRET_KEY={secrets.token_hex(32)}"

for index, line in enumerate(lines):
    if line.startswith("AUTH_SECRET_KEY="):
        lines[index] = key_line
        break
else:
    lines.append(key_line)

path.write_text("\n".join(lines) + "\n")
path.chmod(0o600)
print("AUTH_SECRET_KEY actualizado; valor oculto.")
PY
```

Recrea el contenedor para que Compose lea la variable actualizada:

```bash
sudo docker compose \
  --env-file /opt/honeyphone/.env \
  -f /opt/honeyphone/compose.yaml \
  up -d --force-recreate api
```

Después, revisa `ps` y los logs como se indica abajo. Mantén la nueva clave privada: cambiarla invalida las sesiones existentes. Si una clave se compartió en un chat o captura, trátala como expuesta y rótala.

## 6. Verificar el despliegue

En EC2, revisa el estado y los logs:

```bash
sudo docker compose \
  --env-file /opt/honeyphone/.env \
  -f /opt/honeyphone/compose.yaml \
  ps

sudo docker compose \
  --env-file /opt/honeyphone/.env \
  -f /opt/honeyphone/compose.yaml \
  logs --tail=100 api

curl -fsS https://honeyphone-api.myuspot.org/healthz
```

La respuesta de salud debe indicar que el estado es `ok` y la base de datos está `ready`. Desde EC2 o desde la computadora, confirma que la ruta de registro quedó publicada:

```bash
curl -fsS https://honeyphone-api.myuspot.org/openapi.json \
  | grep -o '/api/v1/auth/register'
```

Debe imprimir:

```text
/api/v1/auth/register
```

Si no aparece, revisa los logs del servicio y confirma que el Compose apunta a `honeyphone-api:0.4.0`.

## 7. Instalar el APK en el A56

Después de desplegar la API, vuelve a la computadora. Con el teléfono conectado y autorizado para depuración USB, desde la raíz de `HoneyPhone-frontend` ejecuta:

```bash
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

El APK debe haberse compilado con:

```bash
HONEYPHONE_API_BASE_URL='https://honeyphone-api.myuspot.org/api/v1/' \
  ./gradlew :app:assembleDebug
```

El flujo de Google requiere que `GOOGLE_CLIENT_IDS` en EC2 coincida con el cliente OAuth Web integrado en el APK.
