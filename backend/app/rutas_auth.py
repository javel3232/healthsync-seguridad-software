"""Módulo 1 - Registro, inicio y cierre de sesión.

Seguridad de esta parte:
  * Contraseñas con scrypt; política de longitud y de contraseñas comunes.
  * Bloqueo temporal de la cuenta tras varios intentos fallidos.
  * Respuesta idéntica para "usuario no existe" y "contraseña incorrecta".
  * El registro responde igual si el correo ya existe (no revela qué correos hay registrados).
  * La sesión se renueva al ingresar y se invalida en el servidor al salir.
"""
from datetime import timedelta

from flask import Blueprint, current_app, jsonify, request, session

from . import archivos, auditoria, correo, validaciones as v
from .db import actualizar, confirmar, consultar, ejecutar
from .errores import ErrorNegocio
from .seguridad import (
    hash_password,
    iniciar_sesion,
    login_requerido,
    token_csrf,
    usuario_actual,
    verificar_password,
)
from .servicios import cuentas
from .tiempo import ahora_utc

bp = Blueprint("auth", __name__, url_prefix="/api/auth")

# Hash de una contraseña inventada: se compara cuando el correo no existe para que
# el tiempo de respuesta no delate si la cuenta existe.
_HASH_FALSO = hash_password("contrasena-que-nadie-usa-0")

MENSAJE_REGISTRO = (
    "Solicitud recibida. Le enviamos un correo con el estado de su cuenta "
    "(los pacientes pueden ingresar de inmediato; los profesionales, cuando validemos su tarjeta)."
)


@bp.post("/registro")
def registro():
    """Registro público. Se envía como multipart/form-data porque los profesionales adjuntan una foto."""
    formulario = request.form
    roles_publicos = [r for r, d in current_app.config["CASO"]["roles"].items() if d.get("registro_publico")]

    nombre = v.texto(formulario.get("nombre"), "El nombre", 2, 100)
    email = v.correo(formulario.get("email"))
    password = v.contrasena(formulario.get("password"), email)
    nacimiento = v.fecha_nacimiento(formulario.get("fecha_nacimiento"))
    rol = v.opcion(formulario.get("rol"), "El tipo de cuenta", roles_publicos)
    codigo = v.texto(formulario.get("codigo_referido"), "El código de referidos", 1, 20, opcional=True).upper()

    contenido_tarjeta = None
    especialidad = "Medicina general"
    if rol == "profesional":
        contenido_tarjeta = archivos.leer_y_validar(request.files.get("tarjeta"))
        especialidad = v.texto(formulario.get("especialidad"), "La especialidad", 3, 80, opcional=True) or especialidad

    referidor_id = None
    if codigo:
        referidor = consultar(
            "SELECT id FROM cuentas WHERE codigo_referido = %s AND estado = 'activo'", (codigo,), uno=True
        )
        if not referidor:
            raise ErrorNegocio("El código de referidos no es válido.")
        referidor_id = referidor["id"]

    # Correo ya registrado: misma respuesta que un registro nuevo, y aviso al dueño del correo.
    if consultar("SELECT id FROM cuentas WHERE email = %s", (email,), uno=True):
        correo.notificar_correo_ya_registrado(email)
        return jsonify(mensaje=MENSAJE_REGISTRO), 201

    nombre_tarjeta = None
    perfil = None
    if contenido_tarjeta is not None:
        nombre_tarjeta, mime = archivos.guardar_bytes_imagen(contenido_tarjeta)
        perfil = {"especialidad": especialidad, "tarjeta_archivo": nombre_tarjeta, "tarjeta_mime": mime}
    try:
        cuenta_id = cuentas.crear(nombre, email, hash_password(password), rol, nacimiento, perfil, referidor_id)
        requiere_aprobacion = current_app.config["CASO"]["roles"][rol].get("requiere_aprobacion", False)
        activacion = None if requiere_aprobacion else cuentas.activar(cuenta_id)
        auditoria.registrar("registro", cuenta_id, f"rol={rol}")
        confirmar()
    except Exception:
        if nombre_tarjeta:
            archivos.eliminar(nombre_tarjeta)  # no dejar archivos huérfanos si la transacción falla
        raise

    correo.notificar_registro(email, nombre, activa=activacion is not None)
    if activacion:
        cuentas.notificar_activacion(activacion)
    return jsonify(mensaje=MENSAJE_REGISTRO), 201


