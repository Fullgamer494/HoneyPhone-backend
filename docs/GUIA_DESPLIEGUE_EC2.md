# Guía para continuar el despliegue en EC2

## Estado actual

- La instancia `HoneyPhone-backend` usa Ubuntu Server 26.04 en `us-east-2`.
- Docker y Docker Compose se instalaron en la instancia.
- La imagen de la API se construyó localmente como `honeyphone-api:0.3.0`.
- El archivo Compose de EC2 está en `infra/compose.ec2.yaml`.
- API y PostgreSQL están ejecutándose en EC2; `/healthz` responde localmente con la base lista.
- La API está publicada temporalmente en el puerto `8000`; PostgreSQL no publica su puerto.
- El dominio para la API será `honeyphone-api.myuspot.org`; actualmente no resuelve, así que falta crear su registro DNS `A`.
- Se reservó la Elastic IP `3.134.150.144` para la instancia. Confirma en EC2 que la asociación esté completada antes de crear el registro DNS.

## 1. Recuperar la conexión SSH

La instancia aparece en estado `Running`. La Elastic IP reservada para ella es `3.134.150.144`; úsala después de confirmar que ya está asociada. Si SSH agota el tiempo de espera antes de validar la clave privada, revisa los elementos siguientes.

En la consola de EC2, abre **Status and alarms** y confirma que ambas comprobaciones estén aprobadas (`2/2 checks passed`). En **Networking**, comprueba que la tabla de rutas de la subred tenga `0.0.0.0/0` dirigido a un Internet Gateway. Revisa también que la ACL de red permita entrada por TCP 22 y el tráfico de respuesta por puertos efímeros.

Si **Connect → EC2 Instance Connect** permite entrar, comprueba SSH y el firewall del sistema:

```bash
sudo systemctl status ssh
sudo systemctl enable --now ssh
sudo ufw status verbose
```

La clave privada está en:

```text
/home/fullg/Projects/honeyphone/AWS/HoneyPhone.pem
```

Conéctate desde el equipo que contiene esa clave. Después de asociar la Elastic IP, usa:

```bash
chmod 400 /home/fullg/Projects/honeyphone/AWS/HoneyPhone.pem
ssh -i /home/fullg/Projects/honeyphone/AWS/HoneyPhone.pem \
  ubuntu@3.134.150.144
```

## 2. Transferir la imagen y el archivo Compose

Desde el equipo local, después de asociar la Elastic IP, puedes transferir la imagen y el Compose así:

```bash
scp -i /home/fullg/Projects/honeyphone/AWS/HoneyPhone.pem \
  /tmp/honeyphone-api-0.4.1.tar.gz \
  /home/fullg/Projects/honeyphone/HoneyPhone-backend/infra/compose.ec2.yaml \
  ubuntu@3.134.150.144:/tmp/
```

El archivo comprimido contiene la imagen construida. Si ya no existe, vuelve a generarlo desde la raíz de `HoneyPhone-backend`:

```bash
docker save honeyphone-api:0.4.1 | gzip -1 > /tmp/honeyphone-api-0.4.1.tar.gz
```

## 3. Preparar e iniciar los contenedores

Conéctate por SSH y ejecuta en la instancia:

```bash
sudo install -d -m 0750 /opt/honeyphone
gzip -dc /tmp/honeyphone-api-0.4.1.tar.gz | sudo docker load
sudo install -m 0644 /tmp/compose.ec2.yaml /opt/honeyphone/compose.yaml
```

Crea una contraseña aleatoria para PostgreSQL. El comando conserva el archivo si ya existe y no imprime la contraseña:

```bash
sudo bash -c 'umask 077; touch /opt/honeyphone/.env; grep -q "^DB_PASSWORD=" /opt/honeyphone/.env || { printf "DB_PASSWORD=" >> /opt/honeyphone/.env; openssl rand -hex 32 >> /opt/honeyphone/.env; }; grep -q "^AUTH_SECRET_KEY=" /opt/honeyphone/.env || { printf "AUTH_SECRET_KEY=" >> /opt/honeyphone/.env; openssl rand -hex 32 >> /opt/honeyphone/.env; }; grep -q "^GOOGLE_CLIENT_IDS=" /opt/honeyphone/.env || printf "GOOGLE_CLIENT_IDS=\n" >> /opt/honeyphone/.env; chmod 600 /opt/honeyphone/.env'

Antes del primer arranque, edita `/opt/honeyphone/.env` y asigna a `GOOGLE_CLIENT_IDS` el ID de cliente OAuth **Web** (no el secreto). Conserva el `AUTH_SECRET_KEY` generado; no lo publiques ni lo reemplaces entre despliegues, porque eso cerraría las sesiones activas.

```bash
sudo nano /opt/honeyphone/.env
```
```

