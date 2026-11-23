"""Cliente HTTP para la API externa del caso (simulador de Open mHealth o servicio real).

Solo se consultan rutas relativas a EXTERNAL_API_BASE_URL: ninguna ruta o URL
que venga de una petición del usuario se usa como destino (evita SSRF).
"""
import requests
from flask import current_app

TIMEOUT = (3, 10)  # (conexión, lectura) en segundos
TAMANO_MAXIMO_RESPUESTA = 5 * 1024 * 1024


class ErrorApiExterna(RuntimeError):
    """La API externa no respondió o respondió algo inesperado."""


def _encabezados() -> dict:
    encabezados = {"Accept": "application/json"}
    llave = current_app.config["EXTERNAL_API_KEY"]
    if llave:
        encabezados["Authorization"] = f"Bearer {llave}"
    return encabezados


def obtener_json(ruta: str, params: dict | None = None):
    """GET a EXTERNAL_API_BASE_URL/<ruta>. Devuelve el JSON o lanza ErrorApiExterna."""
    direccion = f"{current_app.config['EXTERNAL_API_BASE_URL']}/{ruta.lstrip('/')}"
    try:
        respuesta = requests.get(
            direccion, params=params, headers=_encabezados(), timeout=TIMEOUT, allow_redirects=False
        )
        if respuesta.status_code != 200:
            raise ErrorApiExterna(f"La API externa respondió con el estado {respuesta.status_code}.")
        if len(respuesta.content) > TAMANO_MAXIMO_RESPUESTA:
            raise ErrorApiExterna("La respuesta de la API externa es demasiado grande.")
        return respuesta.json()
    except requests.RequestException as error:
        raise ErrorApiExterna(f"No fue posible contactar la API externa ({type(error).__name__}).") from error
    except ValueError as error:
        raise ErrorApiExterna("La API externa devolvió una respuesta que no es JSON.") from error
