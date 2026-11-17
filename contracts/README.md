# Contrato y semántica

`openapi.yaml` comenzó como propuesta del kit. La API FastAPI actual publica `/openapi.json`; su comparación de etapa 01 comprobó rutas, respuestas P0, propiedades/required, enums y cuerpos de ejemplo. Actualiza contrato y backend juntos si cambia la interfaz. Rutas P1 permanecen solo en el documento/SQL y no están registradas como endpoints operativos.

Sin auth headers ni security scheme. Installation se crea con primer POST. Errores propios con `code/message`; FastAPI normaliza también errores de validación. Fechas RFC3339 con zona y base de datos UTC. Cliente no suministra verdict ni hash.

## Reglas de señal

| Tipo | Ejemplos reason → outcome |
|---|---|
| WIFI_SECURITY | OS_SECURITY_REPORTED → PASS; OPEN_NETWORK/LEGACY_SECURITY → ATTENTION; FIELD_UNAVAILABLE/NO_WIFI → UNKNOWN |
| CAPTIVE_PORTAL | OS_PORTAL_NOT_DETECTED → PASS; PORTAL_DETECTED → UNKNOWN (acceso requerido, no ataque); FIELD_UNAVAILABLE → UNKNOWN |
| DNS | DNS_MATCH → PASS; DNS_MISMATCH → ATTENTION; NOT_CONFIGURED/REFERENCE_UNAVAILABLE/TIMEOUT/NETWORK_ERROR → UNKNOWN |
| HTTPS | TLS_VALID → PASS; TLS_INVALID → ATTENTION (no atribuir ataque); NOT_CONFIGURED/TIMEOUT/NETWORK_ERROR → UNKNOWN |

NETWORK_CHANGED/CANCELLED → UNKNOWN cuando se interrumpe. PERMISSION_DENIED → UNKNOWN para señales cuya API lo requiera. NOT_APPLICABLE reservado para futuro caso justificado, no usarlo para ocultar que falta dominio. Validar combinaciones por tipo, unicidad de tipos, evidencia compatible y tiempos en el servicio. El schema OpenAPI común no expresa todas las reglas cruzadas.

INCOMPLETE cuando `run_status=CANCELLED` o alguna señal es UNKNOWN. `has_attention` refleja ATTENTION aunque el verdict sea INCOMPLETE. Con todas comprobadas, ATTENTION_REQUIRED cuando existe atención y NO_DISCREPANCIES en otro caso. Esto no significa “red segura”. Cursor de checks usa `(started_at, UUID)`. `received_at` lo calcula servidor; hash interno no se expone.

## Ejemplos

`contracts/examples/` contiene cuatro cargas de ejemplo, todas sintéticas: `demo-normal`, `demo-discrepancia`, `demo-incompleto` y `live-incompleto`. Las tres DEMO se pueden enviar como demo solo si se mantiene `source=DEMO`. `live-incompleto` es una plantilla, no una captura real; no debe presentarse como observación del teléfono. La app genera UUID aleatorios propios al guardar y los conserva en reintentos.
