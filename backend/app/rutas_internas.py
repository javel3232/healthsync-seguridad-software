"""Endpoints internos para los robots C++ (servicios "worker" y "worker-alertas").

Solo los usan los robots dentro de la red de Docker: nginx no expone /api/internal.
Cada petición debe traer el encabezado X-Internal-Token con el valor de WORKER_TOKEN.

Protocolo: respuestas en texto plano, una fila por línea y campos separados por tabulador,
solo con números e identificadores (nunca texto libre escrito por usuarios). Esto evita
que un nombre malicioso pueda inyectar nada en el robot.

Los robots PROPONEN y el backend DECIDE: antes de ejecutar cualquier acción, el backend
vuelve a comprobar las condiciones (documentación completa, umbral realmente superado).
"""
from decimal import Decimal

from flask import Blueprint, Response, abort, request

from . import auditoria, correo
from .db import actualizar, confirmar, consultar, ejecutar
from .seguridad import token_interno_valido
from .servicios import cuentas

bp = Blueprint("interno", __name__, url_prefix="/api/internal")


@bp.before_request
def verificar_token():
    if not token_interno_valido():
        abort(401)


def _texto(lineas: list[str]) -> Response:
    return Response("".join(f"{linea}\n" for linea in lineas), mimetype="text/plain")


# ------------------------------------------------- Robot de validación de profesionales
@bp.get("/validacion/pendientes")
def validacion_pendientes():
    """Solicitudes de profesionales pendientes. Línea: id <TAB> documentacion_completa (1|0)."""
    pendientes = consultar(
        "SELECT id FROM cuentas WHERE rol = 'profesional' AND estado = 'pendiente' ORDER BY id LIMIT 100"
    )
    return _texto([f"{p['id']}\t{1 if cuentas.profesional_completo(p['id']) else 0}" for p in pendientes])


@bp.post("/validacion/<int:cuenta_id>/validar")
def validacion_validar(cuenta_id: int):
    """El robot actúa como administrador: activa la cuenta si su documentación está completa."""
    if not cuentas.profesional_completo(cuenta_id):
        return Response("documentacion_incompleta\n", status=409, mimetype="text/plain")
    resultado = cuentas.activar(cuenta_id, por_bot=True)
    if resultado is None:
        return Response("ya_resuelta\n", status=409, mimetype="text/plain")
    confirmar()
    cuentas.notificar_activacion(resultado)
    return Response("ok\n", mimetype="text/plain")


# ----------------------------------------------------------- Robot de monitoreo de alertas
@bp.get("/alertas/evaluar")
def alertas_evaluar():
    """Alertas activas con su lectura más reciente aún no evaluada.

    Línea: alerta_id <TAB> metrica_id <TAB> operador <TAB> umbral <TAB> valor
    """
    filas = consultar(
        "SELECT a.id AS alerta_id, m.id AS metrica_id, a.operador, a.umbral, m.valor "
        "FROM alertas a "
        "JOIN cuentas c ON c.id = a.paciente_id AND c.estado = 'activo' AND c.rol = 'paciente' "
        "JOIN metricas m ON m.id = ("
        "    SELECT m2.id FROM metricas m2 WHERE m2.paciente_id = a.paciente_id AND m2.tipo = a.tipo_metrica "
        "    ORDER BY m2.medido_en DESC, m2.id DESC LIMIT 1) "
        "WHERE a.activa = 1 "
        "AND NOT EXISTS (SELECT 1 FROM alertas_disparos d WHERE d.alerta_id = a.id AND d.metrica_id = m.id) "
        "ORDER BY a.id LIMIT 1000"
    )
    return _texto(
        [f"{f['alerta_id']}\t{f['metrica_id']}\t{f['operador']}\t{f['umbral']:f}\t{f['valor']:f}" for f in filas]
    )


def _supera(operador: str, valor: Decimal, umbral: Decimal) -> bool:
    return valor > umbral if operador == "mayor" else valor < umbral


@bp.post("/alertas/<int:alerta_id>/disparar")
def alertas_disparar(alerta_id: int):
    """Registra el disparo de una alerta y envía los correos. El backend revalida todo."""
    try:
        metrica_id = int(request.form.get("metrica_id", ""))
    except ValueError:
        abort(400)

    alerta = consultar(
        "SELECT a.*, p.nombre AS paciente_nombre, p.email AS paciente_email FROM alertas a "
        "JOIN cuentas p ON p.id = a.paciente_id AND p.estado = 'activo' WHERE a.id = %s AND a.activa = 1",
        (alerta_id,),
        uno=True,
    )
    metrica = consultar(
        "SELECT id, valor, medido_en FROM metricas WHERE id = %s AND tipo = %s AND paciente_id = %s",
        (metrica_id, alerta["tipo_metrica"], alerta["paciente_id"]),
        uno=True,
    ) if alerta else None
    if not alerta or not metrica:
        return Response("no_encontrada\n", status=404, mimetype="text/plain")
    if not _supera(alerta["operador"], metrica["valor"], alerta["umbral"]):
        return Response("no_supera_umbral\n", status=409, mimetype="text/plain")

    profesional = None
    if alerta["notificar_profesional"] and alerta["profesional_id"]:
        profesional = consultar(
            "SELECT id, nombre, email FROM cuentas WHERE id = %s AND rol = 'profesional' AND estado = 'activo'",
            (alerta["profesional_id"],),
            uno=True,
        )

    # INSERT IGNORE + clave única (alerta, lectura): una lectura nunca avisa dos veces.
    if (
        actualizar(
            "INSERT IGNORE INTO alertas_disparos (alerta_id, metrica_id, paciente_id, profesional_id, tipo_metrica, "
            "operador, umbral, valor, medido_en) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                alerta_id, metrica_id, alerta["paciente_id"], profesional["id"] if profesional else None,
                alerta["tipo_metrica"], alerta["operador"], alerta["umbral"], metrica["valor"], metrica["medido_en"],
            ),
        )
        == 0
    ):
        return Response("ya_notificada\n", mimetype="text/plain")
    disparo_id = consultar("SELECT id FROM alertas_disparos WHERE alerta_id = %s AND metrica_id = %s", (alerta_id, metrica_id), uno=True)["id"]
    auditoria.registrar("alerta_disparada", alerta["paciente_id"], f"alerta={alerta_id} metrica={metrica_id}")
    confirmar()

    # Los correos se envían tras confirmar; si fallan, queda constancia en el disparo.
    enviado_paciente = correo.notificar_alerta_paciente(
        alerta["paciente_email"], alerta["paciente_nombre"], alerta["tipo_metrica"], alerta["operador"],
        alerta["umbral"], metrica["valor"],
    )
    enviado_profesional = bool(profesional) and correo.notificar_alerta_profesional(
        profesional["email"], profesional["nombre"], alerta["paciente_nombre"], alerta["tipo_metrica"],
        alerta["operador"], alerta["umbral"], metrica["valor"],
    )
    ejecutar(
        "UPDATE alertas_disparos SET correo_paciente = %s, correo_profesional = %s WHERE id = %s",
        (1 if enviado_paciente else 0, 1 if enviado_profesional else 0, disparo_id),
    )
    confirmar()
    return Response("ok\n", mimetype="text/plain")
