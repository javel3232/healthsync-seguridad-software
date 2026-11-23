<script setup>
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import Mensaje from "@/components/Mensaje.vue";
import { api } from "@/api";
import { localAIso } from "@/formato";
import { sesion } from "@/sesion";

const router = useRouter();
const termino = ref("");
const resultados = ref([]);
const error = ref("");
const saldo = ref(null);

// Formulario de agendamiento (solo pacientes): se abre bajo el profesional elegido.
const agendando = ref(null);
const cita = ref({ inicio: "", motivo: "" });
const errorCita = ref("");
const enviando = ref(false);

async function buscar() {
  error.value = "";
  try {
    resultados.value = (await api(`/directorio?q=${encodeURIComponent(termino.value)}`)).resultados;
  } catch (e) {
    error.value = e.message;
  }
}

onMounted(async () => {
  await buscar();
  if (sesion.tieneRol("paciente")) {
    try {
      saldo.value = (await api("/creditos")).saldo;
    } catch {
      /* el saldo es informativo */
    }
  }
});

function abrir(profesional) {
  agendando.value = profesional.id;
  cita.value = { inicio: "", motivo: "" };
  errorCita.value = "";
}

async function agendar(profesional) {
  errorCita.value = "";
  enviando.value = true;
  try {
    const datos = await api("/consultas", {
      metodo: "POST",
      cuerpo: { profesional_id: profesional.id, inicio: localAIso(cita.value.inicio), motivo: cita.value.motivo },
    });
    router.push({ name: "consulta", params: { id: datos.id } });
  } catch (e) {
    errorCita.value = e.message;
  } finally {
    enviando.value = false;
  }
}
</script>

<template>
  <div class="col-lg-9">
    <h1 class="h3 mb-3">Directorio de profesionales</h1>
    <p v-if="saldo !== null" class="text-secondary">Su saldo: <strong>{{ saldo }}</strong> créditos</p>
    <form class="d-flex gap-2 mb-3" @submit.prevent="buscar">
      <input v-model="termino" class="form-control" placeholder="Buscar por nombre o especialidad" maxlength="60" />
      <button class="btn btn-dark">Buscar</button>
    </form>
    <Mensaje :texto="error" />
    <p v-if="!resultados.length && !error" class="text-secondary">No se encontraron profesionales.</p>

    <div v-for="profesional in resultados" :key="profesional.id" class="card mb-3">
      <div class="card-body">
        <div class="d-flex justify-content-between align-items-start">
          <div>
            <h2 class="h6 mb-0">{{ profesional.nombre }}</h2>
            <span class="badge text-bg-info">{{ profesional.especialidad }}</span>
          </div>
          <div class="text-end">
            <div class="fw-semibold">{{ profesional.tarifa_creditos }} créditos</div>
            <button v-if="sesion.tieneRol('paciente')" class="btn btn-sm btn-dark mt-1" @click="abrir(profesional)">Agendar</button>
          </div>
        </div>
        <p class="small text-secondary mt-2 mb-0" v-if="profesional.descripcion">{{ profesional.descripcion }}</p>

        <form v-if="agendando === profesional.id" class="border-top mt-3 pt-3" @submit.prevent="agendar(profesional)">
          <div class="row g-2">
            <div class="col-md-5">
              <label class="form-label small" :for="`inicio-${profesional.id}`">Fecha y hora (duración 30 min)</label>
              <input :id="`inicio-${profesional.id}`" v-model="cita.inicio" type="datetime-local" class="form-control" required />
            </div>
            <div class="col-md-7">
              <label class="form-label small" :for="`motivo-${profesional.id}`">Motivo de la consulta</label>
              <input :id="`motivo-${profesional.id}`" v-model="cita.motivo" class="form-control" minlength="5" maxlength="300" required />
            </div>
          </div>
          <Mensaje :texto="errorCita" class="mt-2" />
          <div class="mt-2 d-flex gap-2">
            <button class="btn btn-success btn-sm" :disabled="enviando">Confirmar y pagar {{ profesional.tarifa_creditos }} créditos</button>
            <button type="button" class="btn btn-link btn-sm" @click="agendando = null">Cancelar</button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>
