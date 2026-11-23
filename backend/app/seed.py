"""Datos semilla de HealthSync. Se ejecuta en cada arranque (servicio "seed") y es idempotente:
si una cuenta ya existe no se toca, y los datos de ejemplo solo se crean la primera vez.

Crea:
  * administradores, pacientes y profesionales de prueba (caso.json), todos con SEED_PASSWORD
    (el administrador principal usa ADMIN_PASSWORD);
  * dispositivos, métricas, alertas, consultas (completada, confirmada y en curso), un referido
    y dos solicitudes de profesional pendientes (una con documentación completa y otra incompleta);
  * imágenes de ejemplo generadas por este script como "tarjeta profesional" (no son documentos reales).

Todo se crea con los mismos servicios que usa la aplicación, de modo que saldos y libros
contables quedan coherentes.
"""
import os
import random
import struct
import sys
import time
import zlib
from datetime import date, timedelta

import mysql.connector
from flask import current_app

from . import archivos, create_app
from .config import cargar_caso, parametros_db
from .db import confirmar, consultar, ejecutar, revertir
from .seguridad import hash_password
from .servicios import creditos, cuentas
from .tiempo import ahora_utc


def esperar_base_de_datos(intentos: int = 30) -> None:
    for intento in range(1, intentos + 1):
        try:
            mysql.connector.connect(**parametros_db()).close()
            return
        except mysql.connector.Error as error:
            print(f"[seed] Base de datos no disponible (intento {intento}): {error}", flush=True)
            time.sleep(2)
    raise SystemExit("[seed] No fue posible conectarse a la base de datos.")


def png_de_ejemplo(ancho: int = 160, alto: int = 100, color=(40, 90, 160)) -> bytes:
    """Genera un PNG válido (rectángulo de color con una franja) sin depender de librerías de imágenes."""
    filas = b""
    for y in range(alto):
        fila = b"\x00"
        for x in range(ancho):
            en_franja = 30 <= y <= 40
            fila += bytes((255, 255, 255) if en_franja else color)
        filas += fila

    def bloque(tipo: bytes, datos: bytes) -> bytes:
        return struct.pack(">I", len(datos)) + tipo + datos + struct.pack(">I", zlib.crc32(tipo + datos) & 0xFFFFFFFF)

    return (
        b"\x89PNG\r\n\x1a\n"
        + bloque(b"IHDR", struct.pack(">IIBBBBB", ancho, alto, 8, 2, 0, 0, 0))
        + bloque(b"IDAT", zlib.compress(filas))
        + bloque(b"IEND", b"")
    )


def id_de(email: str) -> int | None:
    fila = consultar("SELECT id FROM cuentas WHERE email = %s", (email,), uno=True)
    return fila["id"] if fila else None


def crear_cuenta_activa(nombre, email, password, rol, nacimiento, especialidad=None, tarifa=None, descripcion="") -> int:
    """Crea y activa una cuenta (si no existe). Devuelve su id."""
    existente = id_de(email)
    if existente:
        return existente
    perfil = None
    if rol == "profesional":
        nombre_archivo, mime = archivos.guardar_bytes_imagen(png_de_ejemplo())
        perfil = {"especialidad": especialidad or "Medicina general", "tarjeta_archivo": nombre_archivo, "tarjeta_mime": mime}
    cuenta_id = cuentas.crear(nombre, email, hash_password(password), rol, nacimiento, perfil)
    cuentas.activar(cuenta_id)
    if rol == "profesional":
        ejecutar(
            "UPDATE perfiles_profesionales SET tarifa_creditos = %s, descripcion = %s WHERE cuenta_id = %s",
            (tarifa or 20, descripcion, cuenta_id),
        )
    return cuenta_id


