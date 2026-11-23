"""Programa de referidos: código propio, puntos ganados y canje por meses de premium."""
from flask import Blueprint, current_app, jsonify

from . import validaciones as v
from .db import confirmar, consultar
from .seguridad import rol_requerido, usuario_actual
from .servicios import referidos

bp = Blueprint("referidos", __name__, url_prefix="/api/referidos")


@bp.get("")
@rol_requerido("paciente", "profesional")
def resumen():
    cuenta_id = usuario_actual()["id"]
    cuenta = consultar(
        "SELECT c.codigo_referido, b.puntos, b.premium_hasta FROM cuentas c "
        "JOIN billeteras b ON b.cuenta_id = c.id WHERE c.id = %s",
        (cuenta_id,),
        uno=True,
    )
    lista = consultar(
        "SELECT r.id, c.nombre, r.estado, r.puntos, r.creado_en, r.completado_en FROM referidos r "
        "JOIN cuentas c ON c.id = r.referido_id WHERE r.referidor_id = %s ORDER BY r.id DESC LIMIT 100",
        (cuenta_id,),
    )
    movimientos = consultar(
        "SELECT tipo, puntos, referencia, creado_en FROM movimientos_puntos WHERE cuenta_id = %s ORDER BY id DESC LIMIT 50",
        (cuenta_id,),
    )
    return jsonify(
        codigo=cuenta["codigo_referido"],
        puntos=cuenta["puntos"],
        premium_hasta=cuenta["premium_hasta"],
        puntos_por_referido=current_app.config["PUNTOS_POR_REFERIDO"],
        puntos_por_mes=current_app.config["PUNTOS_POR_MES_PREMIUM"],
        referidos=lista,
        movimientos=movimientos,
    )


@bp.post("/canjear")
@rol_requerido("paciente", "profesional")
def canjear():
    meses = v.entero(v.cuerpo_json().get("meses"), "Los meses", 1, 12)
    estado = referidos.canjear(usuario_actual()["id"], meses)
    confirmar()
    return jsonify(mensaje=f"Canje realizado: {meses} mes(es) de premium.", **estado)
