# Arquitectura de ejecución

HoneyPhone tiene una app Android y una API modular. No requiere frontend web ni microservicios.

    Compose UI
      → ViewModel
      → RoomReviewRepository
         → Room: revisiones, señales y outbox
         → AndroidSignalReader: APIs de Wi-Fi y conectividad
         → NetworkApi: sincronización manual
      → adb reverse por USB
      → FastAPI router → service → repository
      → SQLAlchemy / psycopg
      → PostgreSQL

AndroidSignalReader puede ejecutar sondas DNS TXT/DoH y HTTPS por la red Wi-Fi activa cuando existe configuración válida. Las sondas y el transporte de la API tienen responsabilidades distintas.

La API expone rutas P0 de salud y revisiones. El esquema PostgreSQL conserva modelos de señuelo para una fase futura; no hay listener ni rutas P1 implementadas. El modelo relacional está en modelo-er.mmd; decisiones en ../decisions/.