def crear_solicitud_pendiente(nombre, email, password, nacimiento, especialidad, con_tarjeta: bool) -> None:
    if id_de(email):
        return
    perfil = {"especialidad": especialidad, "tarjeta_archivo": None, "tarjeta_mime": None}
    if con_tarjeta:
        perfil["tarjeta_archivo"], perfil["tarjeta_mime"] = archivos.guardar_bytes_imagen(png_de_ejemplo(color=(120, 60, 60)))
    cuentas.crear(nombre, email, hash_password(password), "profesional", nacimiento, perfil)


def sembrar_metricas(paciente_id: int, dispositivo_id: int, semilla: int) -> None:
    """72 horas de frecuencia cardíaca y oxígeno, y 3 días de pasos y sueño. La última lectura siempre es normal."""
    azar = random.Random(semilla)
    ahora = ahora_utc().replace(minute=0, second=0, microsecond=0)
    filas = []
    for horas in range(72):
        momento = ahora - timedelta(hours=horas)
        pulso = 138 if horas == 30 else azar.randint(60, 98)      # un valor atípico histórico
        oxigeno = 90 if horas == 31 else azar.randint(95, 99)
        filas.append((paciente_id, dispositivo_id, "heart-rate", pulso, "beats/min", momento))
        filas.append((paciente_id, dispositivo_id, "oxygen-saturation", oxigeno, "%", momento))
    for dias in range(3):
        momento = ahora.replace(hour=0) - timedelta(days=dias)
        filas.append((paciente_id, dispositivo_id, "step-count", azar.randint(3000, 10500), "steps", momento))
        filas.append((paciente_id, dispositivo_id, "sleep-duration", azar.randint(5, 9), "h", momento))
    for fila in filas:
        ejecutar(
            "INSERT INTO metricas (paciente_id, dispositivo_id, tipo, valor, unidad, medido_en, fuente) "
            "VALUES (%s, %s, %s, %s, %s, %s, 'wearable') ON DUPLICATE KEY UPDATE id = id",
            fila,
        )


def sembrar_consulta(paciente_id, profesional_id, inicio, motivo, estado, costo, diagnostico=None, notas=None, consentimiento=False):
    """Inserta una consulta con los asientos de crédito que le corresponden según su estado."""
    consulta_id = ejecutar(
        "INSERT INTO consultas (paciente_id, profesional_id, inicio, motivo, estado, costo_creditos, diagnostico_resumido, "
        "notas_clinicas, consentimiento_metricas, consentimiento_en) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (paciente_id, profesional_id, inicio, motivo, estado, costo, diagnostico, notas, 1 if consentimiento else 0,
         ahora_utc() if consentimiento else None),
    )
    saldos = creditos.bloquear(paciente_id, profesional_id)
    creditos.aplicar(paciente_id, -costo, "pago_consulta", saldos, profesional_id, f"consulta:{consulta_id}")
    if estado == "completada":
        creditos.aplicar(profesional_id, costo, "cobro_consulta", saldos, paciente_id, f"consulta:{consulta_id}")


