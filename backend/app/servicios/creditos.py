"""Movimientos de créditos (saldo en billeteras + libro contable).

Garantías:
  * Atomicidad: el saldo y su asiento en `movimientos_credito` se escriben en la
    misma transacción que la operación de negocio que los originó.
  * Concurrencia: las billeteras involucradas se bloquean con SELECT ... FOR UPDATE,
    siempre en orden de id ascendente para evitar interbloqueos (deadlocks).
  * Nunca un saldo negativo: se valida aquí y además la columna es UNSIGNED.

Uso típico:
    saldos = bloquear(paciente_id, profesional_id)
    aplicar(paciente_id, -costo, "pago_consulta", saldos, ...)
    aplicar(profesional_id, +costo, "cobro_consulta", saldos, ...)
"""
from ..db import consultar, ejecutar
from ..errores import ErrorNegocio


def bloquear(*cuentas_ids: int) -> dict[int, int]:
    """Bloquea las billeteras indicadas y devuelve {cuenta_id: saldo_actual}."""
    ids = sorted(set(cuentas_ids))
    marcas = ", ".join(["%s"] * len(ids))  # solo marcas de posición: ningún dato va dentro del SQL
    filas = consultar(
        f"SELECT cuenta_id, saldo_creditos FROM billeteras WHERE cuenta_id IN ({marcas}) ORDER BY cuenta_id FOR UPDATE",
        tuple(ids),
    )
    saldos = {fila["cuenta_id"]: fila["saldo_creditos"] for fila in filas}
    if len(saldos) != len(ids):
        raise ErrorNegocio("Una de las cuentas no tiene billetera de créditos.", 404)
    return saldos


def aplicar(
    cuenta_id: int,
    monto: int,
    tipo: str,
    saldos: dict[int, int],
    contraparte_id: int | None = None,
    referencia: str | None = None,
    nota: str | None = None,
) -> int:
    """Suma (monto > 0) o resta (monto < 0) créditos y registra el asiento. Devuelve el saldo nuevo."""
    nuevo = saldos[cuenta_id] + monto
    if nuevo < 0:
        raise ErrorNegocio("Saldo de créditos insuficiente.", 409)
    ejecutar("UPDATE billeteras SET saldo_creditos = %s WHERE cuenta_id = %s", (nuevo, cuenta_id))
    ejecutar(
        "INSERT INTO movimientos_credito (cuenta_id, tipo, monto, saldo_posterior, contraparte_id, referencia, nota) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (cuenta_id, tipo, monto, nuevo, contraparte_id, referencia, nota),
    )
    saldos[cuenta_id] = nuevo
    return nuevo


def transferir(origen_id: int, destino_id: int, monto: int, nota: str | None) -> int:
    """Mueve créditos entre dos cuentas de forma atómica. Devuelve el saldo restante del origen."""
    if origen_id == destino_id:
        raise ErrorNegocio("No puede transferirse créditos a sí mismo.")
    saldos = bloquear(origen_id, destino_id)
    restante = aplicar(origen_id, -monto, "transferencia_enviada", saldos, destino_id, nota=nota)
    aplicar(destino_id, monto, "transferencia_recibida", saldos, origen_id, nota=nota)
    return restante


def saldo(cuenta_id: int) -> int:
    fila = consultar("SELECT saldo_creditos FROM billeteras WHERE cuenta_id = %s", (cuenta_id,), uno=True)
    return fila["saldo_creditos"] if fila else 0
