# HealthSync

Plataforma de salud digital (proyecto del curso *Seguridad en Software*, caso **HealthSync**). Integra datos de dispositivos *wearables*, consultas médicas virtuales pagadas con créditos, alertas de salud automáticas y un programa de referidos.

Enunciado: [`casos/healthsync/ENUNCIADO.md`](casos/healthsync/ENUNCIADO.md) · Ficha de entrega: [`ENTREGA.md`](ENTREGA.md) · Guía del grupo auditor: [`GUIA_AUDITOR.md`](GUIA_AUDITOR.md)

## Contenido

1. [Qué hace la aplicación](#1-qué-hace-la-aplicación)
2. [Arquitectura](#2-arquitectura)
3. [Instalación y ejecución](#3-instalación-y-ejecución)
4. [Cuentas de prueba y recorrido sugerido](#4-cuentas-de-prueba-y-recorrido-sugerido)
5. [Estructura del código](#5-estructura-del-código)
6. [Referencia de la API](#6-referencia-de-la-api)
7. [Decisiones de seguridad](#7-decisiones-de-seguridad)
8. [Pruebas automáticas](#8-pruebas-automáticas)
9. [Problemas comunes](#9-problemas-comunes)
10. [Generar el ZIP de entrega](#10-generar-el-zip-de-entrega)

## 1. Qué hace la aplicación

| Módulo (peso) | Funcionalidad |
|---|---|
| **Registro y verificación (20 %)** | Registro de pacientes (activos de inmediato) y de profesionales de salud (adjuntan la foto de su tarjeta profesional y quedan *pendientes*). Panel de administración para aprobar o rechazar, con correo al profesional y aparición en el directorio. **Programa de referidos**: cada usuario activo tiene un código; quien se registra con él le da puntos al referidor, canjeables por meses de *premium*. **Robot de validación en C++** (cada minuto): valida las solicitudes con documentación completa. |
| **Wearables (10 %)** | El paciente vincula dispositivos, sincroniza sus métricas desde la API externa (frecuencia cardíaca, pasos, oxígeno, sueño), que se normalizan y se guardan sin duplicados. También puede registrar lecturas manuales. |
| **Consultas virtuales (30 %)** | Directorio con búsqueda, agendamiento con cobro inmediato en créditos, cancelación con reembolso, ciclo *confirmada → en curso → completada*. El profesional ve las métricas del paciente **solo con su consentimiento explícito y mientras la consulta está en curso**, y registra diagnóstico y notas clínicas. Historial para pacientes y profesionales. |
| **Alertas programadas (30 %)** | El paciente define umbrales (p. ej. frecuencia cardíaca > 120). Un **robot en C++ (cada segundo)** evalúa la lectura más reciente de cada paciente activo y dispara las alertas: correo al paciente y, si lo autorizó, al profesional elegido. |
| **Transferencias (10 %)** | Transferencia de créditos entre usuarios, atómica y con historial de movimientos. |

## 2. Arquitectura

```
Navegador ──► localhost:8080 ── web (nginx + SPA Vue) ──/api──► backend (Flask + gunicorn)
                                                                  │     │       │       │
                                                                 db  mailpit  mock-api  archivos
                                                              (MySQL) (correo) (API ext.) (volumen)
                                                                  ▲
                          worker          (robot C++, 1 vez/min) ─┤  vía /api/internal
                          worker-alertas  (robot C++, 1 vez/seg) ─┘  (red interna de Docker)
```

| Servicio | Tecnología | Función |
|---|---|---|
| `web` | nginx + Vue 3 + Bootstrap 5 | Sirve la SPA, añade cabeceras de seguridad y redirige `/api` al backend. Bloquea `/api/internal`. |
| `backend` | Python 3.13, Flask 3.1, gunicorn | API REST con toda la lógica de negocio. |
| `seed` | (imagen del backend) | Crea administrador, cuentas de prueba y datos de ejemplo. Es idempotente. |
| `db` | MySQL 8.4 | Base de datos (la aplicación usa un usuario propio, no `root`). |
| `worker` | C++17 + libcurl | Robot de **validación** de profesionales (cada 60 s). |
| `worker-alertas` | C++17 + libcurl | Robot de **monitoreo de alertas** (cada 1 s). Mismo ejecutable, con `ROBOT=alertas`. |
| `mailpit` | Mailpit | Captura todos los correos. No envía nada a Internet. |
| `mock-api` | Flask | Simula la API externa de wearables (Open mHealth). |

Solo se publican dos puertos, y únicamente en `127.0.0.1`: `8080` (aplicación) y `8025` (correos).

## 3. Instalación y ejecución

**Requisitos:** Docker Desktop (Windows/macOS) o Docker Engine con Compose v2 (Linux), y unos 4 GB libres. Python 3 solo se necesita para generar el ZIP de entrega y para las pruebas automáticas.

```bash
# 1. Crear el archivo de variables de entorno (ya trae valores listos para desarrollo)
cp .env.example .env              # Windows PowerShell: Copy-Item .env.example .env

# 2. Construir y levantar todo (la primera vez tarda varios minutos)
docker compose up --build

# 3. Abrir
#    Aplicación:                  http://localhost:8080
#    Correos enviados (Mailpit):  http://localhost:8025
```

Cuando `docker compose` muestre `[seed] ... datos semilla listos` y los dos robots (`[validacion] Iniciado`, `[alertas] Iniciado`), la aplicación está lista.

| Para | Comando |
|---|---|
| Ver logs de un servicio | `docker compose logs -f backend` (o `worker`, `worker-alertas`, `seed`) |
| Reconstruir tras cambiar código | `docker compose up --build` |
| **Empezar de cero** (borra base de datos y archivos) | `docker compose down -v` y luego `docker compose up --build` |
| Consola de MySQL | `docker compose exec db mysql -u root -p app` (clave: `MYSQL_ROOT_PASSWORD` del `.env`) |
| Detener un robot (para probar la aprobación manual) | `docker compose stop worker` |

Variables de entorno: todas están documentadas en [`.env.example`](.env.example). Los valores incluidos son **solo para desarrollo**.

## 4. Cuentas de prueba y recorrido sugerido

Todas usan `SEED_PASSWORD` del `.env` (por defecto `Prueba-Health2026`), salvo el administrador principal (`ADMIN_PASSWORD`, por defecto `Admin-Health2026`).

| Rol | Correo |
|---|---|
| Administrador | `admin@healthsync.test` (clave `ADMIN_PASSWORD`) · `admin2@healthsync.test` |
| Paciente | `paciente1@healthsync.test` · `paciente2@healthsync.test` |
| Profesional | `profesional1@healthsync.test` (Cardiología) · `profesional2@healthsync.test` (Medicina general) |
| Solicitudes pendientes | `pendiente1@healthsync.test` (documentación completa: el robot la valida en ≤ 1 min) · `pendiente2@healthsync.test` (**sin tarjeta**: queda para el administrador) |

**Recorrido para ver todos los flujos** (ver más detalle en [`ENTREGA.md`](ENTREGA.md)):

1. **Registro y validación:** en `/registro` cree un profesional con una foto PNG/JPEG. Ingrese como admin → *Administración* → revise la tarjeta → *Aprobar* (o espere ≤ 1 min a que lo haga el robot). Revise el correo en Mailpit.
2. **Referidos:** como `paciente1` abra *Referidos*, copie el código y regístrese con él: `paciente1` gana puntos y puede canjearlos por premium.
3. **Wearables:** como paciente, *Wearables* → *Sincronizar ahora* (importa desde la API externa simulada).
4. **Consultas:** *Directorio* → *Agendar* → autorice el consentimiento → como profesional abra la consulta, *Iniciar*, *Ver métricas*, escriba diagnóstico y notas, *Finalizar* (el profesional recibe los créditos).
5. **Alertas:** *Alertas* → cree "frecuencia cardíaca mayor que 120" autorizando al profesional → en *Wearables* registre una lectura manual de 150 → en ~1 segundo el robot dispara la alerta; vea los dos correos en Mailpit.
6. **Transferencias:** *Créditos* → transfiera a `paciente2@healthsync.test`.

## 5. Estructura del código

```
docker-compose.yml        Servicios, redes internas y volúmenes
.env.example              Variables de entorno (copiar como .env)
ENTREGA.md                Ficha de entrega para el grupo auditor
database/init/
  01-esquema-base.sql     Tabla base de cuentas (plantilla)
  02-healthsync.sql       Esquema de HealthSync (11 tablas nuevas + ampliación de `cuentas`)
backend/app/
  __init__.py             Fábrica de la app, manejo de errores, cabeceras
  config.py               Configuración desde el entorno
  db.py                   Acceso a datos (consultas parametrizadas, transacciones)
  seguridad.py            Hash de contraseñas, sesión, CSRF, roles
  validaciones.py         Validación de entradas   · errores.py  · tiempo.py
  auditoria.py            Registro de eventos de seguridad
  archivos.py             Subida segura de la tarjeta profesional
  correo.py               Plantillas y envío de correos
  api_externa.py          Cliente de la API de wearables
  metricas.py             Definición de métricas y rangos válidos
  servicios/              Lógica reutilizable: creditos.py, cuentas.py, referidos.py
  rutas_auth.py           Registro, ingreso, salida, cambio de contraseña
  rutas_cuentas.py        Perfil y directorio
  rutas_admin.py          Panel de validación de profesionales
  rutas_referidos.py      Código, puntos y canje por premium
  rutas_wearables.py      Dispositivos, sincronización y métricas
  rutas_consultas.py      Agenda, cobro, consentimiento, notas, historial
  rutas_alertas.py        Umbrales y notificaciones
  rutas_creditos.py       Saldo, movimientos y transferencias
  rutas_internas.py       Endpoints exclusivos de los robots
  seed.py                 Datos semilla
frontend/src/
  api.js · sesion.js · formato.js · router/index.js · App.vue
  components/Mensaje.vue
  views/                  Una vista por módulo (12 vistas)
worker/src/
  main.cpp                Ciclo y configuración   · http.cpp/.hpp  Cliente libcurl
  robot_validacion.cpp    Robot 1                 · robot_alertas.cpp  Robot 2
casos/healthsync/         Enunciado y caso.json (roles y cuentas de prueba)
mock-api/                 Simulador de la API externa
scripts/                  empaquetar.py (ZIP de entrega) · prueba_flujos.py (pruebas)
```

**Convenciones:** código y mensajes en español; un archivo de rutas (*blueprint*) por módulo; las reglas de negocio compartidas viven en `servicios/`; cada archivo empieza con un docstring que explica su propósito y sus reglas.

## 6. Referencia de la API

Todas las rutas empiezan por `/api`. Excepto registro e ingreso, exigen sesión; las que modifican datos exigen además el encabezado `X-CSRF-Token` (se obtiene en `/auth/ingresar` o `/auth/yo`).

| Módulo | Método y ruta | Rol | Descripción |
|---|---|---|---|
| Auth | `POST /auth/registro` (multipart) | público | Registro de paciente o profesional |
| | `POST /auth/ingresar` · `/auth/salir` · `GET /auth/yo` | — | Sesión |
| | `POST /auth/cambiar-password` | cualquiera | Cambia la contraseña y cierra otras sesiones |
| Cuenta | `GET/PUT /perfil` · `GET /directorio?q=` | sesión | Perfil propio y directorio de profesionales |
| Admin | `GET /admin/solicitudes?estado=` · `GET /admin/solicitudes/<id>/tarjeta` | admin | Solicitudes y foto de la tarjeta |
| | `POST /admin/solicitudes/<id>/aprobar` · `/rechazar` | admin | Resolver (el rechazo exige motivo) |
| Referidos | `GET /referidos` · `POST /referidos/canjear` | paciente, profesional | Código, puntos y canje |
| Wearables | `GET/POST /wearables/dispositivos` · `DELETE …/<id>` | paciente | Vincular y desvincular |
| | `POST /wearables/dispositivos/<id>/sincronizar` | paciente | Importar desde la API externa |
| | `GET /wearables/metricas` · `GET /wearables/resumen` · `POST /wearables/metricas` | paciente | Historial, última lectura y lectura manual |
| Consultas | `GET /consultas` · `GET /consultas/<id>` | paciente, profesional | Historial y detalle (solo participantes) |
| | `POST /consultas` | paciente | Agendar y pagar |
| | `POST /consultas/<id>/cancelar` | participantes | Cancelar con reembolso |
| | `POST /consultas/<id>/iniciar` · `/finalizar` · `PUT …/notas` · `GET …/metricas` | profesional | Realizar la consulta |
| | `PUT /consultas/<id>/consentimiento` | paciente | Autorizar o retirar el acceso a métricas |
| Alertas | `GET/POST /alertas` · `PUT/DELETE /alertas/<id>` · `GET /alertas/disparos` | paciente | Configurar e historial |
| | `GET /alertas/recibidas` | profesional | Alertas autorizadas por pacientes |
| Créditos | `GET /creditos` · `POST /creditos/transferir` | paciente, profesional | Saldo, movimientos y transferencias |
| Interno | `GET /internal/validacion/pendientes` · `POST …/<id>/validar` | robot | Robot de validación |
| | `GET /internal/alertas/evaluar` · `POST …/<id>/disparar` | robot | Robot de alertas |

**Reglas de negocio clave:** el bono de bienvenida de un paciente es 100 créditos; un referido completado da 50 puntos; un mes premium cuesta 100 puntos; una consulta dura 30 minutos y se cobra al confirmar (los créditos quedan retenidos y pasan al profesional al finalizar; si se cancela, vuelven al paciente); una transferencia admite hasta 1000 créditos. Son configurables en `.env`.

## 7. Decisiones de seguridad

La plantilla original no es segura (SQL concatenado, MD5, asignación masiva en el perfil, `system()` en C++, CORS abierto, errores con traza...). Estas son las decisiones tomadas y por qué:

| Riesgo | Qué se hizo |
|---|---|
| Inyección SQL | Todas las consultas usan parámetros (`%s`); el único SQL armado dinámicamente usa marcadores y listas fijas. Las búsquedas escapan `%` y `_`. |
| Almacenamiento de contraseñas | `scrypt` con sal por usuario (Werkzeug). Política de 10+ caracteres con letras y números, sin contraseñas comunes. |
| Fuerza bruta y enumeración | Bloqueo temporal de la cuenta tras 5 intentos fallidos; mismo mensaje y tiempo para "no existe" y "clave incorrecta"; el registro responde igual si el correo ya existe. |
| Sesiones | Cookie `HttpOnly`, `SameSite=Lax`, caducidad de 2 h, sin `localStorage`. El rol y estado se leen de la base en **cada petición**; al salir o cambiar la contraseña la cookie anterior queda invalidada. |
| CSRF | Token por sesión en la cabecera `X-CSRF-Token`, comparado en tiempo constante; las peticiones JSON además exigen `Content-Type: application/json`. |
| Control de acceso (IDOR) | Decoradores por rol en cada ruta; el id del usuario sale siempre de la sesión. Las consultas de otras personas responden 404. No existe una ruta que lea cuentas ajenas por id. |
| Datos clínicos | Métricas visibles al profesional solo con **consentimiento explícito por consulta** y con la consulta en curso. Cada acceso queda registrado. Las alertas llegan a un profesional solo si el paciente lo autorizó. |
| Dinero | Transacciones con `SELECT … FOR UPDATE` en orden fijo (sin condiciones de carrera ni interbloqueos), libro contable de movimientos y saldos `UNSIGNED` como segunda barrera. |
| Subida de archivos | Tipo detectado por *magic bytes* (PNG/JPEG), máximo 2 MB, nombre aleatorio fuera de la carpeta web, entrega solo a administradores con `nosniff`. |
| Errores | Respuestas JSON genéricas; las trazas solo van al log del servidor. |
| Cabeceras y exposición | CSP estricta, `X-Frame-Options`, `nosniff`, `Referrer-Policy`; puertos solo en `127.0.0.1`; MySQL no se publica; `/api/internal` bloqueado en nginx y protegido con token. |
| Robots C++ | Sin `system()` ni buffers fijos; ejecutable endurecido (PIE, RELRO, *stack protector*, FORTIFY); contenedor sin privilegios. Los robots **proponen y el backend decide**: se revalida cada condición. Protocolo de solo números e identificadores. |
| Contenedores y secretos | Usuarios sin privilegios, `no-new-privileges`, `cap_drop: ALL`; `.env` fuera de las imágenes y del ZIP; cada servicio recibe solo las variables que necesita; usuario de BD sin acceso a otras bases. |
| SSRF | El cliente de la API externa solo usa rutas relativas a la URL configurada; no sigue redirecciones. |
| Trazabilidad | Tabla `eventos_seguridad` (ingresos, aprobaciones, transferencias, accesos a métricas...) sin guardar contraseñas ni datos clínicos. |

## 8. Pruebas automáticas

Con la aplicación levantada:

```bash
pip install requests
python scripts/prueba_flujos.py            # usa http://localhost:8080 y lee .env
```

Ejecuta ~90 comprobaciones de extremo a extremo (registro, validación, referidos, wearables, consultas, créditos, alertas con los robots, y casos negativos de seguridad: SQLi, IDOR, CSRF, subida maliciosa, bloqueo de cuenta...). Termina con código 0 si todo pasa. Crea cuentas con correos aleatorios, por lo que se puede repetir.

## 9. Problemas comunes

- **El puerto 8080 o 8025 está ocupado.** Cambie el número de la izquierda en `ports` del servicio en `docker-compose.yml`.
- **Error `Defina SECRET_KEY en .env`** (o similar): no creó el `.env`. Ejecute `cp .env.example .env`.
- **Cambié un `.sql` y no se refleja.** Esos scripts solo corren al crear el volumen: `docker compose down -v`.
- **El servicio `seed` falla.** `docker compose logs seed`. Si cambió `CASO` o las contraseñas después de arrancar, haga `docker compose down -v`.
- **No llegan correos.** Revise http://localhost:8025 (Mailpit captura todo; nada sale a Internet).
- **La solicitud de un profesional se aprobó sola.** Es el robot de validación (cada minuto). Para aprobar manualmente use `pendiente2@healthsync.test` o `docker compose stop worker`.

## 10. Generar el ZIP de entrega

1. Diligencie `ENTREGA.md` (grupo, integrantes y fecha).
2. Verifique el arranque desde cero: `docker compose down -v && docker compose up --build`.
3. `python scripts/empaquetar.py --grupo IDENTIFICADOR` (sin Python: `docker run --rm -v "${PWD}:/p" -w /p python:3.13-slim python scripts/empaquetar.py --grupo IDENTIFICADOR`).
4. Suba `entregas/<grupo>-<fecha>.zip` a la plataforma y registre la huella SHA-256 que imprime el script. El ZIP excluye `.env`, `node_modules`, `dist`, `.git` y los compilados.
