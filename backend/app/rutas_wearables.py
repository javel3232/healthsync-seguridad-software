"""Módulo 2 - Sincronización de dispositivos wearables.

El paciente vincula un dispositivo, y la plataforma importa sus métricas desde la
API externa (Open mHealth, simulada por defecto), las normaliza y las guarda en
su perfil de salud. También puede registrar una lectura manual, útil cuando no
hay dispositivo y para probar las alertas.

Solo los pacientes usan este módulo, y siempre sobre sus propios datos: el id
del paciente sale de la sesión, nunca de la petición.
"""
import secrets
from datetime import timedelta

from flask import Blueprint, current_app, jsonify, request

from . import api_externa, auditoria, validaciones as v
from .db import confirmar, consultar, ejecutar, ejecutar_muchos
from .errores import ErrorNegocio
from .metricas import TIPOS
from .seguridad import rol_requerido, usuario_actual
from .tiempo import ahora_utc

bp = Blueprint("wearables", __name__, url_prefix="/api/wearables")

PROVEEDORES = ("Fitbit", "Garmin", "Apple Watch", "Xiaomi", "Samsung", "Otro")
MAX_PUNTOS_POR_ESQUEMA = 2000


@bp.before_request
@rol_requerido("paciente")
def solo_pacientes():
    """Todo el módulo es exclusivo de pacientes."""


# ---------------------------------------------------------------- Dispositivos
@bp.get("/dispositivos")
def listar_dispositivos():
    filas = consultar(
        "SELECT id, nombre, proveedor, vinculado_en, ultima_sincronizacion FROM dispositivos "
        "WHERE paciente_id = %s ORDER BY id",
        (usuario_actual()["id"],),
    )
    return jsonify(dispositivos=filas)


@bp.post("/dispositivos")
def vincular_dispositivo():
    datos = v.cuerpo_json()
    paciente_id = usuario_actual()["id"]
    nombre = v.texto(datos.get("nombre"), "El nombre del dispositivo", 2, 80)
    proveedor = v.opcion(datos.get("proveedor"), "El proveedor", PROVEEDORES)

    cantidad = consultar("SELECT COUNT(*) AS n FROM dispositivos WHERE paciente_id = %s", (paciente_id,), uno=True)["n"]
    if cantidad >= current_app.config["MAX_DISPOSITIVOS"]:
        raise ErrorNegocio(f"Puede vincular hasta {current_app.config['MAX_DISPOSITIVOS']} dispositivos.", 409)

    # Identificador opaco que se envía a la API externa en lugar de datos personales.
    id_externo = "hs-" + secrets.token_hex(8)
    dispositivo_id = ejecutar(
        "INSERT INTO dispositivos (paciente_id, nombre, proveedor, id_externo) VALUES (%s, %s, %s, %s)",
        (paciente_id, nombre, proveedor, id_externo),
    )
    auditoria.registrar("dispositivo_vinculado", paciente_id, f"dispositivo={dispositivo_id}")
    confirmar()
    return jsonify(mensaje="Dispositivo vinculado.", id=dispositivo_id), 201


@bp.delete("/dispositivos/<int:dispositivo_id>")
def desvincular_dispositivo(dispositivo_id: int):
    _dispositivo_propio(dispositivo_id)
    ejecutar("DELETE FROM dispositivos WHERE id = %s AND paciente_id = %s", (dispositivo_id, usuario_actual()["id"]))
    confirmar()
    return jsonify(mensaje="Dispositivo desvinculado. Sus métricas históricas se conservan.")


def _dispositivo_propio(dispositivo_id: int) -> dict:
    """Devuelve el dispositivo solo si pertenece al paciente autenticado; si no, 404."""
    fila = consultar(
        "SELECT id, id_externo FROM dispositivos WHERE id = %s AND paciente_id = %s",
        (dispositivo_id, usuario_actual()["id"]),
        uno=True,
    )
    if not fila:
        raise ErrorNegocio("Dispositivo no encontrado.", 404)
    return fila


# --------------------------------------------------------------- Sincronización
def _normalizar(punto: dict, esquema: str, paciente_id: int, dispositivo_id: int) -> tuple | None:
    """Convierte un dataPoint de Open mHealth en una fila de `metricas`. Devuelve None si no es válido."""
    definicion = TIPOS[esquema]
    try:
        valor = punto["body"][definicion["campo"]]["value"]
        momento = v.fecha_hora_utc(punto["body"]["effective_time_frame"]["date_time"], "La fecha")
        origen_id = str(punto["header"]["id"])[:64]
    except (KeyError, TypeError, ErrorNegocio):
        return None
    if not v.numero_finito(valor) or not definicion["min"] <= valor <= definicion["max"]:
        return None
    return (paciente_id, dispositivo_id, esquema, valor, definicion["unidad"], momento, "wearable", origen_id)


