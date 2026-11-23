<script setup>
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import Mensaje from "@/components/Mensaje.vue";
import { api } from "@/api";
import { ESTADOS_CONSULTA, ETIQUETAS_METRICA, fechaHora, textoMetrica } from "@/formato";
import { sesion } from "@/sesion";

const route = useRoute();
const id = route.params.id;
const consulta = ref(null);
const metricas = ref(null);
const notas = ref({ diagnostico_resumido: "", notas_clinicas: "" });
const mensaje = ref("");
const error = ref("");

const esPaciente = computed(() => sesion.tieneRol("paciente"));
const esProfesional = computed(() => sesion.tieneRol("profesional"));
const puedeEscribirNotas = computed(() => esProfesional.value && ["en_curso", "completada"].includes(consulta.value?.estado));

async function cargar() {
  try {
    consulta.value = (await api(`/consultas/${id}`)).consulta;
    notas.value = {
      diagnostico_resumido: consulta.value.diagnostico_resumido ?? "",
      notas_clinicas: consulta.value.notas_clinicas ?? "",
    };
  } catch (e) {
    error.value = e.message;
  }
}

// Ejecuta una acción sobre la consulta, muestra el resultado y recarga el detalle.
async function accion(ruta, metodo = "POST", cuerpo = {}) {
  mensaje.value = error.value = "";
  try {
    mensaje.value = (await api(`/consultas/${id}${ruta}`, { metodo, cuerpo })).mensaje;
    await cargar();
  } catch (e) {
    error.value = e.message;
  }
}

const cancelar = () => accion("/cancelar");
const iniciar = () => accion("/iniciar");
const finalizar = () => accion("/finalizar");
const cambiarConsentimiento = (otorgado) => accion("/consentimiento", "PUT", { otorgado });
const guardarNotas = () => accion("/notas", "PUT", notas.value);

async function verMetricas() {
  mensaje.value = error.value = "";
  try {
    metricas.value = (await api(`/consultas/${id}/metricas?dias=7`)).metricas;
  } catch (e) {
    metricas.value = null;
    error.value = e.message;
  }
}

onMounted(cargar);
</script>

<template>
  <div class="col-lg-9" v-if="consulta">
    <RouterLink to="/consultas" class="small">&larr; Volver a mis consultas</RouterLink>
    <h1 class="h3 mt-2">Consulta #{{ consulta.id }}
      <span class="badge fs-6" :class="ESTADOS_CONSULTA[consulta.estado].clase">{{ ESTADOS_CONSULTA[consulta.estado].texto }}</span>
    </h1>

    <dl class="row">
      <dt class="col-sm-3">Fecha</dt><dd class="col-sm-9">{{ fechaHora(consulta.inicio) }} (30 min)</dd>
      <dt class="col-sm-3">Profesional</dt><dd class="col-sm-9">{{ consulta.profesional }}</dd>
      <dt class="col-sm-3">Paciente</dt><dd class="col-sm-9">{{ consulta.paciente }}</dd>
      <dt class="col-sm-3">Motivo</dt><dd class="col-sm-9">{{ consulta.motivo }}</dd>
      <dt class="col-sm-3">Costo</dt><dd class="col-sm-9">{{ consulta.costo_creditos }} créditos</dd>
      <dt class="col-sm-3">Métricas compartidas</dt>
      <dd class="col-sm-9">{{ consulta.consentimiento_metricas ? "Sí, el paciente lo autorizó" : "No autorizado" }}</dd>
    </dl>

    <Mensaje :texto="mensaje" tipo="success" />
    <Mensaje :texto="error" />

    <!-- Acciones del paciente -->
    <div v-if="esPaciente && ['confirmada', 'en_curso'].includes(consulta.estado)" class="card mb-3">
      <div class="card-body">
        <h2 class="h6">Compartir mis métricas</h2>
        <p class="small text-secondary">
          Si lo autoriza, el profesional podrá ver el historial de su wearable solo mientras la consulta esté en curso.
          Puede retirar la autorización en cualquier momento.
        </p>
        <button v-if="!consulta.consentimiento_metricas" class="btn btn-success btn-sm" @click="cambiarConsentimiento(true)">Autorizar</button>
        <button v-else class="btn btn-outline-danger btn-sm" @click="cambiarConsentimiento(false)">Retirar autorización</button>
      </div>
    </div>

    <div class="d-flex gap-2 mb-3">
      <button v-if="esProfesional && consulta.estado === 'confirmada'" class="btn btn-primary" @click="iniciar">Iniciar consulta</button>
      <button v-if="consulta.estado === 'confirmada'" class="btn btn-outline-danger" @click="cancelar">
        Cancelar{{ esPaciente ? " (se devuelven los créditos)" : "" }}
      </button>
      <button v-if="esProfesional && consulta.estado === 'en_curso'" class="btn btn-success" @click="finalizar">Finalizar consulta</button>
    </div>

    <!-- Métricas del paciente (profesional, consulta en curso, con consentimiento) -->
    <div v-if="esProfesional && consulta.estado === 'en_curso'" class="card mb-3">
      <div class="card-body">
        <h2 class="h6">Métricas del paciente (últimos 7 días)</h2>
        <button class="btn btn-outline-dark btn-sm" @click="verMetricas">Ver métricas</button>
        <div v-if="metricas" class="table-responsive mt-3" style="max-height: 280px; overflow: auto">
          <table class="table table-sm">
            <thead><tr><th>Métrica</th><th>Valor</th><th>Fecha</th></tr></thead>
            <tbody>
              <tr v-for="(m, i) in metricas" :key="i">
                <td>{{ ETIQUETAS_METRICA[m.tipo] }}</td><td>{{ textoMetrica(m.tipo, m.valor) }}</td><td>{{ fechaHora(m.medido_en) }}</td>
              </tr>
            </tbody>
          </table>
          <p v-if="!metricas.length" class="text-secondary small">El paciente no tiene métricas en ese periodo.</p>
        </div>
      </div>
    </div>

    <!-- Notas clínicas: las escribe el profesional; las ven ambos -->
    <div class="card" v-if="puedeEscribirNotas || consulta.diagnostico_resumido">
      <div class="card-body">
        <h2 class="h6">Diagnóstico y notas clínicas</h2>
        <form v-if="puedeEscribirNotas" @submit.prevent="guardarNotas">
          <div class="mb-2">
            <label class="form-label small" for="diag">Diagnóstico resumido</label>
            <input id="diag" v-model="notas.diagnostico_resumido" class="form-control" minlength="3" maxlength="255" required />
          </div>
          <div class="mb-2">
            <label class="form-label small" for="notas">Notas clínicas</label>
            <textarea id="notas" v-model="notas.notas_clinicas" class="form-control" rows="5" maxlength="5000"></textarea>
          </div>
          <button class="btn btn-dark btn-sm">Guardar notas</button>
        </form>
        <template v-else>
          <p class="mb-1"><strong>Diagnóstico:</strong> {{ consulta.diagnostico_resumido }}</p>
          <p class="mb-0" style="white-space: pre-wrap">{{ consulta.notas_clinicas || "Sin notas." }}</p>
        </template>
      </div>
    </div>
  </div>
  <Mensaje v-else :texto="error" />
</template>
