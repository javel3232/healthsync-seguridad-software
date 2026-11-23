"""Creación, activación y rechazo de cuentas.

El ciclo de vida de una cuenta es:
    pendiente --(validación del administrador o del robot)--> activo
    pendiente --(rechazo del administrador)-------------------> rechazado

Al activarse una cuenta ocurre, en una sola transacción:
  * se genera su código de referidos (pacientes y profesionales),
  * se crea su billetera (los pacientes reciben el bono de bienvenida),
  * si se registró con un código, se completa el referido y el referidor gana puntos.
"""
import secrets

from flask import current_app

from .. import archivos, auditoria, correo
from ..db import actualizar, consultar, ejecutar
from . import creditos

# Sin caracteres ambiguos (0/O, 1/I/L) para que el código sea fácil de dictar.
ALFABETO_CODIGO = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
ROLES_CON_BILLETERA = ("paciente", "profesional")


def _codigo_referido_unico() -> str:
    for _ in range(20):
        codigo = "".join(secrets.choice(ALFABETO_CODIGO) for _ in range(8))
        if not consultar("SELECT id FROM cuentas WHERE codigo_referido = %s", (codigo,), uno=True):
            return codigo
    raise RuntimeError("No fue posible generar un código de referidos único.")


def crear(
    nombre: str,
    email: str,
    password_hash: str,
    rol: str,
    fecha_nacimiento,
    perfil_profesional: dict | None = None,
    referidor_id: int | None = None,
) -> int:
    """Inserta una cuenta en estado 'pendiente' (más su perfil profesional y su referido, si aplica)."""
    cuenta_id = ejecutar(
        "INSERT INTO cuentas (nombre, email, password_hash, rol, fecha_nacimiento, estado) "
        "VALUES (%s, %s, %s, %s, %s, 'pendiente')",
        (nombre, email, password_hash, rol, fecha_nacimiento),
    )
    if perfil_profesional is not None:
        ejecutar(
            "INSERT INTO perfiles_profesionales (cuenta_id, especialidad, tarjeta_archivo, tarjeta_mime) "
            "VALUES (%s, %s, %s, %s)",
            (
                cuenta_id,
                perfil_profesional["especialidad"],
                perfil_profesional.get("tarjeta_archivo"),
                perfil_profesional.get("tarjeta_mime"),
            ),
        )
    if referidor_id is not None:
        ejecutar("INSERT INTO referidos (referidor_id, referido_id) VALUES (%s, %s)", (referidor_id, cuenta_id))
    return cuenta_id


def activar(cuenta_id: int, administrador_id: int | None = None, por_bot: bool = False) -> dict | None:
    """Activa una cuenta pendiente. Devuelve datos para notificar, o None si ya no estaba pendiente.

    El UPDATE condicionado a estado = 'pendiente' hace que, si el administrador y el robot
    intentan activar la misma cuenta a la vez, solo uno lo consiga.
    """
    if actualizar("UPDATE cuentas SET estado = 'activo' WHERE id = %s AND estado = 'pendiente'", (cuenta_id,)) == 0:
        return None
    cuenta = consultar("SELECT id, nombre, email, rol FROM cuentas WHERE id = %s", (cuenta_id,), uno=True)
    resultado = {"cuenta": cuenta, "codigo": None, "referidor": None, "puntos": 0}

    if cuenta["rol"] in ROLES_CON_BILLETERA:
        resultado["codigo"] = _codigo_referido_unico()
        ejecutar("UPDATE cuentas SET codigo_referido = %s WHERE id = %s", (resultado["codigo"], cuenta_id))
        ejecutar("INSERT INTO billeteras (cuenta_id) VALUES (%s)", (cuenta_id,))
        bono = current_app.config["BONO_BIENVENIDA"]
        if cuenta["rol"] == "paciente" and bono > 0:
            saldos = creditos.bloquear(cuenta_id)
            creditos.aplicar(cuenta_id, bono, "bono", saldos, nota="Bono de bienvenida")

    if cuenta["rol"] == "profesional":
        ejecutar(
            "UPDATE perfiles_profesionales SET revisado_por = %s, revisado_por_bot = %s, "
            "revisado_en = UTC_TIMESTAMP(), motivo_rechazo = NULL WHERE cuenta_id = %s",
            (administrador_id, 1 if por_bot else 0, cuenta_id),
        )

    resultado["referidor"], resultado["puntos"] = _completar_referido(cuenta_id)
    actor = "robot" if por_bot else ("administrador" if administrador_id else "sistema")
    auditoria.registrar("cuenta_activada", administrador_id, f"cuenta={cuenta_id} por={actor}")
    return resultado


