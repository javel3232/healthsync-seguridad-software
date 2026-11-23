"""Módulo 4 - Alertas de salud programadas.

El paciente define umbrales sobre sus métricas (por ejemplo, frecuencia cardíaca
mayor a 120). Un robot en C++ evalúa cada segundo la lectura más reciente de cada
paciente (ver rutas_internas.py). Al dispararse una alerta se avisa al paciente
por correo y, solo si el paciente lo autorizó, también al profesional que eligió.
"""
from flask import Blueprint, current_app, jsonify

from . import auditoria, validaciones as v
from .db import confirmar, consultar, ejecutar
from .errores import ErrorNegocio
from .metricas import OPERADORES, TIPOS
from .seguridad import rol_requerido, usuario_actual

bp = Blueprint("alertas", __name__, url_prefix="/api/alertas")

_SELECCION = (
    "SELECT a.id, a.tipo_metrica, a.operador, a.umbral, a.activa, a.notificar_profesional, a.profesional_id, "
    "a.creado_en, pr.nombre AS profesional FROM alertas a LEFT JOIN cuentas pr ON pr.id = a.profesional_id "
)


def _profesional_valido(profesional_id) -> int:
    """El profesional elegido debe existir y estar activo."""
    profesional_id = v.entero(profesional_id, "El profesional", 1, 2**62)
    fila = consultar(
        "SELECT id FROM cuentas WHERE id = %s AND rol = 'profesional' AND estado = 'activo'", (profesional_id,), uno=True
    )
    if not fila:
        raise ErrorNegocio("El profesional elegido no existe o no está activo.", 404)
    return profesional_id


def _alerta_propia(alerta_id: int) -> dict:
    fila = consultar(_SELECCION + "WHERE a.id = %s AND a.paciente_id = %s", (alerta_id, usuario_actual()["id"]), uno=True)
    if not fila:
        raise ErrorNegocio("Alerta no encontrada.", 404)
    return fila


# ------------------------------------------------------------------ Paciente
@bp.get("")
@rol_requerido("paciente")
def listar():
    filas = consultar(_SELECCION + "WHERE a.paciente_id = %s ORDER BY a.id DESC", (usuario_actual()["id"],))
    return jsonify(alertas=filas, etiquetas={t: d["etiqueta"] for t, d in TIPOS.items()})


@bp.post("")
@rol_requerido("paciente")
def crear():
    datos = v.cuerpo_json()
    paciente_id = usuario_actual()["id"]
    tipo = v.opcion(datos.get("tipo_metrica"), "La métrica", TIPOS)
    operador = v.opcion(datos.get("operador"), "El operador", OPERADORES)
    umbral = v.decimal(datos.get("umbral"), "El umbral", TIPOS[tipo]["min"], TIPOS[tipo]["max"])
    notificar = v.booleano(datos.get("notificar_profesional", False), "La autorización al profesional")
    profesional_id = _profesional_valido(datos.get("profesional_id")) if notificar else None

    cantidad = consultar("SELECT COUNT(*) AS n FROM alertas WHERE paciente_id = %s", (paciente_id,), uno=True)["n"]
    if cantidad >= current_app.config["MAX_ALERTAS"]:
        raise ErrorNegocio(f"Puede tener hasta {current_app.config['MAX_ALERTAS']} alertas.", 409)

    alerta_id = ejecutar(
        "INSERT INTO alertas (paciente_id, tipo_metrica, operador, umbral, notificar_profesional, profesional_id) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (paciente_id, tipo, operador, umbral, 1 if notificar else 0, profesional_id),
    )
    auditoria.registrar("alerta_creada", paciente_id, f"alerta={alerta_id} autoriza_profesional={notificar}")
    confirmar()
    return jsonify(mensaje="Alerta creada.", id=alerta_id), 201


@bp.put("/<int:alerta_id>")
@rol_requerido("paciente")
def modificar(alerta_id: int):
    """Cambia solo los campos enviados: activar/pausar, umbral, operador o autorización al profesional."""
    datos = v.cuerpo_json()
    actual = _alerta_propia(alerta_id)
    activa = v.booleano(datos["activa"], "El estado") if "activa" in datos else bool(actual["activa"])
    operador = v.opcion(datos["operador"], "El operador", OPERADORES) if "operador" in datos else actual["operador"]
    umbral = (
        v.decimal(datos["umbral"], "El umbral", TIPOS[actual["tipo_metrica"]]["min"], TIPOS[actual["tipo_metrica"]]["max"])
        if "umbral" in datos
        else actual["umbral"]
    )
    notificar = (
        v.booleano(datos["notificar_profesional"], "La autorización al profesional")
        if "notificar_profesional" in datos
        else bool(actual["notificar_profesional"])
    )
    profesional_id = actual["profesional_id"]
    if "profesional_id" in datos:
        profesional_id = _profesional_valido(datos["profesional_id"])
    if notificar and profesional_id is None:
        raise ErrorNegocio("Para autorizar el aviso debe elegir un profesional.")
    if not notificar:
        profesional_id = None  # sin autorización no se conserva ningún vínculo
    ejecutar(
        "UPDATE alertas SET activa = %s, operador = %s, umbral = %s, notificar_profesional = %s, profesional_id = %s "
        "WHERE id = %s AND paciente_id = %s",
        (1 if activa else 0, operador, umbral, 1 if notificar else 0, profesional_id, alerta_id, usuario_actual()["id"]),
    )
    confirmar()
    return jsonify(mensaje="Alerta actualizada.")


@bp.delete("/<int:alerta_id>")
@rol_requerido("paciente")
def eliminar(alerta_id: int):
    _alerta_propia(alerta_id)
    ejecutar("DELETE FROM alertas WHERE id = %s AND paciente_id = %s", (alerta_id, usuario_actual()["id"]))
    confirmar()
    return jsonify(mensaje="Alerta eliminada.")


@bp.get("/disparos")
@rol_requerido("paciente")
def historial_paciente():
    """Alertas que se activaron para el paciente."""
    filas = consultar(
        "SELECT d.id, d.tipo_metrica, d.operador, d.umbral, d.valor, d.medido_en, d.disparada_en, "
        "d.correo_paciente, d.correo_profesional, pr.nombre AS profesional "
        "FROM alertas_disparos d LEFT JOIN cuentas pr ON pr.id = d.profesional_id "
        "WHERE d.paciente_id = %s ORDER BY d.id DESC LIMIT 100",
        (usuario_actual()["id"],),
    )
    return jsonify(disparos=filas)


# --------------------------------------------------------------- Profesional
@bp.get("/recibidas")
@rol_requerido("profesional")
def recibidas_profesional():
    """Alertas de pacientes que autorizaron expresamente avisar a este profesional."""
    filas = consultar(
        "SELECT d.id, d.tipo_metrica, d.operador, d.umbral, d.valor, d.medido_en, d.disparada_en, pa.nombre AS paciente "
        "FROM alertas_disparos d JOIN cuentas pa ON pa.id = d.paciente_id "
        "WHERE d.profesional_id = %s ORDER BY d.id DESC LIMIT 100",
        (usuario_actual()["id"],),
    )
    auditoria.registrar("consulta_alertas_recibidas", usuario_actual()["id"])
    confirmar()
    return jsonify(disparos=filas)
