"""Módulo 3 - Consultas médicas virtuales.

Ciclo de vida de una consulta:

    confirmada --iniciar--> en_curso --finalizar--> completada
        |
        +--cancelar--> cancelada (reembolso al paciente)

Dinero: el costo en créditos se descuenta del paciente al CONFIRMAR la cita y queda
retenido. Si la cita se cancela, se devuelve íntegro al paciente. Si se completa,
se acredita al profesional. Así nunca hay que quitarle saldo a un profesional que
ya lo gastó.

Privacidad: el profesional solo ve las métricas del wearable del paciente mientras
la consulta está en curso Y el paciente dio su consentimiento explícito para esa
consulta. Cada acceso queda en el registro de eventos de seguridad.
"""
from datetime import timedelta

from flask import Blueprint, current_app, jsonify, request

from . import auditoria, correo, validaciones as v
from .db import actualizar, confirmar, consultar, ejecutar
from .errores import ErrorNegocio
from .metricas import TIPOS
from .seguridad import rol_requerido, usuario_actual
from .servicios import creditos
from .tiempo import ahora_utc

bp = Blueprint("consultas", __name__, url_prefix="/api/consultas")

ANTICIPACION_MINIMA = timedelta(minutes=5)
ANTICIPACION_MAXIMA = timedelta(days=90)
ESTADOS = ("confirmada", "en_curso", "completada", "cancelada")

# Columnas que se devuelven de una consulta. Las notas clínicas son visibles solo para sus dos participantes.
_SELECCION = (
    "SELECT c.id, c.paciente_id, c.profesional_id, c.inicio, c.motivo, c.estado, c.costo_creditos, "
    "c.consentimiento_metricas, c.consentimiento_en, c.diagnostico_resumido, c.notas_clinicas, "
    "pa.nombre AS paciente, pr.nombre AS profesional "
    "FROM consultas c JOIN cuentas pa ON pa.id = c.paciente_id JOIN cuentas pr ON pr.id = c.profesional_id "
)


# ---------------------------------------------------------------------- Utilidades
def _consulta_de_participante(consulta_id: int, bloquear: bool = False) -> dict:
    """Carga una consulta solo si el usuario autenticado participa en ella; si no, responde 404.

    Se responde 404 (y no 403) para no revelar que existen consultas de otras personas.
    """
    usuario = usuario_actual()
    fila = consultar(
        _SELECCION + "WHERE c.id = %s AND (c.paciente_id = %s OR c.profesional_id = %s)" + (" FOR UPDATE" if bloquear else ""),
        (consulta_id, usuario["id"], usuario["id"]),
        uno=True,
    )
    if not fila:
        raise ErrorNegocio("Consulta no encontrada.", 404)
    return fila


def _exigir_rol_en_consulta(consulta: dict, rol: str) -> None:
    """Comprueba que el usuario actúa con el papel que exige la operación (paciente o profesional)."""
    campo = "paciente_id" if rol == "paciente" else "profesional_id"
    if consulta[campo] != usuario_actual()["id"]:
        raise ErrorNegocio("No tiene permisos para esta acción.", 403)


def _datos_correo(cuenta_id: int) -> dict:
    return consultar("SELECT nombre, email FROM cuentas WHERE id = %s", (cuenta_id,), uno=True)


def _formato_utc(momento) -> str:
    return momento.strftime("%Y-%m-%d %H:%M")


# ------------------------------------------------------------------ Historial y detalle
@bp.get("")
@rol_requerido("paciente", "profesional")
def historial():
    """Historial de citas del usuario: fecha, diagnóstico resumido, notas clínicas y costo."""
    usuario = usuario_actual()
    columna = "c.paciente_id" if usuario["rol"] == "paciente" else "c.profesional_id"
    condiciones, parametros = [f"{columna} = %s"], [usuario["id"]]
    if request.args.get("estado"):
        condiciones.append("c.estado = %s")
        parametros.append(v.opcion(request.args["estado"], "El estado", ESTADOS))
    filas = consultar(
        _SELECCION + "WHERE " + " AND ".join(condiciones) + " ORDER BY c.inicio DESC LIMIT 200",  # condiciones: texto fijo
        tuple(parametros),
    )
    return jsonify(consultas=filas)


@bp.get("/<int:consulta_id>")
@rol_requerido("paciente", "profesional")
def detalle(consulta_id: int):
    return jsonify(consulta=_consulta_de_participante(consulta_id))


