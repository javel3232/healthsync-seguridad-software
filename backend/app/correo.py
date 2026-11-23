"""Envío de correo. En el entorno de pruebas todo correo llega a Mailpit (http://localhost:8025).

Cada función `notificar_*` arma el mensaje de un evento del negocio. Los correos
se envían DESPUÉS de confirmar la transacción de base de datos, y un fallo en el
envío nunca revierte la operación: solo queda registrado en el log.
"""
import logging
import smtplib
from email.message import EmailMessage

from flask import current_app

log = logging.getLogger(__name__)

ETIQUETAS_METRICA = {
    "heart-rate": "frecuencia cardíaca",
    "step-count": "pasos diarios",
    "oxygen-saturation": "saturación de oxígeno",
    "sleep-duration": "horas de sueño",
}


def enviar(destinatario: str, asunto: str, cuerpo: str) -> bool:
    """Envía un correo de texto. Devuelve False (sin lanzar error) si no se pudo enviar."""
    try:
        mensaje = EmailMessage()
        mensaje["From"] = current_app.config["MAIL_FROM"]
        mensaje["To"] = destinatario
        mensaje["Subject"] = asunto
        mensaje.set_content(cuerpo)
        with smtplib.SMTP(current_app.config["SMTP_HOST"], current_app.config["SMTP_PORT"], timeout=5) as smtp:
            smtp.send_message(mensaje)
        return True
    except (OSError, smtplib.SMTPException, ValueError):
        log.exception("No se pudo enviar el correo '%s'", asunto)
        return False


# ------------------------------------------------------------ Registro y cuentas
def notificar_registro(email: str, nombre: str, activa: bool) -> bool:
    if activa:
        cuerpo = f"Hola {nombre}.\n\nSu cuenta de HealthSync fue creada y ya está activa. Puede iniciar sesión."
    else:
        cuerpo = (
            f"Hola {nombre}.\n\nRecibimos su solicitud de registro como profesional de salud. "
            "Su cuenta quedará activa cuando validemos su tarjeta profesional. Le avisaremos por este medio."
        )
    return enviar(email, "Registro recibido - HealthSync", cuerpo)


def notificar_correo_ya_registrado(email: str) -> bool:
    cuerpo = (
        "Alguien intentó registrarse en HealthSync con este correo, que ya tiene una cuenta.\n\n"
        "Si fue usted, simplemente inicie sesión. Si no, puede ignorar este mensaje."
    )
    return enviar(email, "Intento de registro con su correo - HealthSync", cuerpo)


def notificar_activacion(email: str, nombre: str, codigo_referido: str) -> bool:
    cuerpo = (
        f"Hola {nombre}.\n\nSu cuenta de profesional de salud fue validada y ya está activa. "
        "Su perfil es visible en el directorio de HealthSync y los pacientes pueden agendar consultas con usted.\n\n"
        f"Su código de referidos: {codigo_referido}"
    )
    return enviar(email, "Su cuenta fue activada - HealthSync", cuerpo)


def notificar_rechazo(email: str, nombre: str, motivo: str) -> bool:
    cuerpo = f"Hola {nombre}.\n\nNo pudimos validar su solicitud de registro.\nMotivo: {motivo}"
    return enviar(email, "Su solicitud no fue aprobada - HealthSync", cuerpo)


def notificar_referido_completado(email: str, nombre: str, puntos: int) -> bool:
    cuerpo = f"Hola {nombre}.\n\nUn usuario que se registró con su código completó su registro. Ganó {puntos} puntos."
    return enviar(email, "Ganó puntos por un referido - HealthSync", cuerpo)


# ------------------------------------------------------------------- Consultas
def notificar_consulta_confirmada(email: str, nombre: str, otro: str, inicio_utc: str, costo: int, es_paciente: bool) -> bool:
    if es_paciente:
        detalle = f"Su consulta con {otro} quedó confirmada para el {inicio_utc} UTC. Se descontaron {costo} créditos."
    else:
        detalle = f"El paciente {otro} agendó una consulta con usted para el {inicio_utc} UTC."
    return enviar(email, "Consulta confirmada - HealthSync", f"Hola {nombre}.\n\n{detalle}")


def notificar_consulta_cancelada(email: str, nombre: str, inicio_utc: str, reembolso: int | None) -> bool:
    extra = f" Se devolvieron {reembolso} créditos al paciente." if reembolso else ""
    return enviar(
        email, "Consulta cancelada - HealthSync", f"Hola {nombre}.\n\nLa consulta del {inicio_utc} UTC fue cancelada.{extra}"
    )


# --------------------------------------------------------------------- Alertas
def notificar_alerta_paciente(email: str, nombre: str, tipo: str, operador: str, umbral, valor) -> bool:
    cuerpo = (
        f"Hola {nombre}.\n\nSe activó una de sus alertas de salud: {ETIQUETAS_METRICA.get(tipo, tipo)} "
        f"{'superó' if operador == 'mayor' else 'cayó por debajo de'} {umbral}. Lectura más reciente: {valor}.\n\n"
        "Si se siente mal, consulte a un profesional de salud."
    )
    return enviar(email, "Alerta de salud - HealthSync", cuerpo)


def notificar_alerta_profesional(email: str, nombre: str, paciente: str, tipo: str, operador: str, umbral, valor) -> bool:
    cuerpo = (
        f"Hola {nombre}.\n\nSu paciente {paciente}, que autorizó este aviso, activó una alerta: "
        f"{ETIQUETAS_METRICA.get(tipo, tipo)} {'superó' if operador == 'mayor' else 'cayó por debajo de'} {umbral}. "
        f"Lectura más reciente: {valor}."
    )
    return enviar(email, "Alerta de un paciente - HealthSync", cuerpo)


# ------------------------------------------------------------- Transferencias
def notificar_transferencia(email: str, nombre: str, origen: str, monto: int) -> bool:
    cuerpo = f"Hola {nombre}.\n\n{origen} le transfirió {monto} créditos. Ya están disponibles en su saldo."
    return enviar(email, "Recibió créditos - HealthSync", cuerpo)
