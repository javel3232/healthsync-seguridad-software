"""Registro de eventos de seguridad (inicios de sesión, aprobaciones, accesos a datos clínicos...).

Cada evento se guarda en la tabla `eventos_seguridad` y se escribe en el log.
Nunca se registran contraseñas, tokens ni datos clínicos: solo qué pasó, quién y desde dónde.
No hace commit: lo confirma quien llama junto con el resto de su transacción.
"""
import logging

from flask import has_request_context, request

from .db import ejecutar

log = logging.getLogger("auditoria")


def registrar(evento: str, cuenta_id: int | None = None, detalle: str = "") -> None:
    ip = request.remote_addr if has_request_context() else None
    log.info("evento=%s cuenta=%s ip=%s detalle=%s", evento, cuenta_id, ip, detalle)
    ejecutar(
        "INSERT INTO eventos_seguridad (cuenta_id, evento, detalle, ip) VALUES (%s, %s, %s, %s)",
        (cuenta_id, evento[:40], detalle[:255], ip),
    )