def _completar_referido(referido_id: int):
    """Si la cuenta se registró con un código, acredita los puntos al referidor."""
    referido = consultar(
        "SELECT id, referidor_id FROM referidos WHERE referido_id = %s AND estado = 'pendiente' FOR UPDATE",
        (referido_id,),
        uno=True,
    )
    if not referido:
        return None, 0
    puntos = current_app.config["PUNTOS_POR_REFERIDO"]
    ejecutar(
        "UPDATE referidos SET estado = 'completado', puntos = %s, completado_en = UTC_TIMESTAMP() WHERE id = %s",
        (puntos, referido["id"]),
    )
    ejecutar("UPDATE billeteras SET puntos = puntos + %s WHERE cuenta_id = %s", (puntos, referido["referidor_id"]))
    ejecutar(
        "INSERT INTO movimientos_puntos (cuenta_id, tipo, puntos, referencia) VALUES (%s, 'referido', %s, %s)",
        (referido["referidor_id"], puntos, f"referido:{referido_id}"),
    )
    referidor = consultar(
        "SELECT nombre, email FROM cuentas WHERE id = %s", (referido["referidor_id"],), uno=True
    )
    return referidor, puntos


def rechazar(cuenta_id: int, administrador_id: int, motivo: str) -> dict | None:
    """Rechaza una solicitud de profesional pendiente. Devuelve datos para notificar, o None."""
    if (
        actualizar(
            "UPDATE cuentas SET estado = 'rechazado' WHERE id = %s AND estado = 'pendiente' AND rol = 'profesional'",
            (cuenta_id,),
        )
        == 0
    ):
        return None
    ejecutar(
        "UPDATE perfiles_profesionales SET revisado_por = %s, revisado_por_bot = 0, revisado_en = UTC_TIMESTAMP(), "
        "motivo_rechazo = %s WHERE cuenta_id = %s",
        (administrador_id, motivo, cuenta_id),
    )
    ejecutar("UPDATE referidos SET estado = 'cancelado' WHERE referido_id = %s AND estado = 'pendiente'", (cuenta_id,))
    auditoria.registrar("cuenta_rechazada", administrador_id, f"cuenta={cuenta_id}")
    return consultar("SELECT nombre, email FROM cuentas WHERE id = %s", (cuenta_id,), uno=True)


def notificar_activacion(resultado: dict) -> None:
    """Envía los correos derivados de una activación. Llamar DESPUÉS de confirmar la transacción."""
    cuenta = resultado["cuenta"]
    if cuenta["rol"] == "profesional":
        correo.notificar_activacion(cuenta["email"], cuenta["nombre"], resultado["codigo"])
    if resultado["referidor"]:
        correo.notificar_referido_completado(
            resultado["referidor"]["email"], resultado["referidor"]["nombre"], resultado["puntos"]
        )


def profesional_completo(cuenta_id: int) -> bool:
    """¿La solicitud del profesional tiene la documentación completa?

    Criterio: tarjeta profesional adjunta (archivo presente en disco), fecha de nacimiento
    de un mayor de edad y correo registrado. Lo usan tanto el panel como el robot.
    """
    fila = consultar(
        "SELECT c.email, c.fecha_nacimiento, p.tarjeta_archivo FROM cuentas c "
        "JOIN perfiles_profesionales p ON p.cuenta_id = c.id WHERE c.id = %s AND c.rol = 'profesional'",
        (cuenta_id,),
        uno=True,
    )
    if not fila or not fila["email"] or not fila["fecha_nacimiento"]:
        return False
    return archivos.existe(fila["tarjeta_archivo"])
