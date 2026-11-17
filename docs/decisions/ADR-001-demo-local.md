# ADR-001 — alcance para la entrega inmediata
Estado: aceptado como línea base derivada de instrucciones explícitas del usuario.
Contexto: Samsung A56 Android 16, Ubuntu, menos de 24 h, prioridad de interfaz y API local.
Decisión: app Compose, FastAPI, PostgreSQL, Room, sin autenticación. API por loopback+USB.
Dominio y AWS posteriores. No invertir tiempo en login o token de dispositivo.
Consecuencia: installation_id es correlación y no autorización; la demo no es multiusuario segura.
Antes de exposición remota se debe rediseñar acceso, control de propietario y transporte HTTPS.
El objetivo de esta entrega es comunicación y persistencia reales con alcance técnico declarado.
