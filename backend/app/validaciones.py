"""Validación y normalización de los datos que llegan en las peticiones.

Toda función lanza `ErrorNegocio` (400) con un mensaje claro si el dato no es
válido. Los datos se validan siempre en el servidor, aunque el formulario de la
interfaz ya los revise.
"""
import math
import re
import unicodedata
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation

from flask import request

from .errores import ErrorNegocio

_EMAIL = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}$")
# Contraseñas demasiado comunes que se rechazan aunque cumplan la longitud.
_CONTRASENAS_COMUNES = {
    "1234567890", "contrasena1", "contraseña1", "password123", "qwerty12345",
    "abcdefghij1", "12345678910", "admin12345", "colombia123", "123456789a",
}


def cuerpo_json() -> dict:
    """Devuelve el cuerpo JSON de la petición. Exige Content-Type: application/json."""
    if not request.is_json:
        raise ErrorNegocio("La petición debe enviarse como JSON.", 415)
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        raise ErrorNegocio("El cuerpo de la petición no es un objeto JSON válido.")
    return datos


def texto(valor, campo: str, minimo: int = 1, maximo: int = 100, opcional: bool = False, multilinea: bool = False) -> str:
    """Texto sin caracteres de control y con longitud acotada.

    Por defecto es de una sola línea (nombres, correos, motivos): rechaza saltos de línea y
    tabulaciones, lo que además impide inyectar encabezados en los correos que se envían.
    """
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        if opcional:
            return ""
        raise ErrorNegocio(f"{campo} es obligatorio.")
    if not isinstance(valor, str):
        raise ErrorNegocio(f"{campo} debe ser un texto.")
    limpio = unicodedata.normalize("NFC", valor).strip()
    permitidos = "\n\t" if multilinea else ""
    if any(unicodedata.category(c).startswith("C") and c not in permitidos for c in limpio):
        raise ErrorNegocio(f"{campo} contiene caracteres no permitidos.")
    if not minimo <= len(limpio) <= maximo:
        raise ErrorNegocio(f"{campo} debe tener entre {minimo} y {maximo} caracteres.")
    return limpio


def correo(valor) -> str:
    email = texto(valor, "El correo", 5, 254).lower()
    if not _EMAIL.match(email):
        raise ErrorNegocio("El correo no tiene un formato válido.")
    return email


def contrasena(valor, email: str = "") -> str:
    """Política: 10 a 128 caracteres con letras y números; sin contraseñas comunes ni el correo."""
    if not isinstance(valor, str) or not 10 <= len(valor) <= 128:
        raise ErrorNegocio("La contraseña debe tener entre 10 y 128 caracteres.")
    if not re.search(r"[A-Za-z]", valor) or not re.search(r"\d", valor):
        raise ErrorNegocio("La contraseña debe combinar letras y números.")
    if valor.lower() in _CONTRASENAS_COMUNES or (email and valor.lower() == email.lower()):
        raise ErrorNegocio("La contraseña es demasiado común o predecible.")
    return valor


def fecha_nacimiento(valor, edad_minima: int = 18) -> date:
    """Fecha ISO (AAAA-MM-DD) que corresponda a una persona de `edad_minima` a 120 años."""
    try:
        fecha = date.fromisoformat(str(valor))
    except ValueError:
        raise ErrorNegocio("La fecha de nacimiento debe tener el formato AAAA-MM-DD.") from None
    hoy = date.today()
    edad = hoy.year - fecha.year - ((hoy.month, hoy.day) < (fecha.month, fecha.day))
    if edad > 120 or fecha > hoy:
        raise ErrorNegocio("La fecha de nacimiento no es válida.")
    if edad < edad_minima:
        raise ErrorNegocio(f"Debe ser mayor de {edad_minima} años para registrarse.")
    return fecha


def entero(valor, campo: str, minimo: int, maximo: int) -> int:
    # bool es subclase de int en Python: se rechaza explícitamente.
    if isinstance(valor, bool) or not isinstance(valor, (int, str)):
        raise ErrorNegocio(f"{campo} debe ser un número entero.")
    try:
        numero = int(valor)
    except ValueError:
        raise ErrorNegocio(f"{campo} debe ser un número entero.") from None
    if not minimo <= numero <= maximo:
        raise ErrorNegocio(f"{campo} debe estar entre {minimo} y {maximo}.")
    return numero


def decimal(valor, campo: str, minimo: float, maximo: float) -> Decimal:
    if isinstance(valor, bool) or not isinstance(valor, (int, float, str)):
        raise ErrorNegocio(f"{campo} debe ser un número.")
    try:
        numero = Decimal(str(valor))
    except InvalidOperation:
        raise ErrorNegocio(f"{campo} debe ser un número.") from None
    if not numero.is_finite() or not (Decimal(str(minimo)) <= numero <= Decimal(str(maximo))):
        raise ErrorNegocio(f"{campo} debe estar entre {minimo} y {maximo}.")
    return numero.quantize(Decimal("0.01"))


def opcion(valor, campo: str, permitidas) -> str:
    if valor not in permitidas:
        raise ErrorNegocio(f"{campo} no es válido.")
    return valor


def booleano(valor, campo: str) -> bool:
    if not isinstance(valor, bool):
        raise ErrorNegocio(f"{campo} debe ser verdadero o falso.")
    return valor


def fecha_hora_utc(valor, campo: str) -> datetime:
    """Convierte un ISO 8601 con zona horaria a datetime UTC "ingenuo" (como se guarda en la base)."""
    try:
        momento = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    except ValueError:
        raise ErrorNegocio(f"{campo} no tiene un formato de fecha y hora válido.") from None
    if momento.tzinfo is None:
        raise ErrorNegocio(f"{campo} debe incluir la zona horaria.")
    return momento.astimezone(timezone.utc).replace(tzinfo=None)


def numero_finito(valor) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(valor)