Inicia los servicios:

```bash
sudo docker compose --env-file /opt/honeyphone/.env \
  -f /opt/honeyphone/compose.yaml up -d
```

Consulta el estado y el endpoint de salud desde la instancia:

```bash
sudo docker compose --env-file /opt/honeyphone/.env \
  -f /opt/honeyphone/compose.yaml ps

curl -fsS http://127.0.0.1:8000/healthz
```

Si la API no inicia, consulta los registros:

```bash
sudo docker compose --env-file /opt/honeyphone/.env \
  -f /opt/honeyphone/compose.yaml logs --tail=100 api db
```

## 4. Publicar la imagen en Docker Hub (opcional)

La imagen local todavía no está publicada. Inicia sesión desde el equipo donde está construida:

```bash
docker login -u TU_USUARIO
```

Introduce el token cuando Docker lo solicite. No lo guardes en el repositorio ni lo compartas en el chat. Etiqueta y publica la imagen:

```bash
docker tag honeyphone-api:0.4.1 TU_USUARIO/honeyphone-api:0.4.1
docker push TU_USUARIO/honeyphone-api:0.4.1
```

Para que EC2 use la imagen publicada, añade su nombre al archivo `/opt/honeyphone/.env` en EC2:

```text
HONEYPHONE_API_IMAGE=TU_USUARIO/honeyphone-api:0.4.1
```

Después actualiza el servicio:

```bash
sudo docker compose --env-file /opt/honeyphone/.env \
  -f /opt/honeyphone/compose.yaml pull api
sudo docker compose --env-file /opt/honeyphone/.env \
  -f /opt/honeyphone/compose.yaml up -d api
```

## Acceso HTTP temporal

Compose publica temporalmente la API en el puerto `8000` de todas las interfaces del host. Este acceso sirve para confirmar el despliegue mientras se instala HTTPS.

Mientras el puerto `8000` siga permitido y publicado, la comprobación es:

```text
http://3.134.150.144:8000/healthz
```

La API responde sin autenticación y usa HTTP. Cualquier cliente que alcance ese puerto podría consultar o enviar registros. El capítulo 5 reemplaza este acceso por HTTPS; el cifrado no sustituye la autenticación de dispositivos.

PostgreSQL queda en la red privada de Docker, con almacenamiento persistente en el volumen `postgres_data`. No abras el puerto `5432` en el grupo de seguridad.

## 5. Poner HTTPS delante de FastAPI

La aplicación sigue ejecutándose en Python con Uvicorn. Caddy termina TLS y reenvía las solicitudes a FastAPI dentro de Docker; el certificado y su renovación quedan fuera del código Python.

### 5.1 Fijar la dirección pública y configurar DNS

La instancia muestra una IPv4 pública autoasignada. En EC2, abre **Network & Security → Elastic IPs → Allocate Elastic IP address** y asocia la dirección a la instancia `HoneyPhone-backend`. Una Elastic IP mantiene la dirección al detener e iniciar la instancia. AWS cobra por las IPv4 públicas, incluidas las Elastic IP. [Guía de Elastic IP de AWS](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/working-with-eips.html).

La Elastic IP reservada es `3.134.150.144`. Confirma que EC2 la muestre asociada a `HoneyPhone-backend`; al asociarla, AWS reemplaza la IPv4 autoasignada. Usa `3.134.150.144` para futuras conexiones SSH/SCP y para el DNS.

En Squarespace, abre **Domains → myuspot.org → DNS → DNS Settings → Custom Records → Add record** y crea:

| Campo | Valor |
|---|---|
| Tipo | `A` |
| Nombre | `honeyphone-api` |
| Dirección IP | `3.134.150.144` |

