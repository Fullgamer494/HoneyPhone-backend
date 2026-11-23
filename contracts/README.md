# Contrato y semántica

`openapi.yaml` documenta las rutas operativas de FastAPI y publica los esquemas y ejemplos de solicitud y respuesta. La API también sirve el esquema generado en `/openapi.json`. Ejecuta `python scripts/sync-openapi.py` desde el repositorio backend después de cambiar rutas o modelos; el script sincroniza las rutas implementadas y conserva las rutas P1 marcadas como diseño. No presentes rutas P1 como funciones disponibles.

`/healthz`, registro, inicio de sesión y autenticación con Google son públicos. Las rutas de cuentas que consultan o eliminan la cuenta, dispositivos, revisiones y sesiones/eventos del señuelo requieren `Authorization: Bearer <token>`. El servidor limita las cargas a 64 KiB. Los errores siguen `{code, message}` cuando la aplicación los construye; FastAPI también normaliza errores de validación. Fechas RFC3339 deben incluir zona horaria y se almacenan en UTC. El cliente no suministra el veredicto ni el hash de integridad interno.

`DELETE /api/v1/auth/me` elimina la cuenta autenticada y sus instalaciones asociadas; las relaciones de base de datos eliminan los datos vinculados. La respuesta es `204 No Content`.

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