@bp.post("/ingresar")
def ingresar():
    datos = v.cuerpo_json()
    email = str(datos.get("email", "")).strip().lower()[:254]
    password = str(datos.get("password", ""))[:128]
    config = current_app.config
    ahora = ahora_utc()

    cuenta = consultar("SELECT * FROM cuentas WHERE email = %s", (email,), uno=True)

    if cuenta and cuenta["bloqueado_hasta"] and cuenta["bloqueado_hasta"] > ahora:
        auditoria.registrar("login_bloqueado", cuenta["id"], "cuenta bloqueada temporalmente")
        confirmar()
        raise ErrorNegocio("Demasiados intentos fallidos. Intente de nuevo en unos minutos.", 429)

    # Siempre se calcula un hash, exista o no la cuenta (tiempo de respuesta uniforme).
    correcta = verificar_password(password, cuenta["password_hash"] if cuenta else _HASH_FALSO)
    if not cuenta or not correcta:
        if cuenta:
            intentos = cuenta["intentos_fallidos"] + 1
            bloqueo = None
            if intentos >= config["LOGIN_MAX_INTENTOS"]:
                bloqueo, intentos = ahora + timedelta(minutes=config["LOGIN_BLOQUEO_MINUTOS"]), 0
            ejecutar(
                "UPDATE cuentas SET intentos_fallidos = %s, bloqueado_hasta = %s WHERE id = %s",
                (intentos, bloqueo, cuenta["id"]),
            )
        auditoria.registrar("login_fallido", cuenta["id"] if cuenta else None)
        confirmar()
        raise ErrorNegocio("Correo o contraseña incorrectos.", 401)

    if cuenta["estado"] == "pendiente":
        raise ErrorNegocio("Su cuenta está pendiente de validación. Le avisaremos por correo cuando esté activa.", 403)
    if cuenta["estado"] != "activo":
        raise ErrorNegocio("Su cuenta no está habilitada. Comuníquese con soporte.", 403)

    ejecutar("UPDATE cuentas SET intentos_fallidos = 0, bloqueado_hasta = NULL WHERE id = %s", (cuenta["id"],))
    auditoria.registrar("login_exitoso", cuenta["id"])
    confirmar()
    iniciar_sesion(cuenta)
    return jsonify(usuario=_publico(cuenta), csrf_token=token_csrf())


@bp.post("/salir")
def salir():
    """Cierra la sesión y la invalida en el servidor (también en otros navegadores)."""
    usuario = usuario_actual()
    if usuario:
        ejecutar("UPDATE cuentas SET version_sesion = version_sesion + 1 WHERE id = %s", (usuario["id"],))
        auditoria.registrar("logout", usuario["id"])
        confirmar()
    session.clear()
    return jsonify(mensaje="Sesión cerrada.")


@bp.get("/yo")
def yo():
    """Estado de la sesión. La interfaz lo consulta al cargar para saber si hay usuario y obtener el token CSRF."""
    usuario = usuario_actual()
    if usuario is None:
        return jsonify(usuario=None, csrf_token=None)
    return jsonify(usuario=usuario, csrf_token=token_csrf())


@bp.post("/cambiar-password")
@login_requerido
def cambiar_password():
    datos = v.cuerpo_json()
    usuario = usuario_actual()
    cuenta = consultar("SELECT * FROM cuentas WHERE id = %s", (usuario["id"],), uno=True)
    if not verificar_password(str(datos.get("password_actual", "")), cuenta["password_hash"]):
        auditoria.registrar("cambio_password_fallido", cuenta["id"])
        confirmar()
        raise ErrorNegocio("La contraseña actual no es correcta.", 403)
    nueva = v.contrasena(datos.get("password_nueva"), cuenta["email"])
    # Subir la versión de sesión cierra todas las demás sesiones abiertas de esta cuenta.
    actualizar(
        "UPDATE cuentas SET password_hash = %s, version_sesion = version_sesion + 1 WHERE id = %s",
        (hash_password(nueva), cuenta["id"]),
    )
    auditoria.registrar("cambio_password", cuenta["id"])
    confirmar()
    cuenta["version_sesion"] += 1
    iniciar_sesion(cuenta)
    return jsonify(mensaje="Contraseña actualizada.", csrf_token=token_csrf())


def _publico(cuenta: dict) -> dict:
    """Solo los campos que el cliente necesita: nunca el hash ni contadores internos."""
    return {k: cuenta[k] for k in ("id", "nombre", "email", "rol")}
