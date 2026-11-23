#!/usr/bin/env python3
"""Pruebas de flujo de extremo a extremo de HealthSync (sobre la aplicación en ejecución).

Uso (con la aplicación levantada):
    python scripts/prueba_flujos.py                          # contra http://localhost:8080
    python scripts/prueba_flujos.py --url http://localhost:8080 --correos http://localhost:8025

Lee SEED_PASSWORD y ADMIN_PASSWORD del archivo .env (o de variables de entorno).
Crea cuentas nuevas con correos aleatorios, así que se puede ejecutar varias veces.
No necesita nada más que Python 3 y la librería `requests`.
Termina con código 0 si todo pasa y 1 si algo falla.
"""
import argparse
import os
import secrets
import struct
import sys
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parent.parent
resultados = {"ok": 0, "fallos": []}


def leer_env() -> dict:
    valores = dict(os.environ)
    archivo = RAIZ / ".env"
    if archivo.exists():
        for linea in archivo.read_text(encoding="utf-8").splitlines():
            if "=" in linea and not linea.lstrip().startswith("#"):
                clave, _, valor = linea.partition("=")
                valores.setdefault(clave.strip(), valor.strip())
    return valores


def png_valido() -> bytes:
    """PNG mínimo válido para simular la foto de la tarjeta profesional."""
    def bloque(tipo, datos):
        return struct.pack(">I", len(datos)) + tipo + datos + struct.pack(">I", zlib.crc32(tipo + datos) & 0xFFFFFFFF)
    filas = b"".join(b"\x00" + bytes((30, 80, 150)) * 40 for _ in range(40))
    return (b"\x89PNG\r\n\x1a\n" + bloque(b"IHDR", struct.pack(">IIBBBBB", 40, 40, 8, 2, 0, 0, 0))
            + bloque(b"IDAT", zlib.compress(filas)) + bloque(b"IEND", b""))


def comprobar(condicion: bool, descripcion: str, detalle: str = "") -> bool:
    if condicion:
        resultados["ok"] += 1
        print(f"  ✔ {descripcion}")
    else:
        resultados["fallos"].append(descripcion)
        print(f"  ✘ {descripcion}  {detalle}")
    return condicion


class Cliente:
    """Sesión HTTP que recuerda la cookie y envía el token CSRF en las peticiones que modifican datos."""

    def __init__(self, base: str):
        self.base, self.http, self.csrf = base.rstrip("/"), requests.Session(), None

    def pedir(self, metodo, ruta, **kw):
        encabezados = kw.pop("headers", {})
        if self.csrf and metodo not in ("GET", "HEAD"):
            encabezados["X-CSRF-Token"] = self.csrf
        return self.http.request(metodo, self.base + ruta, headers=encabezados, timeout=20, **kw)

    def ingresar(self, email, password):
        r = self.pedir("POST", "/api/auth/ingresar", json={"email": email, "password": password})
        if r.status_code == 200:
            self.csrf = r.json()["csrf_token"]
        return r


