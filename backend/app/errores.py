"""Errores de negocio.

Las rutas y los servicios lanzan `ErrorNegocio` cuando la petición no se puede
atender (datos inválidos, falta de permisos, saldo insuficiente...). La fábrica
de la aplicación lo convierte en una respuesta JSON {"error": "..."} con el
código HTTP indicado. El mensaje es siempre apto para mostrarse al usuario:
nunca incluye detalles internos.
"""


class ErrorNegocio(Exception):
    def __init__(self, mensaje: str, codigo: int = 400):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.codigo = codigo
