"""Simulador de las APIs externas de los casos.

- /openrouter/api/v1/...  imita la forma de la API de OpenRouter (compatible con OpenAI).
- /openmhealth/v1/...     entrega datos de wearables con una estructura inspirada en
                          los esquemas de Open mHealth (no es una réplica exacta).

Sirve para desarrollar y auditar sin llaves reales ni costos. Los datos son
deterministas: el mismo usuario y la misma métrica siempre producen la misma serie.
Algunas lecturas salen deliberadamente fuera de rango para poder probar alertas.
"""
import hashlib
import random
import time
import uuid
from datetime import datetime, timedelta, timezone

from flask import Flask, jsonify, request

app = Flask(__name__)

MODELOS = {
    "simulado/eco-1": {"name": "Eco 1 (simulado)", "prompt": "0.000001", "completion": "0.000002"},
    "simulado/resumen-1": {"name": "Resumen 1 (simulado)", "prompt": "0.000003", "completion": "0.000006"},
    "simulado/lento-1": {"name": "Lento 1 (simulado, tarda 5 s)", "prompt": "0.000001", "completion": "0.000001"},
}

METRICAS = {
    # esquema: (campo del cuerpo, unidad, mínimo normal, máximo normal, valor atípico)
    "heart-rate": ("heart_rate", "beats/min", 58, 105, 138),
    "step-count": ("step_count", "steps", 2000, 11000, 0),
    "oxygen-saturation": ("oxygen_saturation", "%", 94, 99, 86),
    "sleep-duration": ("sleep_duration", "h", 5, 9, 2),
}


def error(codigo: int, mensaje: str):
    return jsonify(error={"code": codigo, "message": mensaje}), codigo


@app.before_request
def exigir_llave():
    if request.path == "/salud":
        return None
    encabezado = request.headers.get("Authorization", "")
    if not encabezado.startswith("Bearer ") or len(encabezado) <= len("Bearer "):
        return error(401, "Falta el encabezado Authorization: Bearer <llave>.")
    return None


@app.get("/salud")
def salud():
    return jsonify(estado="ok")


# ----------------------------------------------------------------- OpenRouter
@app.get("/openrouter/api/v1/models")
def modelos():
    return jsonify(
        data=[
            {"id": clave, "name": datos["name"], "pricing": {"prompt": datos["prompt"], "completion": datos["completion"]}}
            for clave, datos in MODELOS.items()
        ]
    )


@app.post("/openrouter/api/v1/chat/completions")
def chat():
    cuerpo = request.get_json(silent=True) or {}
    modelo = cuerpo.get("model")
    mensajes = cuerpo.get("messages")
    if modelo not in MODELOS:
        return error(400, f"Modelo desconocido: {modelo!r}. Consulte /models.")
    if not isinstance(mensajes, list) or not mensajes:
        return error(400, "'messages' debe ser una lista no vacía.")
    if modelo == "simulado/lento-1":
        time.sleep(5)

    ultimo = str(mensajes[-1].get("content", "")) if isinstance(mensajes[-1], dict) else ""
    texto_entrada = " ".join(str(m.get("content", "")) for m in mensajes if isinstance(m, dict))
    contenido = f"[Respuesta simulada de {modelo}] Recibí: {ultimo[:200]}"
    tokens_entrada = max(1, len(texto_entrada.split()))
    tokens_salida = len(contenido.split())
    return jsonify(
        id=f"gen-sim-{uuid.uuid4()}",
        object="chat.completion",
        created=int(time.time()),
        model=modelo,
        choices=[{"index": 0, "message": {"role": "assistant", "content": contenido}, "finish_reason": "stop"}],
        usage={"prompt_tokens": tokens_entrada, "completion_tokens": tokens_salida, "total_tokens": tokens_entrada + tokens_salida},
    )


# ---------------------------------------------------------------- Open mHealth
@app.get("/openmhealth/v1/dataPoints")
def puntos_de_datos():
    esquema = request.args.get("schema", "")
    usuario = request.args.get("usuario", "")
    try:
        dias = min(max(int(request.args.get("dias", "1")), 1), 30)
    except ValueError:
        return error(400, "'dias' debe ser un entero entre 1 y 30.")
    if esquema not in METRICAS:
        return error(400, f"Esquema no soportado. Use uno de: {', '.join(METRICAS)}.")
    if not usuario or len(usuario) > 64:
        return error(400, "Parámetro 'usuario' obligatorio.")

    campo, unidad, minimo, maximo, atipico = METRICAS[esquema]
    semilla = int(hashlib.sha256(f"{usuario}:{esquema}".encode()).hexdigest()[:16], 16)
    azar = random.Random(semilla)
    por_dia = 24 if esquema in ("heart-rate", "oxygen-saturation") else 1
    ahora = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)

    puntos = []
    for i in range(dias * por_dia):
        momento = ahora - timedelta(hours=i) if por_dia == 24 else ahora - timedelta(days=i)
        valor = atipico if azar.random() < 0.05 else azar.randint(minimo, maximo)
        puntos.append(
            {
                "header": {
                    "id": str(uuid.UUID(int=azar.getrandbits(128))),
                    "creation_date_time": momento.isoformat(),
                    "schema_id": {"namespace": "omh", "name": esquema, "version": "simulado"},
                },
                "body": {campo: {"value": valor, "unit": unidad}, "effective_time_frame": {"date_time": momento.isoformat()}},
            }
        )
    return jsonify(puntos)
