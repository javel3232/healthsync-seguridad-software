<script setup>
import { computed, onMounted, ref } from "vue";
import Mensaje from "@/components/Mensaje.vue";
import { api } from "@/api";
import { ESTADOS_CONSULTA, fechaHora } from "@/formato";
import { sesion } from "@/sesion";

const consultas = ref([]);
const filtro = ref("");
const error = ref("");
const cargando = ref(true);

const esPaciente = computed(() => sesion.tieneRol("paciente"));

async function cargar() {
  error.value = "";
  cargando.value = true;
  try {
    consultas.value = (await api(`/consultas${filtro.value ? `?estado=${filtro.value}` : ""}`)).consultas;
  } catch (e) {
    error.value = e.message;
  } finally {
    cargando.value = false;
  }
}

onMounted(cargar);
</script>

<template>
  <div class="col-lg-11">
    <div class="d-flex justify-content-between align-items-center mb-3">
      <h1 class="h3 mb-0">Mis consultas</h1>
      <RouterLink v-if="esPaciente" class="btn btn-dark btn-sm" to="/directorio">Agendar una consulta</RouterLink>
    </div>

    <div class="mb-3 d-flex gap-2 align-items-center">
      <label class="form-label mb-0 small" for="filtro">Estado:</label>
      <select id="filtro" v-model="filtro" class="form-select form-select-sm w-auto" @change="cargar">
        <option value="">Todas</option>
        <option v-for="(datos, clave) in ESTADOS_CONSULTA" :key="clave" :value="clave">{{ datos.texto }}</option>
      </select>
    </div>

    <Mensaje :texto="error" />
    <p v-if="!cargando && !consultas.length" class="text-secondary">No tiene consultas.</p>

    <div class="table-responsive" v-if="consultas.length">
      <table class="table table-hover align-middle">
        <thead>
          <tr>
            <th>Fecha</th>
            <th>{{ esPaciente ? "Profesional" : "Paciente" }}</th>
            <th>Motivo</th>
            <th>Diagnóstico</th>
            <th class="text-end">Costo</th>
            <th>Estado</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="c in consultas" :key="c.id">
            <td class="text-nowrap">{{ fechaHora(c.inicio) }}</td>
            <td>{{ esPaciente ? c.profesional : c.paciente }}</td>
            <td>{{ c.motivo }}</td>
            <td>{{ c.diagnostico_resumido || "—" }}</td>
            <td class="text-end">{{ c.costo_creditos }}</td>
            <td><span class="badge" :class="ESTADOS_CONSULTA[c.estado].clase">{{ ESTADOS_CONSULTA[c.estado].texto }}</span></td>
            <td><RouterLink class="btn btn-outline-dark btn-sm" :to="`/consultas/${c.id}`">Abrir</RouterLink></td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