def sembrar_datos_de_ejemplo(ids: dict) -> None:
    """Datos de negocio. Solo se crean si todavía no hay consultas (primera ejecución)."""
    if consultar("SELECT id FROM consultas LIMIT 1", uno=True):
        return
    ahora = ahora_utc().replace(second=0, microsecond=0)
    p1, p2 = ids["paciente1"], ids["paciente2"]
    d1, d2 = ids["profesional1"], ids["profesional2"]

    # Dispositivos y métricas (el id_externo es el que usa el simulador de Open mHealth).
    disp1 = ejecutar("INSERT INTO dispositivos (paciente_id, nombre, proveedor, id_externo) VALUES (%s, 'Reloj de Paciente Uno', 'Garmin', 'semilla-paciente1')", (p1,))
    disp2 = ejecutar("INSERT INTO dispositivos (paciente_id, nombre, proveedor, id_externo) VALUES (%s, 'Banda de Paciente Dos', 'Xiaomi', 'semilla-paciente2')", (p2,))
    sembrar_metricas(p1, disp1, 11)
    sembrar_metricas(p2, disp2, 22)

    # Alertas: la del paciente 1 avisa también al profesional 1 (con autorización); la del 2 no.
    ejecutar("INSERT INTO alertas (paciente_id, tipo_metrica, operador, umbral, notificar_profesional, profesional_id) VALUES (%s, 'heart-rate', 'mayor', 120, 1, %s)", (p1, d1))
    ejecutar("INSERT INTO alertas (paciente_id, tipo_metrica, operador, umbral) VALUES (%s, 'oxygen-saturation', 'menor', 92)", (p2,))

    # Consultas: una completada (con notas), una confirmada futura y una en curso con consentimiento.
    sembrar_consulta(p1, d1, ahora - timedelta(days=5), "Control de rutina", "completada", 20,
                     "Control general sin hallazgos relevantes", "Paciente en buen estado. Se recomienda actividad física regular.")
    sembrar_consulta(p1, d2, ahora + timedelta(days=2, hours=3), "Dolor de cabeza frecuente", "confirmada", 30)
    sembrar_consulta(p2, d1, ahora - timedelta(minutes=10), "Revisión de la frecuencia cardíaca", "en_curso", 20, consentimiento=True)

    # Referido: el paciente 2 se registró con el código del paciente 1 (el referidor ya ganó sus puntos).
    puntos = current_app.config["PUNTOS_POR_REFERIDO"]
    ejecutar("INSERT INTO referidos (referidor_id, referido_id, estado, puntos, completado_en) VALUES (%s, %s, 'completado', %s, UTC_TIMESTAMP())", (p1, p2, puntos))
    ejecutar("UPDATE billeteras SET puntos = puntos + %s WHERE cuenta_id = %s", (puntos, p1))
    ejecutar("INSERT INTO movimientos_puntos (cuenta_id, tipo, puntos, referencia) VALUES (%s, 'referido', %s, %s)", (p1, puntos, f"referido:{p2}"))


def main() -> int:
    caso = cargar_caso()
    if caso["clave"] != "healthsync":
        print(f"[seed] Esta versión del proyecto solo incluye datos del caso HealthSync (CASO={caso['clave']}).", flush=True)
        return 1
    esperar_base_de_datos()

    app = create_app()
    with app.app_context():
        try:
            clave = os.environ.get("SEED_PASSWORD", "")
            admin_clave = os.environ.get("ADMIN_PASSWORD", "")
            if not clave or not admin_clave:
                raise SystemExit("[seed] Defina SEED_PASSWORD y ADMIN_PASSWORD en .env.")

            crear_cuenta_activa("Administrador", os.environ.get("ADMIN_EMAIL", "admin@healthsync.test"), admin_clave, "admin", date(1985, 1, 15))
            especialidades = {"profesional1@healthsync.test": ("Cardiología", 20, "Cardiólogo con 10 años de experiencia."),
                              "profesional2@healthsync.test": ("Medicina general", 30, "Atención primaria y medicina preventiva.")}
            ids = {}
            for numero, cuenta in enumerate(caso.get("cuentas_prueba", []), start=1):
                esp, tarifa, desc = especialidades.get(cuenta["email"], (None, None, ""))
                ids[cuenta["email"].split("@")[0]] = crear_cuenta_activa(
                    cuenta["nombre"], cuenta["email"], clave, cuenta["rol"], date(1980 + numero, 5, 10), esp, tarifa, desc
                )
            crear_solicitud_pendiente("Profesional Pendiente", "pendiente1@healthsync.test", clave, date(1990, 3, 3), "Pediatría", True)
            crear_solicitud_pendiente("Profesional Sin Tarjeta", "pendiente2@healthsync.test", clave, date(1992, 8, 8), "Dermatología", False)

            sembrar_datos_de_ejemplo(ids)
            confirmar()
            print(f"[seed] Caso '{caso['clave']}': datos semilla listos.", flush=True)
            return 0
        except Exception:
            revertir()
            raise


if __name__ == "__main__":
    sys.exit(main())
