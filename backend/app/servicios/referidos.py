"""Canje de puntos de referidos por meses de suscripción premium."""
import calendar
from datetime import date

from flask import current_app

from ..db import consultar, ejecutar
from ..errores import ErrorNegocio


def sumar_meses(fecha: date, meses: int) -> date:
    """Suma meses calendario a una fecha (ajusta el día al fin de mes si hace falta)."""
    indice = fecha.month - 1 + meses
    anio = fecha.year + indice // 12
    mes = indice % 12 + 1
    return date(anio, mes, min(fecha.day, calendar.monthrange(anio, mes)[1]))


def canjear(cuenta_id: int, meses: int) -> dict:
    """Cambia puntos por meses de premium. Devuelve el estado nuevo de la billetera."""
    costo = meses * current_app.config["PUNTOS_POR_MES_PREMIUM"]
    # Bloquea la fila: dos canjes simultáneos no pueden gastar los mismos puntos.
    billetera = consultar(
        "SELECT puntos, premium_hasta FROM billeteras WHERE cuenta_id = %s FOR UPDATE", (cuenta_id,), uno=True
    )
    if not billetera:
        raise ErrorNegocio("La cuenta no tiene billetera.", 404)
    if billetera["puntos"] < costo:
        raise ErrorNegocio(f"Puntos insuficientes: necesita {costo} y tiene {billetera['puntos']}.", 409)
    # Si ya es premium, los meses se suman a partir del vencimiento actual.
    base = max(date.today(), billetera["premium_hasta"] or date.today())
    nuevo_vencimiento = sumar_meses(base, meses)
    ejecutar(
        "UPDATE billeteras SET puntos = puntos - %s, premium_hasta = %s WHERE cuenta_id = %s",
        (costo, nuevo_vencimiento, cuenta_id),
    )
    ejecutar(
        "INSERT INTO movimientos_puntos (cuenta_id, tipo, puntos, referencia) VALUES (%s, 'canje', %s, %s)",
        (cuenta_id, -costo, f"premium:{meses}m"),
    )
    return {"puntos": billetera["puntos"] - costo, "premium_hasta": nuevo_vencimiento}
