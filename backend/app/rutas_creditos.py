"""Saldo, historial de movimientos y transferencias de crédito entre usuarios."""
from flask import Blueprint, current_app, jsonify

from . import auditoria, correo, validaciones as v
from .db import confirmar, consultar
from .errores import ErrorNegocio
from .seguridad import rol_requerido, usuario_actual
from .servicios import creditos

bp = Blueprint("creditos", __name__, url_prefix="/api/creditos")


@bp.get("")
@rol_requerido("paciente", "profesional")
def mi_saldo():
    cuenta_id = usuario_actual()["id"]
    movimientos = consultar(
        "SELECT m.id, m.tipo, m.monto, m.saldo_posterior, m.nota, m.creado_en, c.nombre AS contraparte "
        "FROM movimientos_credito m LEFT JOIN cuentas c ON c.id = m.contraparte_id "
        "WHERE m.cuenta_id = %s ORDER BY m.id DESC LIMIT 100",
        (cuenta_id,),
    )
    return jsonify(
        saldo=creditos.saldo(cuenta_id),
        maximo_transferencia=current_app.config["MAX_TRANSFERENCIA"],
        movimientos=movimientos,
    )


@bp.post("/transferir")
@rol_requerido("paciente", "profesional")
def transferir():
    """Transfiere créditos a otro usuario activo, identificado por su correo."""
    datos = v.cuerpo_json()
    email = v.correo(datos.get("email"))
    monto = v.entero(datos.get("monto"), "El monto", 1, current_app.config["MAX_TRANSFERENCIA"])
    nota = v.texto(datos.get("nota"), "La nota", 0, 140, opcional=True) or None
    origen = usuario_actual()

    destino = consultar(
        "SELECT c.id, c.nombre, c.email FROM cuentas c JOIN billeteras b ON b.cuenta_id = c.id "
        "WHERE c.email = %s AND c.estado = 'activo'",
        (email,),
        uno=True,
    )
    if not destino:
        raise ErrorNegocio("No existe un usuario activo con ese correo.", 404)

    restante = creditos.transferir(origen["id"], destino["id"], monto, nota)
    auditoria.registrar("transferencia", origen["id"], f"destino={destino['id']} monto={monto}")
    confirmar()
    correo.notificar_transferencia(destino["email"], destino["nombre"], origen["nombre"], monto)
    return jsonify(mensaje=f"Transferencia de {monto} créditos realizada.", saldo=restante)
