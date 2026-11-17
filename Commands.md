# Consultar los datos guardados en PostgreSQL

Esta guía muestra cómo inspeccionar desde la terminal las revisiones que la app ya envió al backend y quedaron guardadas en la base PostgreSQL local.

## Abrir una sesión de PostgreSQL

Con Docker:

    docker exec -it honeyphone-local-db-1 psql -U honeyphone_dev -d honeyphone

Si tienes psql instalado en tu equipo, también puedes conectarte por el puerto local:

    psql -h 127.0.0.1 -p 5433 -U honeyphone_dev -d honeyphone -W

La opción -W solicita la contraseña sin incluirla en el comando. Usa la contraseña configurada para la base local del proyecto.

## Explorar tablas y columnas

Dentro de psql:

    \dt
    \d+ network_checks
    \d+ check_signals
    \d+ installations

Para evitar que los resultados largos abran un paginador:

    \pset pager off

## Listar las revisiones más recientes

    SELECT received_at,
           check_id,
           source,
           network_label,
           verdict,
           run_status,
           wifi_metrics
    FROM network_checks
    ORDER BY received_at DESC
    LIMIT 20;

Cada fila es una revisión. wifi_metrics es un objeto JSONB con las métricas disponibles —por ejemplo RSSI, frecuencia, estándar Wi-Fi, velocidad negociada y validación de Internet—; los datos que el teléfono no pudo leer quedan ausentes.

## Ver las señales de cada revisión

    SELECT c.received_at,
           c.check_id,
           s.kind,
           s.outcome,
           s.reason_code,
           s.evidence,
           s.elapsed_ms
    FROM network_checks AS c
    JOIN check_signals AS s USING (check_id)
    ORDER BY c.received_at DESC, s.kind
    LIMIT 80;

Una revisión puede tener hasta cuatro señales: WIFI_SECURITY, CAPTIVE_PORTAL, DNS y HTTPS. Una prueba sin configurar aparece como desconocida; no significa que haya detectado un problema.

## Qué guarda cada tabla

- installations: identificador aleatorio de instalación, versión de la app y fechas de actividad.
- network_checks: revisiones, etiqueta manual opcional, estado, veredicto, métricas Wi-Fi y hash del contenido recibido.
- check_signals: resultado y evidencia permitida de cada señal.

La app no lee ni envía el SSID o la contraseña de la red. Las sondas DNS/HTTPS permanecen pendientes hasta configurar un destino controlado.

Para cerrar la sesión de PostgreSQL:

    \q