@bp.post("/dispositivos/<int:dispositivo_id>/sincronizar")
def sincronizar(dispositivo_id: int):
    """Importa las métricas de los últimos N días desde la API externa."""
    dispositivo = _dispositivo_propio(dispositivo_id)
    cuerpo = request.get_json(silent=True) or {}
    dias = v.entero(cuerpo.get("dias", 7), "Los días", 1, 30)
    paciente_id = usuario_actual()["id"]

    filas, descartadas = [], 0
    for esquema in TIPOS:
        try:
            puntos = api_externa.obtener_json(
                "dataPoints", {"schema": esquema, "usuario": dispositivo["id_externo"], "dias": dias}
            )
        except api_externa.ErrorApiExterna:
            raise ErrorNegocio("El servicio de wearables no está disponible. Intente más tarde.", 502) from None
        if not isinstance(puntos, list):
            raise ErrorNegocio("El servicio de wearables devolvió datos inesperados.", 502)
        for punto in puntos[:MAX_PUNTOS_POR_ESQUEMA]:
            fila = _normalizar(punto, esquema, paciente_id, dispositivo_id) if isinstance(punto, dict) else None
            if fila:
                filas.append(fila)
            else:
                descartadas += 1

    nuevas = ejecutar_muchos(
        "INSERT INTO metricas (paciente_id, dispositivo_id, tipo, valor, unidad, medido_en, fuente, origen_id) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE id = id",
        filas,
    )
    ejecutar("UPDATE dispositivos SET ultima_sincronizacion = UTC_TIMESTAMP() WHERE id = %s", (dispositivo_id,))
    auditoria.registrar("sincronizacion", paciente_id, f"dispositivo={dispositivo_id} lecturas={len(filas)}")
    confirmar()
    return jsonify(
        mensaje="Sincronización completada.",
        recibidas=len(filas),
        nuevas=nuevas if nuevas >= 0 else 0,
        descartadas=descartadas,
    )


# --------------------------------------------------------------------- Métricas
@bp.get("/metricas")
def listar_metricas():
    """Historial de métricas del paciente, opcionalmente filtrado por tipo y número de días."""
    paciente_id = usuario_actual()["id"]
    dias = v.entero(request.args.get("dias", 7), "Los días", 1, 90)
    desde = ahora_utc() - timedelta(days=dias)
    if request.args.get("tipo"):
        tipo = v.opcion(request.args["tipo"], "El tipo de métrica", TIPOS)
        filas = consultar(
            "SELECT id, tipo, valor, unidad, medido_en, fuente FROM metricas "
            "WHERE paciente_id = %s AND tipo = %s AND medido_en >= %s ORDER BY medido_en DESC, id DESC LIMIT 500",
            (paciente_id, tipo, desde),
        )
    else:
        filas = consultar(
            "SELECT id, tipo, valor, unidad, medido_en, fuente FROM metricas "
            "WHERE paciente_id = %s AND medido_en >= %s ORDER BY medido_en DESC, id DESC LIMIT 500",
            (paciente_id, desde),
        )
    return jsonify(metricas=filas)


@bp.get("/resumen")
def resumen():
    """Última lectura de cada tipo de métrica."""
    paciente_id = usuario_actual()["id"]
    ultimas = {}
    for tipo in TIPOS:
        ultimas[tipo] = consultar(
            "SELECT valor, unidad, medido_en, fuente FROM metricas WHERE paciente_id = %s AND tipo = %s "
            "ORDER BY medido_en DESC, id DESC LIMIT 1",
            (paciente_id, tipo),
            uno=True,
        )
    return jsonify(ultimas=ultimas, etiquetas={t: d["etiqueta"] for t, d in TIPOS.items()})


@bp.post("/metricas")
def registrar_lectura_manual():
    """Registra una lectura escrita por el paciente (sin dispositivo)."""
    datos = v.cuerpo_json()
    paciente_id = usuario_actual()["id"]
    tipo = v.opcion(datos.get("tipo"), "El tipo de métrica", TIPOS)
    definicion = TIPOS[tipo]
    valor = v.decimal(datos.get("valor"), "El valor", definicion["min"], definicion["max"])
    medido_en = ahora_utc()
    if datos.get("medido_en"):
        medido_en = v.fecha_hora_utc(datos["medido_en"], "La fecha de la lectura")
        if medido_en > ahora_utc() + timedelta(minutes=5) or medido_en < ahora_utc() - timedelta(days=30):
            raise ErrorNegocio("La lectura debe ser de los últimos 30 días y no puede estar en el futuro.")
    metrica_id = ejecutar(
        "INSERT INTO metricas (paciente_id, tipo, valor, unidad, medido_en, fuente) VALUES (%s, %s, %s, %s, %s, 'manual')",
        (paciente_id, tipo, valor, definicion["unidad"], medido_en),
    )
    confirmar()
    return jsonify(mensaje="Lectura registrada.", id=metrica_id), 201
