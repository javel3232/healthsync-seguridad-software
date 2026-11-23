"""Rutas de soporte: estado del servicio y configuración pública."""
from flask import Blueprint, current_app, jsonify

from .db import consultar

bp = Blueprint("general", __name__, url_prefix="/api")


@bp.get("/salud")
def salud():
    """Comprobación de salud (la usa Docker). Verifica que la base de datos responde."""
    consultar("SELECT 1 AS ok", uno=True)
    return jsonify(estado="ok")


@bp.get("/config")
def config_publica():
    """Datos que necesita la interfaz antes de iniciar sesión. No incluye nada interno."""
    caso = current_app.config["CASO"]
    roles_publicos = {
        clave: {"etiqueta": datos["etiqueta"]}
        for clave, datos in caso["roles"].items()
        if datos.get("registro_publico")
    }
    return jsonify(caso=caso["clave"], nombre=caso["nombre"], roles=roles_publicos)
