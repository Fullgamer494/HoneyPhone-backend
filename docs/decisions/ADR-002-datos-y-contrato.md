# ADR-002 — modelo y contrato unificados
Estado: línea base para implementación.
Conservar módulos por dominio, PostgreSQL/Room, categorías prudentes e idempotencia.
Eliminar HMAC del BSSID y network_pseudonym por falta de necesidad y disponibilidad de ese dato.
UUID v4 generado una vez y persistido basta; UUIDv7 es una optimización futura.
Eliminar cuentas, tokens y Argon2 de P0 por decisión del usuario. No hay endpoints enroll/login.
No particionar; PRIMARY KEY event_id global facilita deduplicación en cualquier fecha.
Un resultado por check_id/kind; enum común de severidad con reason_code específico por tipo.
No duplicar seguridad/portal/dns/https en cabecera y filas: check_signals es la fuente del detalle.
overall_verdict y has_attention se calculan en backend y se conservan como snapshot verificable.
Mismo UUID con mismo contenido normalizado devuelve existente; distinto contenido da409.
Hash server-side excluye received_at y campos derivados; ordena señales por kind y normaliza UTC.
Conservar modelos de sesiones/eventos aunque endpoints P1 no se implementen mañana.
