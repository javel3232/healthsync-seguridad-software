"""Lógica de negocio reutilizable por varias rutas (créditos, cuentas, referidos).

Las rutas se encargan de HTTP (leer la petición, validar, responder). Los
servicios se encargan de las reglas del negocio y de las operaciones que deben
ser atómicas. Ningún servicio hace commit: la ruta que los llama confirma la
transacción cuando todo salió bien.
"""
