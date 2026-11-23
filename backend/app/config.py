"""Carga de configuración desde variables de entorno.

Toda la configuración sale de variables de entorno (archivo .env). Los valores
de negocio (bonos, límites, puntos) también se leen de aquí para no repetirlos
como números sueltos en el código.
"""
import json
import os
from datetime import timedelta
from pathlib import Path

RAIZ_CASOS = Path(__file__).resolve().parents[2] / "casos"

# Longitud mínima de SECRET_KEY: con menos, la firma de la cookie es débil.
LONGITUD_MINIMA_SECRET_KEY = 32


def cargar_caso() -> dict:
    """Lee casos/<caso>/caso.json: roles, cuentas de prueba y API externa."""
    caso = os.environ.get("CASO", "healthsync").lower()
    if caso not in ("healthsync", "marketplace"):
        raise RuntimeError(f"CASO desconocido: {caso!r}")
    with open(RAIZ_CASOS / caso / "caso.json", encoding="utf-8") as archivo:
        datos = json.load(archivo)
    datos["clave"] = caso
    return datos


def parametros_db() -> dict:
    """Parámetros de conexión. La aplicación usa un usuario sin privilegios de administración."""
    return {
        "host": os.environ.get("DB_HOST", "db"),
        "port": int(os.environ.get("DB_PORT", "3306")),
        "user": os.environ.get("MYSQL_USER", "app"),
        "password": os.environ.get("MYSQL_PASSWORD", ""),
        "database": os.environ.get("MYSQL_DATABASE", "app"),
        "connection_timeout": 5,
    }


def _entero(nombre: str, defecto: int) -> int:
    return int(os.environ.get(nombre, str(defecto)))


def cargar_configuracion() -> dict:
    caso = cargar_caso()
    url_externa = os.environ.get("EXTERNAL_API_BASE_URL", "").strip() or caso["api_externa"]["url_simulador"]

    secreto = os.environ.get("SECRET_KEY", "")
    if len(secreto) < LONGITUD_MINIMA_SECRET_KEY:
        raise RuntimeError(f"SECRET_KEY debe tener al menos {LONGITUD_MINIMA_SECRET_KEY} caracteres (ver .env.example).")
    token_robot = os.environ.get("WORKER_TOKEN", "")
    if len(token_robot) < 16:
        raise RuntimeError("WORKER_TOKEN debe tener al menos 16 caracteres (ver .env.example).")

    return {
        # --- Sesión: cookie firmada, no accesible desde JavaScript, caducidad corta.
        "SECRET_KEY": secreto,
        "SESSION_COOKIE_NAME": "sesion",
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        # Ponga COOKIE_SECURE=true cuando se sirva por HTTPS.
        "SESSION_COOKIE_SECURE": os.environ.get("COOKIE_SECURE", "false").lower() == "true",
        "PERMANENT_SESSION_LIFETIME": timedelta(hours=_entero("SESION_HORAS", 2)),
        "SESSION_REFRESH_EACH_REQUEST": True,
        # Tamaño máximo de cualquier petición (la foto de la tarjeta limita el caso más grande).
        "MAX_CONTENT_LENGTH": 3 * 1024 * 1024,
        "JSON_SORT_KEYS": False,
        # --- Infraestructura
        "CASO": caso,
        "DB": parametros_db(),
        "WORKER_TOKEN": token_robot,
        "SMTP_HOST": os.environ.get("SMTP_HOST", "mailpit"),
        "SMTP_PORT": int(os.environ.get("SMTP_PORT", "1025")),
        "MAIL_FROM": os.environ.get("MAIL_FROM", f"no-responder@{caso['clave']}.test"),
        "EXTERNAL_API_BASE_URL": url_externa.rstrip("/"),
        "EXTERNAL_API_KEY": os.environ.get("EXTERNAL_API_KEY", ""),
        "DIRECTORIO_ARCHIVOS": os.environ.get("UPLOAD_DIR", "/var/lib/healthsync/archivos"),
        # --- Reglas de negocio
        "BONO_BIENVENIDA": _entero("BONO_BIENVENIDA", 100),        # créditos al registrarse un paciente
        "PUNTOS_POR_REFERIDO": _entero("PUNTOS_POR_REFERIDO", 50),  # puntos que gana el referidor
        "PUNTOS_POR_MES_PREMIUM": _entero("PUNTOS_POR_MES_PREMIUM", 100),
        "MAX_TRANSFERENCIA": _entero("MAX_TRANSFERENCIA", 1000),    # créditos por transferencia
        "MAX_DISPOSITIVOS": 5,
        "MAX_ALERTAS": 20,
        "DURACION_CONSULTA_MIN": 30,
        "LOGIN_MAX_INTENTOS": _entero("LOGIN_MAX_INTENTOS", 5),
        "LOGIN_BLOQUEO_MINUTOS": _entero("LOGIN_BLOQUEO_MINUTOS", 15),
    }