def fecha_futura(dias: int, hora: int = 15, minuto: int = 0) -> str:
    momento = (datetime.now(timezone.utc) + timedelta(days=dias)).replace(hour=hora, minute=minuto, second=0, microsecond=0)
    return momento.isoformat().replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8080")
    parser.add_argument("--correos", default="http://localhost:8025", help="API de Mailpit (opcional)")
    args = parser.parse_args()
    env = leer_env()
    clave_seed = env.get("SEED_PASSWORD", "")
    clave_admin = env.get("ADMIN_PASSWORD", "")
    sufijo = secrets.token_hex(3)
    clave_nueva = f"Nueva#Clave{sufijo}9"

    anonimo = Cliente(args.url)
    print("\n== 1. Servicio y seguridad básica ==")
    comprobar(anonimo.pedir("GET", "/api/salud").status_code == 200, "El servicio responde")
    comprobar(anonimo.pedir("GET", "/api/directorio").status_code == 401, "El directorio exige sesión")
    comprobar(anonimo.pedir("GET", "/api/admin/solicitudes").status_code == 401, "El panel de admin exige sesión")
    r = anonimo.pedir("POST", "/api/auth/ingresar", json={"email": "' OR '1'='1' -- ", "password": "x"})
    comprobar(r.status_code == 401, "La inyección SQL en el login no da acceso", r.text[:80])
    r = anonimo.pedir("GET", "/api/ruta-inexistente")
    comprobar(r.status_code == 404 and "Traceback" not in r.text, "Los errores no exponen trazas")

    print("\n== 2. Registro de paciente y de profesional ==")
    email_pac, email_pro = f"pac-{sufijo}@prueba.test", f"pro-{sufijo}@prueba.test"
    nombre_pac, nombre_pro = f"Paciente {sufijo}", f"Profesional {sufijo}"  # únicos: el directorio acumula cuentas entre ejecuciones
    r = anonimo.pedir("POST", "/api/auth/registro", data={"nombre": nombre_pac, "email": email_pac, "password": "corta", "fecha_nacimiento": "1990-01-01", "rol": "paciente"})
    comprobar(r.status_code == 400, "Rechaza contraseñas débiles")
    r = anonimo.pedir("POST", "/api/auth/registro", data={"nombre": nombre_pac, "email": email_pac, "password": clave_nueva, "fecha_nacimiento": "2015-01-01", "rol": "paciente"})
    comprobar(r.status_code == 400, "Rechaza menores de edad")
    r = anonimo.pedir("POST", "/api/auth/registro", data={"nombre": nombre_pac, "email": email_pac, "password": clave_nueva, "fecha_nacimiento": "1990-01-01", "rol": "admin"})
    comprobar(r.status_code == 400, "No permite registrarse como administrador")

    # Código de referidos de Paciente Uno
    pac1 = Cliente(args.url)
    comprobar(pac1.ingresar("paciente1@healthsync.test", clave_seed).status_code == 200, "Ingresa Paciente Uno (semilla)")
    ref = pac1.pedir("GET", "/api/referidos").json()
    codigo, puntos_antes = ref["codigo"], ref["puntos"]

    r = anonimo.pedir("POST", "/api/auth/registro", data={"nombre": nombre_pac, "email": email_pac, "password": clave_nueva, "fecha_nacimiento": "1990-01-01", "rol": "paciente", "codigo_referido": codigo})
    comprobar(r.status_code == 201, "Registro de paciente con código de referidos", r.text[:100])
    r2 = anonimo.pedir("POST", "/api/auth/registro", data={"nombre": nombre_pac, "email": email_pac, "password": clave_nueva, "fecha_nacimiento": "1990-01-01", "rol": "paciente"})
    comprobar(r2.status_code == 201 and r2.json() == r.json(), "Correo repetido: misma respuesta (no revela cuentas existentes)")
    r = anonimo.pedir("POST", "/api/auth/registro", data={"nombre": nombre_pro, "email": email_pro, "password": clave_nueva, "fecha_nacimiento": "1985-06-06", "rol": "profesional", "especialidad": "Neurología"})
    comprobar(r.status_code == 400, "El profesional debe adjuntar la tarjeta")
    r = anonimo.pedir("POST", "/api/auth/registro", data={"nombre": nombre_pro, "email": email_pro, "password": clave_nueva, "fecha_nacimiento": "1985-06-06", "rol": "profesional"}, files={"tarjeta": ("x.png", b"<?php echo 1; ?>" * 10, "image/png")})
    comprobar(r.status_code == 400, "Rechaza un archivo que no es imagen aunque diga ser PNG")
    r = anonimo.pedir("POST", "/api/auth/registro", data={"nombre": nombre_pro, "email": email_pro, "password": clave_nueva, "fecha_nacimiento": "1985-06-06", "rol": "profesional", "especialidad": "Neurología", "codigo_referido": codigo}, files={"tarjeta": ("tarjeta.png", png_valido(), "image/png")})
    comprobar(r.status_code == 201, "Registro de profesional con foto de tarjeta", r.text[:100])

    pac = Cliente(args.url)
    comprobar(pac.ingresar(email_pac, clave_nueva).status_code == 200, "El paciente nuevo ingresa de inmediato")
    comprobar(Cliente(args.url).ingresar(email_pro, clave_nueva).status_code == 403, "El profesional pendiente NO puede ingresar")

    print("\n== 3. Validación por el administrador ==")
    admin = Cliente(args.url)
    comprobar(admin.ingresar(env.get("ADMIN_EMAIL", "admin@healthsync.test"), clave_admin).status_code == 200, "Ingresa el administrador")
    comprobar(pac.pedir("GET", "/api/admin/solicitudes").status_code == 403, "Un paciente no accede al panel de admin")
    # El robot de validación corre cada minuto y puede adelantarse al administrador: se busca en todas.
    lista = admin.pedir("GET", "/api/admin/solicitudes?estado=todos").json()["solicitudes"]
    solicitud = next((s for s in lista if s["email"] == email_pro), None)
    comprobar(solicitud is not None and solicitud["documentacion_completa"], "La solicitud aparece con la documentación completa")
    if solicitud:
        img = admin.pedir("GET", f"/api/admin/solicitudes/{solicitud['id']}/tarjeta")
        comprobar(img.status_code == 200 and img.headers["Content-Type"] == "image/png", "El admin ve la foto de la tarjeta")
        comprobar(pac.pedir("GET", f"/api/admin/solicitudes/{solicitud['id']}/tarjeta").status_code == 403, "Un paciente no ve tarjetas de otros")
        aprobada = admin.pedir("POST", f"/api/admin/solicitudes/{solicitud['id']}/aprobar", json={}).status_code
        comprobar(aprobada in (200, 409), "El profesional queda aprobado (por el admin o, si se adelantó, por el robot)")
        comprobar(admin.pedir("POST", f"/api/admin/solicitudes/{solicitud['id']}/aprobar", json={}).status_code == 409, "No se puede aprobar dos veces")
    sin_tarjeta = next((s for s in admin.pedir("GET", "/api/admin/solicitudes").json()["solicitudes"] if s["email"] == "pendiente2@healthsync.test"), None)
    if sin_tarjeta:
        comprobar(admin.pedir("POST", f"/api/admin/solicitudes/{sin_tarjeta['id']}/aprobar", json={}).status_code == 409, "No se aprueba con documentación incompleta")
        comprobar(admin.pedir("POST", f"/api/admin/solicitudes/{sin_tarjeta['id']}/rechazar", json={"motivo": "x"}).status_code == 400, "El rechazo exige un motivo")
    pro = Cliente(args.url)
    comprobar(pro.ingresar(email_pro, clave_nueva).status_code == 200, "El profesional aprobado ya ingresa")
    directorio = pac.pedir("GET", f"/api/directorio?q={nombre_pro}").json()["resultados"]
    comprobar(any(d["nombre"] == nombre_pro for d in directorio), "El profesional aparece en el directorio")
    id_pro = next(d["id"] for d in directorio if d["nombre"] == nombre_pro)
    ref = pac1.pedir("GET", "/api/referidos").json()
    comprobar(ref["puntos"] == puntos_antes + 2 * ref["puntos_por_referido"], "El referidor ganó puntos por los 2 referidos", f"{puntos_antes} -> {ref['puntos']}")
    r = pac1.pedir("POST", "/api/referidos/canjear", json={"meses": 1})
    comprobar(r.status_code == (200 if ref["puntos"] >= ref["puntos_por_mes"] else 409), "Canje de puntos por premium", r.text[:100])
    comprobar(pac1.pedir("POST", "/api/referidos/canjear", json={"meses": 99}).status_code == 400, "Canje con meses inválidos rechazado")
    r = anonimo.pedir("POST", "/api/auth/registro", data={"nombre": "X Y", "email": f"z{sufijo}@prueba.test", "password": clave_nueva, "fecha_nacimiento": "1990-01-01", "rol": "paciente", "codigo_referido": "NOEXISTE"})
    comprobar(r.status_code == 400, "Código de referidos inexistente rechazado")

    print("\n== 4. Wearables ==")
    r = pac.pedir("POST", "/api/wearables/dispositivos", json={"nombre": "Mi reloj", "proveedor": "Garmin"})
    comprobar(r.status_code == 201, "Vincula un dispositivo", r.text[:100])
    id_disp = r.json()["id"]
    r = pac.pedir("POST", f"/api/wearables/dispositivos/{id_disp}/sincronizar", json={"dias": 3})
    comprobar(r.status_code == 200 and r.json()["nuevas"] > 0, "Sincroniza métricas desde la API externa", r.text[:120])
    n1 = r.json().get("nuevas", 0)
    r = pac.pedir("POST", f"/api/wearables/dispositivos/{id_disp}/sincronizar", json={"dias": 3})
    comprobar(r.status_code == 200 and r.json()["nuevas"] == 0, "Sincronizar de nuevo no duplica datos", r.text[:120])
    metricas = pac.pedir("GET", "/api/wearables/metricas?dias=7").json()["metricas"]
    comprobar(len(metricas) >= n1, "Lista el historial de métricas")
    comprobar(pac1.pedir("POST", f"/api/wearables/dispositivos/{id_disp}/sincronizar", json={}).status_code == 404, "No se puede sincronizar el dispositivo de otro paciente")
    comprobar(pro.pedir("GET", "/api/wearables/dispositivos").status_code == 403, "Un profesional no usa el módulo de wearables")
    comprobar(pac.pedir("POST", "/api/wearables/metricas", json={"tipo": "heart-rate", "valor": 9999}).status_code == 400, "Rechaza lecturas imposibles")
    comprobar(pac.pedir("POST", "/api/wearables/metricas", json={"tipo": "heart-rate", "valor": 80}).status_code == 201, "Registra una lectura manual normal")

    print("\n== 5. Consultas y créditos ==")
    saldo0 = pac.pedir("GET", "/api/creditos").json()["saldo"]
    inicio = fecha_futura(3, 15, 0)
    r = pac.pedir("POST", "/api/consultas", json={"profesional_id": id_pro, "inicio": inicio, "motivo": "Mareos frecuentes"})
    comprobar(r.status_code == 201, "Agenda y confirma una consulta", r.text[:120])
    id_cons, costo = r.json()["id"], r.json()["costo"]
    comprobar(pac.pedir("GET", "/api/creditos").json()["saldo"] == saldo0 - costo, "Se descontó el costo del saldo del paciente")
    comprobar(pac.pedir("POST", "/api/consultas", json={"profesional_id": id_pro, "inicio": fecha_futura(3, 15, 10), "motivo": "Otro motivo"}).status_code == 409, "No permite horarios que se cruzan")
    comprobar(pac.pedir("POST", "/api/consultas", json={"profesional_id": id_pro, "inicio": "2020-01-01T10:00:00Z", "motivo": "Pasado"}).status_code == 400, "No permite fechas pasadas")
    comprobar(pro.pedir("POST", "/api/consultas", json={"profesional_id": id_pro, "inicio": inicio, "motivo": "xx"}).status_code == 403, "Un profesional no agenda consultas")
    otro = Cliente(args.url); otro.ingresar("paciente2@healthsync.test", clave_seed)
    comprobar(otro.pedir("GET", f"/api/consultas/{id_cons}").status_code == 404, "Otro paciente NO ve la consulta (control de acceso)")
    comprobar(otro.pedir("POST", f"/api/consultas/{id_cons}/cancelar", json={}).status_code == 404, "Otro paciente no puede cancelarla")
    comprobar(pac.pedir("POST", f"/api/consultas/{id_cons}/iniciar", json={}).status_code == 403, "El paciente no puede iniciar la consulta")
    comprobar(pro.pedir("POST", f"/api/consultas/{id_cons}/iniciar", json={}).status_code == 200, "El profesional inicia la consulta")
    comprobar(pro.pedir("GET", f"/api/consultas/{id_cons}/metricas").status_code == 403, "Sin consentimiento no ve las métricas")
    comprobar(pac.pedir("PUT", f"/api/consultas/{id_cons}/consentimiento", json={"otorgado": True}).status_code == 200, "El paciente da su consentimiento")
    r = pro.pedir("GET", f"/api/consultas/{id_cons}/metricas")
    comprobar(r.status_code == 200 and len(r.json()["metricas"]) > 0, "Con consentimiento el profesional ve las métricas")
    comprobar(pro.pedir("POST", f"/api/consultas/{id_cons}/finalizar", json={}).status_code == 400, "No se finaliza sin diagnóstico")
    comprobar(pac.pedir("PUT", f"/api/consultas/{id_cons}/notas", json={"diagnostico_resumido": "hack"}).status_code == 403, "El paciente no escribe notas clínicas")
    comprobar(pro.pedir("PUT", f"/api/consultas/{id_cons}/notas", json={"diagnostico_resumido": "Cuadro de estrés leve", "notas_clinicas": "Se recomienda descanso.\nControl en 1 mes."}).status_code == 200, "El profesional registra diagnóstico y notas")
    saldo_pro0 = pro.pedir("GET", "/api/creditos").json()["saldo"]
    comprobar(pro.pedir("POST", f"/api/consultas/{id_cons}/finalizar", json={}).status_code == 200, "Finaliza la consulta")
    comprobar(pro.pedir("GET", "/api/creditos").json()["saldo"] == saldo_pro0 + costo, "Se acreditó el pago al profesional")
    comprobar(pac.pedir("PUT", f"/api/consultas/{id_cons}/consentimiento", json={"otorgado": False}).status_code == 409, "El consentimiento ya no cambia tras terminar")
    comprobar(pro.pedir("GET", f"/api/consultas/{id_cons}/metricas").status_code == 409, "Terminada la consulta no se ven más métricas")
    hist = pac.pedir("GET", "/api/consultas").json()["consultas"]
    comprobar(any(c["id"] == id_cons and c["diagnostico_resumido"] and c["notas_clinicas"] for c in hist), "El historial muestra diagnóstico, notas y costo")

    # Cancelación con reembolso y saldo insuficiente
    s_antes = pac.pedir("GET", "/api/creditos").json()["saldo"]
    r = pac.pedir("POST", "/api/consultas", json={"profesional_id": id_pro, "inicio": fecha_futura(4, 10, 0), "motivo": "Consulta a cancelar"})
    id_c2 = r.json()["id"]
    comprobar(pac.pedir("POST", f"/api/consultas/{id_c2}/cancelar", json={}).status_code == 200, "Cancela una consulta confirmada")
    comprobar(pac.pedir("GET", "/api/creditos").json()["saldo"] == s_antes, "Se reembolsó el costo completo")
    comprobar(pac.pedir("POST", f"/api/consultas/{id_c2}/cancelar", json={}).status_code == 409, "No se cancela dos veces (sin doble reembolso)")
    pro.pedir("PUT", "/api/perfil", json={"tarifa_creditos": 1000})
    comprobar(pac.pedir("POST", "/api/consultas", json={"profesional_id": id_pro, "inicio": fecha_futura(5, 10, 0), "motivo": "Sin saldo suficiente"}).status_code == 409, "Rechaza si el saldo no alcanza")
    pro.pedir("PUT", "/api/perfil", json={"tarifa_creditos": costo})

    print("\n== 6. Transferencias ==")
    s = pac.pedir("GET", "/api/creditos").json()["saldo"]
    r = pac.pedir("POST", "/api/creditos/transferir", json={"email": "paciente2@healthsync.test", "monto": 10, "nota": "Prueba"})
    comprobar(r.status_code == 200 and r.json()["saldo"] == s - 10, "Transfiere créditos a otro usuario", r.text[:100])
    comprobar(pac.pedir("POST", "/api/creditos/transferir", json={"email": "paciente2@healthsync.test", "monto": 10**6}).status_code == 400, "Rechaza montos sobre el límite")
    comprobar(pac.pedir("POST", "/api/creditos/transferir", json={"email": "paciente2@healthsync.test", "monto": -5}).status_code == 400, "Rechaza montos negativos")
    comprobar(pac.pedir("POST", "/api/creditos/transferir", json={"email": email_pac, "monto": 5}).status_code == 400, "Rechaza transferirse a sí mismo")
    comprobar(pac.pedir("POST", "/api/creditos/transferir", json={"email": "nadie@prueba.test", "monto": 5}).status_code == 404, "Rechaza destinatarios inexistentes")
    comprobar(pac.pedir("POST", "/api/creditos/transferir", json={"email": "paciente2@healthsync.test", "monto": 1000}).status_code == 409, "Rechaza si el saldo no alcanza")
    comprobar(pac.pedir("POST", "/api/creditos/transferir", json={"email": "paciente2@healthsync.test", "monto": 1.5}).status_code == 400, "Rechaza montos decimales")
    comprobar(admin.pedir("GET", "/api/creditos").status_code == 403, "El administrador no tiene billetera")

    print("\n== 7. Alertas ==")
    r = pac.pedir("POST", "/api/alertas", json={"tipo_metrica": "heart-rate", "operador": "mayor", "umbral": 120, "notificar_profesional": True, "profesional_id": id_pro})
    comprobar(r.status_code == 201, "Crea una alerta autorizando avisar al profesional", r.text[:100])
    id_alerta = r.json()["id"]
    comprobar(pac.pedir("POST", "/api/alertas", json={"tipo_metrica": "heart-rate", "operador": "mayor", "umbral": 120, "notificar_profesional": True}).status_code == 400, "Avisar al profesional exige elegirlo")
    comprobar(pac.pedir("POST", "/api/alertas", json={"tipo_metrica": "heart-rate", "operador": "mayor", "umbral": 120, "notificar_profesional": True, "profesional_id": 1}).status_code == 404, "No se puede elegir como profesional a un admin")
    comprobar(otro.pedir("DELETE", f"/api/alertas/{id_alerta}").status_code == 404, "Otro paciente no borra mi alerta")
    comprobar(pac.pedir("PUT", f"/api/alertas/{id_alerta}", json={"activa": False}).status_code == 200, "Pausa la alerta")
    comprobar(pac.pedir("PUT", f"/api/alertas/{id_alerta}", json={"activa": True}).status_code == 200, "Reactiva la alerta")
    comprobar(pac.pedir("POST", "/api/wearables/metricas", json={"tipo": "heart-rate", "valor": 150}).status_code == 201, "Registra lectura de 150 lpm (el robot debe disparar la alerta)")
    import time
    disparos = []
    for _ in range(15):  # el robot revisa cada segundo
        disparos = pac.pedir("GET", "/api/alertas/disparos").json()["disparos"]
        if disparos:
            break
        time.sleep(1)
    comprobar(bool(disparos), "El robot disparó la alerta (esperando hasta 15 s)")
    if disparos:
        comprobar(disparos[0]["correo_paciente"] == 1 and disparos[0]["correo_profesional"] == 1, "Se enviaron los correos al paciente y al profesional")
        comprobar(any(d["paciente"] == nombre_pac for d in pro.pedir("GET", "/api/alertas/recibidas").json()["disparos"]), "El profesional ve la alerta autorizada")
        time.sleep(3)
        comprobar(len(pac.pedir("GET", "/api/alertas/disparos").json()["disparos"]) == len(disparos), "No se repite el aviso para la misma lectura")

    print("\n== 8. Sesión y cuenta ==")
    comprobar(pac.pedir("PUT", "/api/perfil", json={"nombre": "Ana P. Prueba", "rol": "admin", "estado": "activo"}).json()["cuenta"]["rol"] == "paciente", "El perfil ignora campos como rol (sin asignación masiva)")
    sin_csrf = Cliente(args.url); sin_csrf.http.cookies = pac.http.cookies.copy()
    comprobar(sin_csrf.pedir("PUT", "/api/perfil", json={"nombre": "Hack"}).status_code == 403, "Sin token CSRF la petición se rechaza")
    comprobar(pac.pedir("POST", "/api/auth/cambiar-password", json={"password_actual": "mala", "password_nueva": clave_nueva + "x"}).status_code == 403, "Cambio de contraseña exige la actual")
    victima = f"bloqueo-{sufijo}@prueba.test"
    anonimo.pedir("POST", "/api/auth/registro", data={"nombre": "Victima Uno", "email": victima, "password": clave_nueva, "fecha_nacimiento": "1990-01-01", "rol": "paciente"})
    codigos = [anonimo.pedir("POST", "/api/auth/ingresar", json={"email": victima, "password": "incorrecta1234"}).status_code for _ in range(6)]
    comprobar(codigos[-1] == 429, "La cuenta se bloquea tras varios intentos fallidos", str(codigos))
    comprobar(anonimo.pedir("POST", "/api/auth/ingresar", json={"email": victima, "password": clave_nueva}).status_code == 429, "Bloqueada: ni la clave correcta entra")
    viejo = Cliente(args.url); viejo.http.cookies = pac.http.cookies.copy(); viejo.csrf = pac.csrf
    pac.pedir("POST", "/api/auth/salir", json={})
    comprobar(viejo.pedir("GET", "/api/perfil").status_code == 401, "Al salir, la cookie anterior deja de funcionar")

    # Correos recibidos (solo si Mailpit está disponible)
    try:
        asuntos = [m["Subject"] for m in requests.get(args.correos + "/api/v1/messages", timeout=5).json().get("messages", [])]
        for esperado in ("Registro recibido", "Consulta confirmada", "Alerta de salud", "Recibió créditos", "Su cuenta fue activada"):
            comprobar(any(esperado in a for a in asuntos), f"Mailpit recibió un correo '{esperado}'")
    except Exception:
        print("  (Mailpit no disponible: se omite la verificación de correos)")

    print(f"\nResultado: {resultados['ok']} pruebas correctas, {len(resultados['fallos'])} fallidas.")
    for f in resultados["fallos"]:
        print(f"  ✘ {f}")
    return 1 if resultados["fallos"] else 0


if __name__ == "__main__":
    sys.exit(main())
