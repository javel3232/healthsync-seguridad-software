"""Fábrica de la aplicación Flask de HealthSync."""
import logging
from datetime import date, datetime
from decimal import Decimal

import mysql.connector
from flask import Flask, jsonify, request
from flask.json.provider import DefaultJSONProvider
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from . import db
from .config import cargar_configuracion
from .errores import ErrorNegocio
from .seguridad import verificar_csrf

# Mensajes en español para los errores HTTP que genera el propio framework.
MENSAJES_HTTP = {
    400: "Petición inválida.",
    401: "Debe iniciar sesión.",
    403: "No tiene permisos para esta acción.",
    404: "Recurso no encontrado.",
    405: "Método no permitido.",
    413: "El archivo o la petición es demasiado grande.",
    415: "Tipo de contenido no soportado.",
}


def _serializar(objeto):
    """Fechas en ISO 8601 (las de hora van en UTC con 'Z') y decimales como números."""
    if isinstance(objeto, datetime):
        return objeto.isoformat(timespec="seconds") + "Z"
    if isinstance(objeto, date):
        return objeto.isoformat()
    if isinstance(objeto, Decimal):
        return float(objeto)
    return DefaultJSONProvider.default(objeto)


class ProveedorJson(DefaultJSONProvider):
    default = staticmethod(_serializar)
    sort_keys = False


def create_app() -> Flask:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    app = Flask(__name__)
    app.json = ProveedorJson(app)
    app.config.update(cargar_configuracion())
    # nginx está delante: toma la IP real del cliente del encabezado que nginx fija.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

    # Importación tardía: los módulos de rutas necesitan la aplicación ya configurada.
    from . import (
        rutas_admin, rutas_alertas, rutas_auth, rutas_consultas, rutas_creditos,
        rutas_cuentas, rutas_generales, rutas_internas, rutas_referidos, rutas_wearables,
    )

    for modulo in (
        rutas_generales, rutas_auth, rutas_cuentas, rutas_admin, rutas_referidos,
        rutas_creditos, rutas_wearables, rutas_consultas, rutas_alertas, rutas_internas,
    ):
        app.register_blueprint(modulo.bp)
    app.teardown_appcontext(db.cerrar)
    app.before_request(verificar_csrf)

    @app.after_request
    def cabeceras_de_seguridad(respuesta):
        # La API solo devuelve datos: ningún navegador debe interpretarla como página ni guardarla en caché.
        respuesta.headers.setdefault("X-Content-Type-Options", "nosniff")
        respuesta.headers.setdefault("Cache-Control", "no-store")
        respuesta.headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        return respuesta

    # ------------------------------------------------------------ Manejo de errores
    # Ninguna respuesta de error incluye trazas, consultas SQL ni rutas del servidor.
    @app.errorhandler(ErrorNegocio)
    def error_negocio(error):
        return jsonify(error=error.mensaje), error.codigo

    @app.errorhandler(HTTPException)
    def error_http(error):
        mensaje = MENSAJES_HTTP.get(error.code, "Error en la petición.")
        # Los abort(codigo, description=...) de la propia aplicación llevan un mensaje en español.
        if error.description and error.description != type(error)().description:
            mensaje = error.description
        return jsonify(error=mensaje), error.code

    @app.errorhandler(mysql.connector.Error)
    def error_base_de_datos(error):
        app.logger.error("Error de base de datos (%s): %s", request.path, error)
        return jsonify(error="El servicio no está disponible en este momento. Intente de nuevo."), 503

    @app.errorhandler(Exception)
    def error_inesperado(error):
        app.logger.exception("Error no controlado en %s %s", request.method, request.path)
        return jsonify(error="Ocurrió un error interno. Intente de nuevo más tarde."), 500

    return app
