# Caso HealthSync

El enunciado completo está en [ENUNCIADO.md](ENUNCIADO.md). La documentación de la solución (arquitectura, instalación, API y decisiones de seguridad) está en el [README principal](../../README.md), y el estado de cada módulo en [ENTREGA.md](../../ENTREGA.md).

## Cuentas de prueba

Las crea el servicio `seed` con la contraseña `SEED_PASSWORD` del `.env`:

| Rol | Correos |
|---|---|
| admin | valor de `ADMIN_EMAIL` (contraseña `ADMIN_PASSWORD`) y `admin2@healthsync.test` |
| paciente | paciente1@healthsync.test, paciente2@healthsync.test |
| profesional | profesional1@healthsync.test, profesional2@healthsync.test |

## API externa simulada

`GET {EXTERNAL_API_BASE_URL}/dataPoints?schema=<métrica>&usuario=<id>&dias=<1-30>`, con el encabezado `Authorization: Bearer <llave>`.

Métricas: `heart-rate`, `step-count`, `oxygen-saturation`, `sleep-duration`. La serie es determinista por usuario y métrica, y cerca del 5 % de las lecturas salen fuera de rango (por ejemplo 138 bpm o 86 % de oxígeno) para poder probar las alertas. La respuesta sigue una estructura inspirada en los esquemas de Open mHealth (`header` y `body`); no se verificó que exista un servicio público que entregue datos reales de wearables, por eso el simulador es la fuente por defecto.
