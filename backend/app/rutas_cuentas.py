"""Perfil propio y directorio de profesionales de salud.

El perfil solo se consulta y se edita para la cuenta autenticada: no existe una
ruta que reciba un id de cuenta ajena. Solo se aceptan los campos listados
explícitamente (nunca rol, estado, saldo ni puntos).
"""
from flask import Blueprint, jsonify, request

from . import validaciones as v
from .db import confirmar, consultar, ejecutar
from .seguridad import login_requerido, usuario_actual

bp = Blueprint("cuentas", __name__, url_prefix="/api")

MAX_RESULTADOS_DIRECTORIO = 50


def _escapar_like(termino: str) -> str:
    """Escapa % y _ para que el término de búsqueda se trate como texto literal."""
    return termino.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _perfil_completo(cuenta_id: int) -> dict:
    cuenta = consultar(
        "SELECT c.id, c.nombre, c.email, c.rol, c.estado, c.fecha_nacimiento, c.codigo_referido, "
        "b.saldo_creditos, b.puntos, b.premium_hasta "
        "FROM cuentas c LEFT JOIN billeteras b ON b.cuenta_id = c.id WHERE c.id = %s",
        (cuenta_id,),
        uno=True,
    )
    if cuenta["rol"] == "profesional":
        cuenta["profesional"] = consultar(
            "SELECT especialidad, descripcion, tarifa_creditos FROM perfiles_profesionales WHERE cuenta_id = %s",
            (cuenta_id,),
            uno=True,
        )
    return cuenta


@bp.get("/perfil")
@login_requerido
def ver_perfil():
    return jsonify(cuenta=_perfil_completo(usuario_actual()["id"]))


@bp.put("/perfil")
@login_requerido
def actualizar_perfil():
    usuario = usuario_actual()
    datos = v.cuerpo_json()
    if "nombre" in datos:
        ejecutar("UPDATE cuentas SET nombre = %s WHERE id = %s", (v.texto(datos["nombre"], "El nombre", 2, 100), usuario["id"]))
    if usuario["rol"] == "profesional":
        if "especialidad" in datos:
            ejecutar(
                "UPDATE perfiles_profesionales SET especialidad = %s WHERE cuenta_id = %s",
                (v.texto(datos["especialidad"], "La especialidad", 3, 80), usuario["id"]),
            )
        if "descripcion" in datos:
            ejecutar(
                "UPDATE perfiles_profesionales SET descripcion = %s WHERE cuenta_id = %s",
                (v.texto(datos["descripcion"], "La descripción", 0, 500, opcional=True, multilinea=True), usuario["id"]),
            )
        if "tarifa_creditos" in datos:
            ejecutar(
                "UPDATE perfiles_profesionales SET tarifa_creditos = %s WHERE cuenta_id = %s",
                (v.entero(datos["tarifa_creditos"], "La tarifa", 1, 1000), usuario["id"]),
            )
    confirmar()
    return jsonify(cuenta=_perfil_completo(usuario["id"]))


@bp.get("/directorio")
@login_requerido
def directorio():
    """Profesionales de salud activos. Permite buscar por nombre o especialidad."""
    termino = v.texto(request.args.get("q"), "La búsqueda", 1, 60, opcional=True)
    patron = f"%{_escapar_like(termino)}%"
    profesionales = consultar(
        "SELECT c.id, c.nombre, p.especialidad, p.descripcion, p.tarifa_creditos "
        "FROM cuentas c JOIN perfiles_profesionales p ON p.cuenta_id = c.id "
        "WHERE c.rol = 'profesional' AND c.estado = 'activo' AND (c.nombre LIKE %s OR p.especialidad LIKE %s) "
        "ORDER BY c.nombre LIMIT %s",
        (patron, patron, MAX_RESULTADOS_DIRECTORIO),
    )
    return jsonify(resultados=profesionales)