# ------------------------------------------------------------------- Agendar y cobrar
@bp.post("")
@rol_requerido("paciente")
def agendar():
    """Agenda y confirma una consulta; descuenta el costo del saldo del paciente."""
    datos = v.cuerpo_json()
    paciente = usuario_actual()
    profesional_id = v.entero(datos.get("profesional_id"), "El profesional", 1, 2**62)
    inicio = v.fecha_hora_utc(datos.get("inicio"), "La fecha de la consulta")
    motivo = v.texto(datos.get("motivo"), "El motivo de la consulta", 5, 300)

    ahora = ahora_utc()
    if inicio.second or inicio.microsecond:
        raise ErrorNegocio("La hora de la consulta debe indicarse en minutos exactos.")
    if inicio < ahora + ANTICIPACION_MINIMA:
        raise ErrorNegocio("La consulta debe agendarse al menos 5 minutos en el futuro.")
    if inicio > ahora + ANTICIPACION_MAXIMA:
        raise ErrorNegocio("Solo se pueden agendar consultas dentro de los próximos 90 días.")

    # Bloqueos, en este orden: fila del profesional (serializa sus reservas) y billetera del paciente.
    profesional = consultar(
        "SELECT c.id, c.nombre, c.email, p.tarifa_creditos FROM cuentas c "
        "JOIN perfiles_profesionales p ON p.cuenta_id = c.id "
        "WHERE c.id = %s AND c.rol = 'profesional' AND c.estado = 'activo' FOR UPDATE",
        (profesional_id,),
        uno=True,
    )
    if not profesional:
        raise ErrorNegocio("El profesional no existe o no está disponible.", 404)
    saldos = creditos.bloquear(paciente["id"])

    duracion = timedelta(minutes=current_app.config["DURACION_CONSULTA_MIN"])
    for columna, persona in (("profesional_id", profesional_id), ("paciente_id", paciente["id"])):
        choque = consultar(
            f"SELECT id FROM consultas WHERE {columna} = %s AND estado IN ('confirmada', 'en_curso') "  # `columna` es fijo
            "AND inicio > %s AND inicio < %s LIMIT 1",
            (persona, inicio - duracion, inicio + duracion),
            uno=True,
        )
        if choque:
            quien = "El profesional" if columna == "profesional_id" else "Usted"
            raise ErrorNegocio(f"{quien} ya tiene una consulta que se cruza con ese horario.", 409)

    costo = profesional["tarifa_creditos"]
    consulta_id = ejecutar(
        "INSERT INTO consultas (paciente_id, profesional_id, inicio, motivo, costo_creditos) VALUES (%s, %s, %s, %s, %s)",
        (paciente["id"], profesional_id, inicio, motivo, costo),
    )
    restante = creditos.aplicar(
        paciente["id"], -costo, "pago_consulta", saldos, profesional_id, referencia=f"consulta:{consulta_id}"
    )
    auditoria.registrar("consulta_agendada", paciente["id"], f"consulta={consulta_id}")
    confirmar()

    correo.notificar_consulta_confirmada(
        paciente["email"], paciente["nombre"], profesional["nombre"], _formato_utc(inicio), costo, es_paciente=True
    )
    correo.notificar_consulta_confirmada(
        profesional["email"], profesional["nombre"], paciente["nombre"], _formato_utc(inicio), costo, es_paciente=False
    )
    return jsonify(mensaje="Consulta confirmada.", id=consulta_id, costo=costo, saldo=restante), 201


@bp.post("/<int:consulta_id>/cancelar")
@rol_requerido("paciente", "profesional")
def cancelar(consulta_id: int):
    """Cancela una consulta confirmada y devuelve los créditos al paciente."""
    consulta = _consulta_de_participante(consulta_id, bloquear=True)
    if consulta["estado"] != "confirmada":
        raise ErrorNegocio("Solo se pueden cancelar las consultas confirmadas que aún no iniciaron.", 409)
    ejecutar("UPDATE consultas SET estado = 'cancelada' WHERE id = %s", (consulta_id,))
    saldos = creditos.bloquear(consulta["paciente_id"])
    creditos.aplicar(
        consulta["paciente_id"], consulta["costo_creditos"], "reembolso_consulta", saldos,
        consulta["profesional_id"], referencia=f"consulta:{consulta_id}",
    )
    auditoria.registrar("consulta_cancelada", usuario_actual()["id"], f"consulta={consulta_id}")
    confirmar()
    for cuenta_id in (consulta["paciente_id"], consulta["profesional_id"]):
        destino = _datos_correo(cuenta_id)
        correo.notificar_consulta_cancelada(
            destino["email"], destino["nombre"], _formato_utc(consulta["inicio"]),
            consulta["costo_creditos"] if cuenta_id == consulta["paciente_id"] else None,
        )
    return jsonify(mensaje="Consulta cancelada. Los créditos fueron devueltos al paciente.")


# -------------------------------------------------------- Realización de la consulta
@bp.post("/<int:consulta_id>/iniciar")
@rol_requerido("profesional")
def iniciar(consulta_id: int):
    consulta = _consulta_de_participante(consulta_id, bloquear=True)
    _exigir_rol_en_consulta(consulta, "profesional")
    if consulta["estado"] != "confirmada":
        raise ErrorNegocio("Solo se puede iniciar una consulta confirmada.", 409)
    ejecutar("UPDATE consultas SET estado = 'en_curso' WHERE id = %s", (consulta_id,))
    confirmar()
    return jsonify(mensaje="Consulta en curso.")


