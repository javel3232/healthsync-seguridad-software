"""Definición de las métricas de salud soportadas.

Los nombres de tipo son los esquemas de Open mHealth que entrega la API externa.
Cada tipo declara el campo donde viene el valor, su unidad y un rango de
plausibilidad: una lectura fuera de ese rango (por ejemplo 9999 bpm) se descarta
porque no puede ser real.
"""

TIPOS = {
    "heart-rate": {"campo": "heart_rate", "unidad": "beats/min", "etiqueta": "Frecuencia cardíaca", "min": 20, "max": 250},
    "step-count": {"campo": "step_count", "unidad": "steps", "etiqueta": "Pasos diarios", "min": 0, "max": 100000},
    "oxygen-saturation": {"campo": "oxygen_saturation", "unidad": "%", "etiqueta": "Oxígeno en sangre", "min": 50, "max": 100},
    "sleep-duration": {"campo": "sleep_duration", "unidad": "h", "etiqueta": "Horas de sueño", "min": 0, "max": 24},
}

OPERADORES = ("mayor", "menor")
