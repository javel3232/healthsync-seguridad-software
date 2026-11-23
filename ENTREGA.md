# Ficha de entrega

> Esta ficha la usa el grupo auditor para levantar y probar la aplicación.

## Datos del grupo

- **Grupo:** jagler-velasquez (entrega individual)
- **Integrantes:** Jagler David Velasquez Velasquez
- **Curso:** Seguridad en el Software — Maestría en Ingeniería de Software, Universidad de La Sabana
- **Caso:** healthsync
- **Versión entregada:** Fase 1 (código fuente completo)
- **Fecha:** 2026-11-22

## Cómo levantar la aplicación

Ninguno adicional: siga `GUIA_AUDITOR.md`.

```bash
cp .env.example .env
docker compose up --build
```

- Aplicación: http://localhost:8080 · Correos de prueba (Mailpit): http://localhost:8025
- Cuando el log muestre `[seed] ... datos semilla listos`, `[validacion] Iniciado` y `[alertas] Iniciado`, todo está listo (la primera vez tarda varios minutos).
- Para reiniciar el estado: `docker compose down -v && docker compose up --build`.
- Pruebas de flujo opcionales (con la aplicación en marcha): `pip install requests && python scripts/prueba_flujos.py`.
- La documentación completa (arquitectura, API, decisiones de seguridad) está en `README.md`.

## Cuentas de prueba

Todas usan la contraseña `SEED_PASSWORD` del `.env` (por defecto `Prueba-Health2026`), salvo el administrador principal, que usa `ADMIN_PASSWORD` (por defecto `Admin-Health2026`).

| Rol | Correo | Datos semilla asociados |
|---|---|---|
| admin | `admin@healthsync.test` (valor de `ADMIN_EMAIL`) | Panel de validación de profesionales |
| admin | `admin2@healthsync.test` | Igual que el anterior |
| paciente | `paciente1@healthsync.test` | 50 créditos y 50 puntos de referidos; 1 dispositivo con 72 h de métricas (incluye una lectura atípica de 138 lpm); alerta "frecuencia cardíaca > 120" que avisa a `profesional1`; consulta **completada** (con notas) con `profesional1` y consulta **confirmada** a futuro con `profesional2` |
| paciente | `paciente2@healthsync.test` | 80 créditos; 1 dispositivo con métricas; alerta "oxígeno < 92 %" sin aviso a profesional; registrado con el código de `paciente1`; consulta **en curso** con `profesional1` y consentimiento ya otorgado |
| profesional | `profesional1@healthsync.test` | Cardiología, tarifa 20 créditos; tiene la consulta en curso de `paciente2` lista para ver métricas, escribir notas y finalizar |
| profesional | `profesional2@healthsync.test` | Medicina general, tarifa 30 créditos |
| profesional (pendiente) | `pendiente1@healthsync.test` | Solicitud con **documentación completa**: el robot de validación la aprueba en menos de un minuto y envía el correo de activación |
| profesional (pendiente) | `pendiente2@healthsync.test` | Solicitud **sin tarjeta**: el robot la omite y el administrador no puede aprobarla (sí rechazarla) |

Los códigos de referidos se generan al azar: se ven al ingresar en *Referidos*. Las imágenes de tarjeta de las semillas son rectángulos de color generados por el código (no son documentos reales).

## Estado de los módulos

| Módulo | Estado | Observaciones |
|---|---|---|
| Registro y verificación (20 %) | **Completo** | Registro con nombre, correo, contraseña, fecha de nacimiento y tipo de cuenta. Los profesionales adjuntan la tarjeta (PNG/JPEG ≤ 2 MB) y quedan pendientes. Panel de administración (ver tarjeta, aprobar, rechazar con motivo), correo al profesional y aparición en el directorio. Referidos: código por usuario activo, puntos al activarse el referido, canje por meses premium. Robot de validación en C++ cada 60 s. |
| Wearables (10 %) | **Completo** | Vincular/desvincular dispositivos, sincronizar 1–30 días desde la API externa (simulador por defecto), normalización a 4 métricas, sin duplicados, descarte de lecturas fuera de rango, lectura manual. |
| Consultas virtuales (30 %) | **Completo** | Directorio con búsqueda, agendamiento con cobro al confirmar, validación de cruces de horario, cancelación con reembolso, inicio/finalización, consentimiento por consulta, vista de métricas para el profesional, diagnóstico y notas clínicas, historial para ambos roles. |
| Alertas programadas (30 %) | **Completo** | CRUD de alertas (umbral mayor/menor sobre las 4 métricas), autorización explícita para avisar a un profesional, robot C++ cada 1 s, correos al paciente y al profesional, historial para ambos, sin avisos duplicados para una misma lectura. |
| Transferencias (10 %) | **Completo** | Transferencia atómica por correo del destinatario (máx. 1000 créditos), historial de movimientos, correo al destinatario. |

Los robots de C++, el envío de correo (Mailpit) y el consumo del servicio externo (simulador) están integrados y funcionan en los flujos anteriores.

## Limitaciones conocidas

- **Videollamada:** la "consulta virtual" se modela como su ciclo completo (agenda, cobro, inicio, métricas con consentimiento, notas, cierre), pero no incluye transmisión de audio/video.
- **Inicio de la consulta:** el profesional puede iniciarla en cualquier momento después de confirmada (no se exige que llegue la hora agendada) para facilitar las pruebas.
- **Validación de la tarjeta:** el robot y el panel comprueban que la documentación esté completa (imagen válida adjunta, fecha de nacimiento de un mayor de edad, correo); no verifican la autenticidad de la tarjeta frente a ningún registro oficial.
- **Premium:** canjear puntos solo registra la vigencia (`premium_hasta`); no activa funciones adicionales.
- **Aprobación manual y robot:** el robot valida cada minuto, así que una solicitud con documentación completa puede aprobarse sola antes de que el administrador la revise. Para probar el flujo manual use `pendiente2@healthsync.test` o detenga el robot (`docker compose stop worker`).
- **API de wearables:** se usa un simulador con formato inspirado en Open mHealth; no se encontró un servicio público que entregue datos reales de wearables.
- **Correos:** si el envío falla, queda registrado en el disparo de la alerta (campos `correo_*`) pero no se reintenta.
- **Transporte y límites:** el entorno corre por HTTP en `localhost` (la cookie `Secure` se activa con `COOKIE_SECURE=true` bajo HTTPS). Hay bloqueo de cuenta por intentos fallidos, pero no un límite general de peticiones por IP.
- **Fuera de alcance:** menores de edad (se exige ser mayor de 18), recuperación de contraseña por correo y doble factor de autenticación.
- **Datos:** todos los datos son ficticios; no se usan documentos, datos de salud ni credenciales reales.
