# Caso AI Agent Marketplace: punto de partida

El enunciado completo está en [ENUNCIADO.md](ENUNCIADO.md). Para trabajar este caso, use `CASO=marketplace` en su `.env`.

## Qué trae la plantilla y qué construye el grupo

| Módulo (peso) | Qué trae la plantilla | Qué construye el grupo |
|---|---|---|
| Registro y verificación (20%) | Registro con roles `desarrollador` y `empresa` (ambos quedan `pendiente`). Inicio y cierre de sesión, directorio y perfil de ejemplo. Envío de correo a Mailpit. | Panel de administración para aprobar. Generación y entrega de la API key. Referidos con crédito. Bot de aprobación en C++. |
| Catálogo de agentes (10%) | — | Publicación, aprobación por administrador y visibilidad. |
| Ejecución de agentes (30%) | Simulador compatible con OpenRouter (`/chat/completions`, `/models`) y cliente HTTP de ejemplo. | Autenticación por API key, cobro por ejecución, historial. |
| Ejecuciones programadas (30%) | Robot C++ periódico que consulta `/api/internal/...`. | Programación recurrente y condicional, despacho. |
| Transferencias (10%) | — | Saldos y transferencias entre usuarios. |

## Cuentas de prueba

Las crea el servicio `seed` con la contraseña `SEED_PASSWORD` del `.env`:

| Rol | Correos |
|---|---|
| admin | valor de `ADMIN_EMAIL` (contraseña `ADMIN_PASSWORD`) |
| desarrollador | dev1@marketplace.test, dev2@marketplace.test |
| empresa | empresa1@marketplace.test, empresa2@marketplace.test |

Si agrega roles, agregue también al menos dos cuentas por rol en `caso.json`.

## API externa simulada

- `GET {EXTERNAL_API_BASE_URL}/models`: lista de modelos simulados con precios.
- `POST {EXTERNAL_API_BASE_URL}/chat/completions` con `{"model": "...", "messages": [...]}`: responde con el formato de OpenRouter (compatible con OpenAI).

Ambas exigen el encabezado `Authorization: Bearer <llave>`. Modelos disponibles: `simulado/eco-1`, `simulado/resumen-1` y `simulado/lento-1` (tarda 5 segundos, útil para probar tiempos de espera).

**Usar OpenRouter real (opcional):** defina en `.env` `EXTERNAL_API_BASE_URL=https://openrouter.ai/api/v1` y una `EXTERNAL_API_KEY` propia. La API real cobra por uso, así que la entrega al grupo auditor debe funcionar con el simulador.