No cambies los registros `MX`, `TXT` ni los demás registros que ya use el dominio. Si el dominio tiene nameservers personalizados, crea el registro en el proveedor DNS autoritativo en lugar de Squarespace. [Instrucciones de Squarespace para registros DNS](https://support.squarespace.com/hc/en-us/articles/31119879125645-DNS-records-for-web-hosting).

Guarda el registro y espera a que se propague. El TTL predeterminado de Squarespace es de 4 horas. Comprueba desde una terminal:

```bash
getent ahostsv4 honeyphone-api.myuspot.org
```

El resultado debe incluir `3.134.150.144`. Caddy solo podrá solicitar el certificado cuando el DNS apunte a la instancia.

### 5.2 Abrir los puertos de HTTPS

En **EC2 → Security Groups → Inbound rules**, agrega estas reglas IPv4:

| Tipo | Puerto | Origen |
|---|---:|---|
| HTTP | 80 | `0.0.0.0/0` |
| HTTPS | 443 | `0.0.0.0/0` |

El puerto 80 permite la validación HTTP de ACME y la redirección a HTTPS; Caddy sirve HTTPS en 443. [Requisitos de HTTPS de Caddy](https://caddyserver.com/docs/quick-starts/https).

Después de validar HTTPS, elimina del grupo de seguridad la regla de entrada TCP 8000. Deja cerrado TCP 5432. La instancia no tiene IPv6 asignada, así que no agregues reglas IPv6.

### 5.3 Configurar Caddy para el certificado del dominio

Let’s Encrypt emite certificados de 90 días para nombres DNS con el perfil clásico. Recomienda renovarlos cada 60 días; Caddy automatiza la renovación. [Vigencia y renovación de certificados](https://letsencrypt.org/docs/faq/), [perfiles de Let’s Encrypt](https://letsencrypt.org/docs/profiles/), [HTTPS automático de Caddy](https://caddyserver.com/docs/automatic-https).

Entra a EC2 por SSH y crea `/opt/honeyphone/Caddyfile` con este comando (incluye la última línea `EOF`):

```bash
sudo tee /opt/honeyphone/Caddyfile >/dev/null <<'EOF'
honeyphone-api.myuspot.org {
	encode zstd gzip
	reverse_proxy api:8000
}
EOF
```

Caddy obtendrá un certificado público y lo renovará automáticamente. Conserva sus datos en el volumen `caddy_data`; no borres el volumen al actualizar. La imagen queda fijada a `caddy:2.11.9-alpine`. [Imagen oficial de Caddy](https://hub.docker.com/_/caddy).

No necesitas instalar Certbot: Caddy solicita y renueva el certificado por sí mismo.

### 5.4 Actualizar Docker Compose

Haz una copia de seguridad del Compose actual y reemplázalo con el archivo completo siguiente. Ejecuta el bloque dentro de la sesión SSH de EC2:

```bash
sudo cp /opt/honeyphone/compose.yaml "/opt/honeyphone/compose.yaml.bak.$(date +%Y%m%d-%H%M%S)"
sudo tee /opt/honeyphone/compose.yaml >/dev/null <<'EOF'
name: honeyphone

services:
  db:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: honeyphone
      POSTGRES_USER: honeyphone
      POSTGRES_PASSWORD: ${DB_PASSWORD:?DB_PASSWORD is required}
      TZ: UTC
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U honeyphone -d honeyphone"]
      interval: 5s
      timeout: 3s
      retries: 12
    networks: [private]

  api:
    image: ${HONEYPHONE_API_IMAGE:-honeyphone-api:0.4.1}
    restart: unless-stopped
    environment:
      APP_ENV: production
      DATABASE_URL: postgresql+psycopg://honeyphone:${DB_PASSWORD}@db:5432/honeyphone
      MAX_BODY_BYTES: 65536
      AUTH_SECRET_KEY: ${AUTH_SECRET_KEY:?AUTH_SECRET_KEY is required}
      GOOGLE_CLIENT_IDS: ${GOOGLE_CLIENT_IDS:-}
    depends_on:
      db:
        condition: service_healthy
    networks: [private, edge]

  caddy:
    image: caddy:2.11.9-alpine
    restart: unless-stopped
    depends_on: [api]
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /opt/honeyphone/Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
    networks: [edge]

volumes:
  postgres_data:
  caddy_data:
  caddy_config:

networks:
  private:
    internal: true
  edge:
EOF
```

El bloque elimina la publicación directa de `8000` y deja a Caddy como único punto de entrada web. PostgreSQL solo queda conectado a la red privada. El archivo conserva los mismos nombres de volumen para que Docker reutilice los datos existentes.

Valida la configuración y descarga Caddy. Si `config --quiet` no imprime errores, aplica el Compose:

```bash
sudo docker compose --env-file /opt/honeyphone/.env \
  -f /opt/honeyphone/compose.yaml config --quiet

sudo docker compose --env-file /opt/honeyphone/.env \
  -f /opt/honeyphone/compose.yaml pull caddy

sudo docker compose --env-file /opt/honeyphone/.env \
  -f /opt/honeyphone/compose.yaml up -d
```

Comprueba los registros de Caddy mientras obtiene el certificado:

```bash
sudo docker compose --env-file /opt/honeyphone/.env \
  -f /opt/honeyphone/compose.yaml logs --tail=100 caddy
```

### 5.5 Confirmar HTTPS

Desde la instancia y desde una red externa, consulta:

```bash
curl -fsS https://honeyphone-api.myuspot.org/healthz
curl -I http://honeyphone-api.myuspot.org/healthz
```

La primera petición debe devolver `{"status":"ok","database":"ready"}` con una conexión TLS válida. La segunda debe redirigir a HTTPS. Swagger queda disponible en `https://honeyphone-api.myuspot.org/docs`.

Cuando ambas comprobaciones funcionen, elimina la regla TCP 8000 del grupo de seguridad. Confirma que el contenedor `caddy` sigue activo y conserva `caddy_data` y `caddy_config`; no borres esos volúmenes al actualizar.

### 5.6 Apuntar la app Android a HTTPS

El cliente Android debe usar una URL base que termine en `/api/v1/`. El proyecto `HoneyPhone-frontend` ya lee `HONEYPHONE_API_BASE_URL` en el tipo de compilación `release`. Para compilar el release firmado con la URL de la Elastic IP:

```bash
cd /home/fullg/Projects/honeyphone/HoneyPhone-frontend
HONEYPHONE_API_BASE_URL="https://honeyphone-api.myuspot.org/api/v1/" \
  ./gradlew :app:assembleRelease
```

Gradle requiere las cuatro variables `HONEYPHONE_RELEASE_*` para producir un APK firmado. Si todavía no tienes la clave de firma, permite que la build `debug` acepte la misma URL de entorno:

1. En `HoneyPhone-frontend/app/build.gradle.kts`, junto a `releaseApiBaseUrl`, añade:

   ```kotlin
   val debugApiBaseUrl = providers.environmentVariable("HONEYPHONE_API_BASE_URL")
       .orElse("http://127.0.0.1:8081/api/v1/").get()
   ```

2. Reemplaza la línea actual de `debug`:

   ```kotlin
   debug { buildConfigField("String", "API_BASE_URL", "\"http://127.0.0.1:8081/api/v1/\"") }
   ```

   por:

   ```kotlin
   debug { buildConfigField("String", "API_BASE_URL", buildConfigLiteral(debugApiBaseUrl)) }
   ```

3. Compila desde la raíz de `HoneyPhone-frontend` con el dominio HTTPS:

   ```bash
   HONEYPHONE_API_BASE_URL="https://honeyphone-api.myuspot.org/api/v1/" \
     ./gradlew :app:assembleDebug
   ```

4. Instala el APK resultante en el A56:

   ```bash
   adb install -r app/build/outputs/apk/debug/app-debug.apk
   ```

Android tiene cleartext desactivado, por lo que usa la URL `https://` y no habilites HTTP sin cifrar.

Instala el APK y confirma en la app que `GET /healthz` y la sincronización de una revisión funcionan. La URL de salud de esta API es `/healthz`; las rutas de datos usan el prefijo `/api/v1/`.

### Certificado directo para la IP (alternativa)

Si el dominio no se va a usar, Let’s Encrypt también emite certificados para IP, pero solo con el perfil `shortlived`, válido por 160 horas. Requiere automatización de renovación y una dirección estable. El Caddyfile debe usar la IP como nombre del sitio y especificar `profile shortlived`; no combines esta alternativa con el Caddyfile DNS de arriba. [Certificados IP de Let’s Encrypt](https://letsencrypt.org/2026/01/15/6day-and-ip-general-availability).

### Límite de seguridad actual

HTTPS cifra el tráfico y autentica el servidor; no autentica a los teléfonos. La API actual no tiene autenticación, así que cualquier persona que conozca la IP puede consultar y enviar registros. Antes de guardar datos reales, implementa una credencial por dispositivo o restringe el acceso a clientes de confianza.
