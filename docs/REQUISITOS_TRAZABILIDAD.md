# Cobertura del planteamiento original

| Requisito | Implementación ahora / modelo | Posterior |
|---|---|---|
| F01 Revisar Wi-Fi | UI y lector básico del sistema; UNKNOWN si no disponible | Matriz completa de teléfonos |
| F02 Ver señales | Cuatro señales, severidad y razón; DNS/TLS no configurados | Sondas TXT/DoH y HTTPS propias |
| F03 Entender hallazgos | Ficha de detalle y explicaciones prudentes | Afinar evidencia de sondas |
| F04 Historial | Room + network_checks/check_signals | Retención configurable |
| F05 Sincronizar | POST/GET manual, installation_id sin auth | Auth y sincronización diferida automática |
| F06 Señuelo | honeypot_sessions y diseño | Listener Android con FGS validado |
| F07 Intentos | honeypot_events y contrato P1 | Captura y visualización de conexiones reales |
| F08 Exportar | JSON mínimo local tras integración | CSV y selección de rango |
| F09 Desconocido | UNKNOWN y reason específico en UI/API/BD | Ninguno para el comportamiento base |
| Borrado voluntario | DELETE check, cancelar outbox local | Retención servidor administrada |
| No SSID/BSSID/IP legibles | installation UUID y CIDR en eventos | Revalidar privacidad al añadir sondas |
| Auth del documento original | Omitida expresamente por usuario para esta versión | Requisito antes de exponer servidor |

Este kit cubre en diseño el proyecto completo. La entrega inmediata implementa P0; no afirmar
que funcionalidad P1 o autenticación ya está cubierta en ejecución.

## Pruebas del planteamiento
T01–T05 Wi-Fi/portal/permisos: ejecutar lo posible en A56 y documentar límites.
T06–T12 DNS/HTTPS: pendientes de dominio/laboratorio; escenarios DEMO no equivalen a prueba real.
T13 cambio de red, T14 historial local, T15 sync voluntaria: prioritarias para integración.
T16 aislamiento entre usuarios: diferida porque esta versión no autentica; no inventar un aprobado.
T17 tamaño de API: comprobar. T18–T20 listener/aislamiento: fase posterior.
Añadir checks de idempotencia, conflicto de UUID, borrado y API desconectada para P0.
