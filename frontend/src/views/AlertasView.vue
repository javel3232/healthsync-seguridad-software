<script setup>
import { computed, onMounted, ref } from "vue";
import Mensaje from "@/components/Mensaje.vue";
import { api } from "@/api";
import { ETIQUETAS_METRICA, fechaHora, UNIDADES_METRICA } from "@/formato";
import { sesion } from "@/sesion";

const esPaciente = computed(() => sesion.tieneRol("paciente"));
const alertas = ref([]);
const disparos = ref([]);
const profesionales = ref([]);
const nueva = ref({ tipo_metrica: "heart-rate", operador: "mayor", umbral: "", notificar_profesional: false, profesional_id: "" });
const mensaje = ref("");
const error = ref("");

const tipos = Object.keys(ETIQUETAS_METRICA);

function describir(a) {
  const verbo = a.operador === "mayor" ? "supera" : "cae por debajo de";
  return `${ETIQUETAS_METRICA[a.tipo_metrica]} ${verbo} ${a.umbral} ${UNIDADES_METRICA[a.tipo_metrica]}`;
}

async function cargar() {
  try {
    if (esPaciente.value) {
      alertas.value = (await api("/alertas")).alertas;
      disparos.value = (await api("/alertas/disparos")).disparos;
      profesionales.value = (await api("/directorio")).resultados;
    } else {
      disparos.value = (await api("/alertas/recibidas")).disparos;
    }
  } catch (e) {
    error.value = e.message;
  }
}

async function ejecutar(operacion) {
  mensaje.value = error.value = "";
  try {
    mensaje.value = await operacion();
    await cargar();
  } catch (e) {
    error.value = e.message;
  }
}

const crear = () =>
  ejecutar(async () => {
    const n = nueva.value;
    const cuerpo = {
      tipo_metrica: n.tipo_metrica,
      operador: n.operador,
      umbral: Number(n.umbral),
      notificar_profesional: n.notificar_profesional,
    };
    if (n.notificar_profesional) cuerpo.profesional_id = Number(n.profesional_id);
    const r = await api("/alertas", { metodo: "POST", cuerpo });
    nueva.value.umbral = "";
    return r.mensaje;
  });

const alternar = (a) => ejecutar(async () => (await api(`/alertas/${a.id}`, { metodo: "PUT", cuerpo: { activa: !a.activa } })).mensaje);
const eliminar = (a) => ejecutar(async () => (await api(`/alertas/${a.id}`, { metodo: "DELETE" })).mensaje);

onMounted(cargar);
</script>

<template>
  <div class="col-lg-10">
    <h1 class="h3 mb-3">{{ esPaciente ? "Mis alertas de salud" : "Alertas de mis pacientes" }}</h1>
    <Mensaje :texto="mensaje" tipo="success" />
    <Mensaje :texto="error" />

    <template v-if="esPaciente">
      <p class="text-secondary small">
        Un monitor automático revisa su lectura más reciente cada segundo. Si supera un umbral, recibirá un correo.
      </p>
      <form class="card card-body mb-4" @submit.prevent="crear">
        <h2 class="h6">Nueva alerta</h2>
        <div class="row g-2">
          <div class="col-md-4">
            <select v-model="nueva.tipo_metrica" class="form-select" aria-label="Métrica">
              <option v-for="t in tipos" :key="t" :value="t">{{ ETIQUETAS_METRICA[t] }}</option>
            </select>
          </div>
          <div class="col-md-3">
            <select v-model="nueva.operador" class="form-select" aria-label="Condición">
              <option value="mayor">Es mayor que</option>
              <option value="menor">Es menor que</option>
            </select>
          </div>
          <div class="col-md-3"><input v-model="nueva.umbral" type="number" step="0.1" class="form-control" placeholder="Umbral" required /></div>
          <div class="col-md-2"><button class="btn btn-dark w-100">Crear</button></div>
        </div>
        <div class="form-check mt-3">
          <input id="aviso" v-model="nueva.notificar_profesional" class="form-check-input" type="checkbox" />
          <label class="form-check-label" for="aviso">Autorizo avisar también a un profesional de salud</label>
        </div>
        <select v-if="nueva.notificar_profesional" v-model="nueva.profesional_id" class="form-select mt-2" aria-label="Profesional" required>
          <option value="" disabled>Elija un profesional</option>
          <option v-for="p in profesionales" :key="p.id" :value="p.id">{{ p.nombre }} — {{ p.especialidad }}</option>
        </select>
      </form>

      <h2 class="h5">Alertas configuradas</h2>
      <ul class="list-group mb-4">
        <li v-for="a in alertas" :key="a.id" class="list-group-item d-flex justify-content-between align-items-center">
          <div>
            <span :class="{ 'text-decoration-line-through text-secondary': !a.activa }">{{ describir(a) }}</span>
            <div class="small text-secondary" v-if="a.notificar_profesional">También se avisa a {{ a.profesional }}</div>
          </div>
          <div class="d-flex gap-2">
            <button class="btn btn-outline-secondary btn-sm" @click="alternar(a)">{{ a.activa ? "Pausar" : "Activar" }}</button>
            <button class="btn btn-outline-danger btn-sm" @click="eliminar(a)">Eliminar</button>
          </div>
        </li>
        <li v-if="!alertas.length" class="list-group-item text-secondary">No tiene alertas configuradas.</li>
      </ul>
    </template>

    <h2 class="h5">{{ esPaciente ? "Alertas activadas" : "Alertas recibidas" }}</h2>
    <div class="table-responsive">
      <table class="table table-sm">
        <thead>
          <tr><th>Cuándo</th><th v-if="!esPaciente">Paciente</th><th>Condición</th><th>Lectura</th><th v-if="esPaciente">Avisó a profesional</th></tr>
        </thead>
        <tbody>
          <tr v-for="d in disparos" :key="d.id">
            <td class="text-nowrap">{{ fechaHora(d.disparada_en) }}</td>
            <td v-if="!esPaciente">{{ d.paciente }}</td>
            <td>{{ describir(d) }}</td>
            <td><strong>{{ d.valor }}</strong> {{ UNIDADES_METRICA[d.tipo_metrica] }}</td>
            <td v-if="esPaciente">{{ d.profesional ? (d.correo_profesional ? d.profesional : `${d.profesional} (correo no enviado)`) : "No" }}</td>
          </tr>
          <tr v-if="!disparos.length"><td colspan="5" class="text-secondary">Ninguna alerta se ha activado todavía.</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
