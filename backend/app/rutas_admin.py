"""Panel de administración: validación de profesionales de salud.

Todas las rutas exigen rol administrador (verificado contra la base de datos).
La aprobación solo procede si la documentación está completa; el rechazo exige un motivo.
"""
from flask import Blueprint, jsonify, request

from . import archivos, correo, validaciones as v
from .db import confirmar, consultar
from .errores import ErrorNegocio
from .seguridad import rol_requerido, usuario_actual
from .servicios import cuentas

bp = Blueprint("admin", __name__, url_prefix="/api/admin")

ESTADOS_FILTRO = ("pendiente", "activo", "rechazado", "todos")


@bp.before_request
@rol_requerido("admin")
def solo_administradores():
    """Protege todo el blueprint con una sola comprobación."""


def _solicitud(cuenta_id: int) -> dict:
    fila = consultar(
        "SELECT c.id, c.nombre, c.email, c.fecha_nacimiento, c.estado, c.creado_en, "
        "p.especialidad, p.tarjeta_archivo, p.revisado_por_bot, p.revisado_en, p.motivo_rechazo "
        "FROM cuentas c JOIN perfiles_profesionales p ON p.cuenta_id = c.id "
        "WHERE c.id = %s AND c.rol = 'profesional'",
        (cuenta_id,),
        uno=True,
    )
    if not fila:
        raise ErrorNegocio("Solicitud no encontrada.", 404)
    return fila


@bp.get("/solicitudes")
def listar_solicitudes():
    estado = v.opcion(request.args.get("estado", "pendiente"), "El estado", ESTADOS_FILTRO)
    filtro, parametros = ("", ()) if estado == "todos" else ("AND c.estado = %s", (estado,))
    filas = consultar(
        "SELECT c.id, c.nombre, c.email, c.fecha_nacimiento, c.estado, c.creado_en, "
        "p.especialidad, p.revisado_por_bot, p.revisado_en, p.motivo_rechazo "
        "FROM cuentas c JOIN perfiles_profesionales p ON p.cuenta_id = c.id "
        f"WHERE c.rol = 'profesional' {filtro} ORDER BY c.id DESC LIMIT 200",  # `filtro` es texto fijo, sin datos del usuario
        parametros,
    )
    for fila in filas:
        fila["documentacion_completa"] = cuentas.profesional_completo(fila["id"])
    return jsonify(solicitudes=filas)


@bp.get("/solicitudes/<int:cuenta_id>/tarjeta")
def ver_tarjeta(cuenta_id: int):
    """Entrega la foto de la tarjeta profesional (solo administradores)."""
    fila = consultar("SELECT tarjeta_archivo, tarjeta_mime FROM perfiles_profesionales WHERE cuenta_id = %s", (cuenta_id,), uno=True)
    if not fila or not fila["tarjeta_archivo"]:
        raise ErrorNegocio("La solicitud no tiene tarjeta adjunta.", 404)
    return archivos.enviar_imagen(fila["tarjeta_archivo"], fila["tarjeta_mime"])


@bp.post("/solicitudes/<int:cuenta_id>/aprobar")
def aprobar(cuenta_id: int):
    solicitud = _solicitud(cuenta_id)
    if solicitud["estado"] != "pendiente":
        raise ErrorNegocio("La solicitud ya fue resuelta.", 409)
    if not cuentas.profesional_completo(cuenta_id):
        raise ErrorNegocio("No se puede aprobar: la documentación está incompleta.", 409)
    resultado = cuentas.activar(cuenta_id, administrador_id=usuario_actual()["id"])
    if resultado is None:
        raise ErrorNegocio("La solicitud ya fue resuelta.", 409)
    confirmar()
    cuentas.notificar_activacion(resultado)
    return jsonify(mensaje="Profesional aprobado. Se le envió un correo y ya aparece en el directorio.")


@bp.post("/solicitudes/<int:cuenta_id>/rechazar")
def rechazar(cuenta_id: int):
    motivo = v.texto(v.cuerpo_json().get("motivo"), "El motivo", 5, 300)
    _solicitud(cuenta_id)
    destinatario = cuentas.rechazar(cuenta_id, usuario_actual()["id"], motivo)
    if destinatario is None:
        raise ErrorNegocio("La solicitud ya fue resuelta.", 409)
    confirmar()
    correo.notificar_rechazo(destinatario["email"], destinatario["nombre"], motivo)
    return jsonify(mensaje="Solicitud rechazada. Se notificó al solicitante.")


@bp.get("/cuentas")
def listar_cuentas():
    """Resumen de todas las cuentas (sin datos sensibles)."""
    return jsonify(
        cuentas=consultar(
            "SELECT id, nombre, email, rol, estado, creado_en FROM cuentas ORDER BY id DESC LIMIT 200"
        )
    )
