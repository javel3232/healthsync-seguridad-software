// Funciones de presentación: fechas, etiquetas y colores de estado.
// Las fechas llegan del servidor en UTC (ISO 8601) y se muestran en la hora local del navegador.

export function fechaHora(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("es-CO", { dateStyle: "medium", timeStyle: "short" });
}

export function fecha(iso) {
  if (!iso) return "—";
  // Las fechas sin hora (AAAA-MM-DD) se interpretan como locales para no desplazar el día.
  const [a, m, d] = iso.slice(0, 10).split("-").map(Number);
  return new Date(a, m - 1, d).toLocaleDateString("es-CO", { dateStyle: "medium" });
}

// Valor de un <input type="datetime-local"> (hora local) -> ISO 8601 en UTC.
export function localAIso(valor) {
  return new Date(valor).toISOString();
}

export const ETIQUETAS_METRICA = {
  "heart-rate": "Frecuencia cardíaca",
  "step-count": "Pasos diarios",
  "oxygen-saturation": "Oxígeno en sangre",
  "sleep-duration": "Horas de sueño",
};

export const UNIDADES_METRICA = {
  "heart-rate": "lpm",
  "step-count": "pasos",
  "oxygen-saturation": "%",
  "sleep-duration": "h",
};

export function textoMetrica(tipo, valor) {
  return `${Number(valor)} ${UNIDADES_METRICA[tipo] ?? ""}`.trim();
}

export const ESTADOS_CONSULTA = {
  confirmada: { texto: "Confirmada", clase: "text-bg-primary" },
  en_curso: { texto: "En curso", clase: "text-bg-warning" },
  completada: { texto: "Completada", clase: "text-bg-success" },
  cancelada: { texto: "Cancelada", clase: "text-bg-secondary" },
};

export const TIPOS_MOVIMIENTO = {
  bono: "Bono de bienvenida",
  transferencia_enviada: "Transferencia enviada",
  transferencia_recibida: "Transferencia recibida",
  pago_consulta: "Pago de consulta",
  cobro_consulta: "Cobro de consulta",
  reembolso_consulta: "Reembolso de consulta",
};

export const ROLES = { paciente: "Paciente", profesional: "Profesional de salud", admin: "Administrador" };
