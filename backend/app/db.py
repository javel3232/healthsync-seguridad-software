"""Acceso a la base de datos.

Todas las consultas usan parámetros (%s). Nunca se arma SQL concatenando datos
que vienen de una petición.

    consultar("SELECT * FROM cuentas WHERE id = %s", (id_cuenta,), uno=True)
    ejecutar("UPDATE cuentas SET nombre = %s WHERE id = %s", (nombre, id_cuenta))
    confirmar()

La conexión es una por petición y trabaja con transacciones (autocommit apagado)
en nivel READ COMMITTED. Si la petición termina sin confirmar, se revierte.
Para operaciones sobre dinero use `FOR UPDATE` en la consulta que lee el saldo.
"""
import mysql.connector
from flask import current_app, g


def conexion():
    """Devuelve la conexión de la petición actual, creándola si no existe."""
    if "db" not in g:
        g.db = mysql.connector.connect(**current_app.config["DB"], autocommit=False)
        cursor = g.db.cursor()
        # Evita leer una "foto" vieja de los datos dentro de una transacción larga.
        cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED")
        cursor.execute("SET time_zone = '+00:00'")
        cursor.close()
    return g.db


def cerrar(_excepcion=None):
    """Se ejecuta al terminar cada petición: revierte lo no confirmado y cierra."""
    db = g.pop("db", None)
    if db is not None:
        try:
            db.rollback()
        finally:
            db.close()


def consultar(sql: str, parametros: tuple = (), uno: bool = False):
    """SELECT. Devuelve una fila (dict) si `uno`, o una lista de filas."""
    cursor = conexion().cursor(dictionary=True)
    try:
        cursor.execute(sql, parametros)
        return cursor.fetchone() if uno else cursor.fetchall()
    finally:
        cursor.close()


def ejecutar(sql: str, parametros: tuple = ()) -> int:
    """INSERT/UPDATE/DELETE. Devuelve el id insertado (si aplica)."""
    cursor = conexion().cursor()
    try:
        cursor.execute(sql, parametros)
        return cursor.lastrowid
    finally:
        cursor.close()


def actualizar(sql: str, parametros: tuple = ()) -> int:
    """Como `ejecutar`, pero devuelve el número de filas afectadas."""
    cursor = conexion().cursor()
    try:
        cursor.execute(sql, parametros)
        return cursor.rowcount
    finally:
        cursor.close()


def ejecutar_muchos(sql: str, filas: list[tuple]) -> int:
    """Inserción por lotes. Devuelve el número de filas afectadas."""
    if not filas:
        return 0
    cursor = conexion().cursor()
    try:
        cursor.executemany(sql, filas)
        return cursor.rowcount
    finally:
        cursor.close()


def confirmar():
    conexion().commit()


def revertir():
    conexion().rollback()
