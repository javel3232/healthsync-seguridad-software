"""Almacenamiento de archivos subidos (foto de la tarjeta profesional).

Controles aplicados:
  * Solo se aceptan PNG y JPEG; el tipo se determina por los primeros bytes del
    contenido, no por el nombre ni por el Content-Type que declara el cliente.
  * Tamaño máximo de 2 MB.
  * El archivo se guarda con un nombre aleatorio, fuera de la carpeta que sirve
    nginx. El nombre original nunca se usa como ruta.
  * Solo se entrega a través de un endpoint que verifica el rol del solicitante.
"""
import re
import secrets
from pathlib import Path

from flask import current_app, send_file
from werkzeug.datastructures import FileStorage

from .errores import ErrorNegocio

TAMANO_MAXIMO = 2 * 1024 * 1024
TAMANO_MINIMO = 64
# Firma inicial (magic bytes) -> (tipo MIME, extensión)
FIRMAS = {
    b"\x89PNG\r\n\x1a\n": ("image/png", ".png"),
    b"\xff\xd8\xff": ("image/jpeg", ".jpg"),
}
_NOMBRE_VALIDO = re.compile(r"^[0-9a-f]{32}\.(png|jpg)$")


def _directorio() -> Path:
    ruta = Path(current_app.config["DIRECTORIO_ARCHIVOS"])
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


def detectar_tipo(contenido: bytes) -> tuple[str, str] | None:
    for firma, tipo in FIRMAS.items():
        if contenido.startswith(firma):
            return tipo
    return None


def guardar_bytes_imagen(contenido: bytes) -> tuple[str, str]:
    """Valida y guarda una imagen. Devuelve (nombre_en_disco, tipo_mime)."""
    if not TAMANO_MINIMO <= len(contenido) <= TAMANO_MAXIMO:
        raise ErrorNegocio("La imagen debe pesar entre 64 bytes y 2 MB.")
    tipo = detectar_tipo(contenido)
    if tipo is None:
        raise ErrorNegocio("La foto de la tarjeta profesional debe ser una imagen PNG o JPEG válida.")
    mime, extension = tipo
    nombre = secrets.token_hex(16) + extension
    with open(_directorio() / nombre, "xb") as destino:  # "x": falla si el archivo ya existe
        destino.write(contenido)
    return nombre, mime


def leer_y_validar(archivo: FileStorage | None) -> bytes:
    """Lee la imagen de un formulario multipart y comprueba tamaño y tipo, sin guardarla todavía."""
    if archivo is None or not archivo.filename:
        raise ErrorNegocio("Los profesionales deben adjuntar la foto de su tarjeta profesional.")
    contenido = archivo.read(TAMANO_MAXIMO + 1)
    if not TAMANO_MINIMO <= len(contenido) <= TAMANO_MAXIMO or detectar_tipo(contenido) is None:
        raise ErrorNegocio("La foto de la tarjeta profesional debe ser una imagen PNG o JPEG de hasta 2 MB.")
    return contenido


def eliminar(nombre: str) -> None:
    """Borra un archivo guardado (se usa si la transacción de base de datos falla)."""
    if _NOMBRE_VALIDO.match(nombre or ""):
        (_directorio() / nombre).unlink(missing_ok=True)


def enviar_imagen(nombre: str, mime: str):
    """Respuesta HTTP con la imagen guardada, o ErrorNegocio 404 si no existe."""
    if not _NOMBRE_VALIDO.match(nombre or ""):
        raise ErrorNegocio("Archivo no encontrado.", 404)
    ruta = _directorio() / nombre
    if not ruta.is_file():
        raise ErrorNegocio("Archivo no encontrado.", 404)
    respuesta = send_file(ruta, mimetype=mime, conditional=False, max_age=0)
    respuesta.headers["Content-Disposition"] = "inline"
    respuesta.headers["Cache-Control"] = "private, no-store"
    return respuesta


def existe(nombre: str | None) -> bool:
    return bool(nombre) and bool(_NOMBRE_VALIDO.match(nombre)) and (_directorio() / nombre).is_file()
