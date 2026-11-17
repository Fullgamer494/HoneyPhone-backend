# ADR-004 — señuelo posterior con persistencia preparada
Estado: aceptado para avance P0; selección FGS pendiente de prueba.
Puerto propuesto 8080/TCP, apagado por defecto y sin cuerpos de formulario ni contraseñas.
Servicio visible solo al usuario activarlo, cierre manual/automático y límites de bytes/tiempo.
No afirmar que un tipo de FGS es admisible sin validar su caso de uso y permisos en Android real.
Android16 y target36: considerar pruebas opt-in de protección LAN; al adoptar target37+
se debe implementar ACCESS_LOCAL_NETWORK según documentación vigente.
Cliente aislado por AP puede impedir conexiones sin afectar revisión local.
Las tablas se incluyen ahora; el servidor HTTP, sus APIs y capturas del Samsung quedan P1.