@bp.put("/<int:consulta_id>/consentimiento")
@rol_requerido("paciente")
def consentimiento(consulta_id: int):
    """El paciente autoriza (o retira la autorización) para que el profesional vea sus métricas en esta consulta."""
    otorgado = v.booleano(v.cuerpo_json().get("otorgado"), "El consentimiento")
    consulta = _consulta_de_participante(consulta_id, bloquear=True)
    _exigir_rol_en_consulta(consulta, "paciente")
    if consulta["estado"] not in ("confirmada", "en_curso"):
        raise ErrorNegocio("El consentimiento solo se puede cambiar mientras la consulta está vigente.", 409)
    ejecutar(
        "UPDATE consultas SET consentimiento_metricas = %s, consentimiento_en = UTC_TIMESTAMP() WHERE id = %s",
        (1 if otorgado else 0, consulta_id),
    )
    auditoria.registrar(
        "consentimiento_otorgado" if otorgado else "consentimiento_retirado", usuario_actual()["id"], f"consulta={consulta_id}"
    )
    confirmar()
    return jsonify(mensaje="Consentimiento registrado." if otorgado else "Consentimiento retirado.")


@bp.get("/<int:consulta_id>/metricas")
@rol_requerido("profesional")
def metricas_del_paciente(consulta_id: int):
    """Historial de métricas del paciente, visible para el profesional con consentimiento y consulta en curso."""
    consulta = _consulta_de_participante(consulta_id)
    _exigir_rol_en_consulta(consulta, "profesional")
    if consulta["estado"] != "en_curso":
        raise ErrorNegocio("Las métricas solo están disponibles mientras la consulta está en curso.", 409)
    if not consulta["consentimiento_metricas"]:
        raise ErrorNegocio("El paciente no ha dado su consentimiento para compartir sus métricas.", 403)
    dias = v.entero(request.args.get("dias", 7), "Los días", 1, 30)
    filas = consultar(
        "SELECT tipo, valor, unidad, medido_en FROM metricas WHERE paciente_id = %s AND medido_en >= %s "
        "ORDER BY medido_en DESC, id DESC LIMIT 500",
        (consulta["paciente_id"], ahora_utc() - timedelta(days=dias)),
    )
    auditoria.registrar("acceso_metricas_paciente", usuario_actual()["id"], f"consulta={consulta_id} paciente={consulta['paciente_id']}")
    confirmar()
    return jsonify(metricas=filas, etiquetas={t: d["etiqueta"] for t, d in TIPOS.items()})


@bp.put("/<int:consulta_id>/notas")
@rol_requerido("profesional")
def registrar_notas(consulta_id: int):
    """El profesional registra el diagnóstico resumido y las notas clínicas."""
    datos = v.cuerpo_json()
    consulta = _consulta_de_participante(consulta_id, bloquear=True)
    _exigir_rol_en_consulta(consulta, "profesional")
    if consulta["estado"] not in ("en_curso", "completada"):
        raise ErrorNegocio("Solo se pueden registrar notas en una consulta en curso o completada.", 409)
    diagnostico = consulta["diagnostico_resumido"]
    notas = consulta["notas_clinicas"]
    if "diagnostico_resumido" in datos:
        diagnostico = v.texto(datos["diagnostico_resumido"], "El diagnóstico resumido", 3, 255)
    if "notas_clinicas" in datos:
        notas = v.texto(datos["notas_clinicas"], "Las notas clínicas", 0, 5000, opcional=True, multilinea=True)
    ejecutar(
        "UPDATE consultas SET diagnostico_resumido = %s, notas_clinicas = %s WHERE id = %s",
        (diagnostico, notas, consulta_id),
    )
    auditoria.registrar("notas_clinicas", usuario_actual()["id"], f"consulta={consulta_id}")
    confirmar()
    return jsonify(mensaje="Notas guardadas.")


@bp.post("/<int:consulta_id>/finalizar")
@rol_requerido("profesional")
def finalizar(consulta_id: int):
    """Cierra la consulta y acredita el costo retenido al profesional. Exige diagnóstico resumido."""
    consulta = _consulta_de_participante(consulta_id, bloquear=True)
    _exigir_rol_en_consulta(consulta, "profesional")
    if consulta["estado"] != "en_curso":
        raise ErrorNegocio("Solo se puede finalizar una consulta en curso.", 409)
    if not consulta["diagnostico_resumido"]:
        raise ErrorNegocio("Registre el diagnóstico resumido antes de finalizar la consulta.")
    actualizar("UPDATE consultas SET estado = 'completada' WHERE id = %s", (consulta_id,))
    saldos = creditos.bloquear(consulta["profesional_id"])
    creditos.aplicar(
        consulta["profesional_id"], consulta["costo_creditos"], "cobro_consulta", saldos,
        consulta["paciente_id"], referencia=f"consulta:{consulta_id}",
    )
    auditoria.registrar("consulta_completada", usuario_actual()["id"], f"consulta={consulta_id}")
    confirmar()
    return jsonify(mensaje="Consulta completada. Los créditos fueron acreditados a su saldo.")
