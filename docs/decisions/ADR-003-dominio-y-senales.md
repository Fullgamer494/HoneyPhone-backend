# ADR-003 — sin dominio, señales parciales honestas
Estado: aceptado para demo local.
No hay dominio administrable todavía. Las sondas DNS/DoH y HTTPS del proyecto quedan
UNKNOWN/NOT_CONFIGURED; no sustituir con Google, un proveedor variable o el localhost de API
y afirmar que se ejecutó el diagnóstico propuesto. Escenarios sintéticos usan source=DEMO.
Sí se puede leer capacidad Wi-Fi/portal del sistema con APIs públicas, sin BSSID/SSID.
adb reverse verifica transporte de API por USB, independiente de la red auditada.
El esquema conserva evidence acotada, reason_code y source para implementar después las sondas.
En la futura fase DNS, usar TXT fijo y DnsResolver.rawQuery para la respuesta del sistema,
DoH de referencia, límites de tiempo y error de referencia como desconocido.
