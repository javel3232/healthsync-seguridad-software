<script setup>
import { computed, onMounted, ref } from "vue";
import Mensaje from "@/components/Mensaje.vue";
import { api } from "@/api";
import { ETIQUETAS_METRICA, fechaHora, textoMetrica } from "@/formato";

const PROVEEDORES = ["Fitbit", "Garmin", "Apple Watch", "Xiaomi", "Samsung", "Otro"];

const dispositivos = ref([]);
const ultimas = ref({});
const metricas = ref([]);
const nuevo = ref({ nombre: "", proveedor: "Garmin" });
const lectura = ref({ tipo: "heart-rate", valor: "" });
const filtro = ref({ tipo: "", dias: 7 });
const diasSync = ref(7); // días que se importan al sincronizar
const mensaje = ref("");
const error = ref("");
const sincronizando = ref(null);

const tipos = computed(() => Object.keys(ETIQUETAS_METRICA));

async function cargarMetricas() {
  const params = new URLSearchParams({ dias: filtro.value.dias });
  if (filtro.value.tipo) params.set("tipo", filtro.value.tipo);
  metricas.value = (await api(`/wearables/metricas?${params}`)).metricas;
  ultimas.value = (await api("/wearables/resumen")).ultimas;
}

async function cargar() {
  try {
    dispositivos.value = (await api("/wearables/dispositivos")).dispositivos;
    await cargarMetricas();
  } catch (e) {
    error.value = e.message;
  }
}

// Ejecuta una operación, muestra su mensaje y refresca los datos.
async function ejecutar(operacion) {
  mensaje.value = error.value = "";
  try {
    mensaje.value = await operacion();
    await cargar();
  } catch (e) {
    error.value = e.message;
  }
}

const vincular = () =>
  ejecutar(async () => {
    const datos = await api("/wearables/dispositivos", { metodo: "POST", cuerpo: nuevo.value });
    nuevo.value.nombre = "";
    return datos.mensaje;
  });

const desvincular = (d) => ejecutar(async () => (await api(`/wearables/dispositivos/${d.id}`, { metodo: "DELETE" })).mensaje);

async function sincronizar(d) {
  sincronizando.value = d.id;
  await ejecutar(async () => {
    const r = await api(`/wearables/dispositivos/${d.id}/sincronizar`, { metodo: "POST", cuerpo: { dias: Number(diasSync.value) } });
    return `${r.mensaje} Lecturas nuevas: ${r.nuevas} (recibidas ${r.recibidas}, descartadas ${r.descartadas}).`;
  });
  sincronizando.value = null;
}

const registrarLectura = () =>
  ejecutar(async () => {
    const datos = await api("/wearables/metricas", { metodo: "POST", cuerpo: { tipo: lectura.value.tipo, valor: Number(lectura.value.valor) } });
    lectura.value.valor = "";
    return datos.mensaje;
  });

onMounted(cargar);
</script>

<template>
  <div class="col-lg-11">
    <h1 class="h3 mb-3">Mis wearables</h1>
    <Mensaje :texto="mensaje" tipo="success" />
    <Mensaje :texto="error" />

    <!-- Última lectura de cada métrica -->
    <div class="row g-3 mb-4">
      <div class="col-6 col-md-3" v-for="tipo in tipos" :key="tipo">
        <div class="card h-100"><div class="card-body py-2">
          <div class="small text-secondary">{{ ETIQUETAS_METRICA[tipo] }}</div>
          <div class="fs-4" v-if="ultimas[tipo]">{{ textoMetrica(tipo, ultimas[tipo].valor) }}</div>
          <div class="fs-6 text-secondary" v-else>Sin datos</div>
          <div class="small text-secondary" v-if="ultimas[tipo]">{{ fechaHora(ultimas[tipo].medido_en) }}</div>
        </div></div>
      </div>
    </div>

    <div class="row g-4">
      <div class="col-lg-6">
        <h2 class="h5">Dispositivos</h2>
        <ul class="list-group mb-3">
          <li v-for="d in dispositivos" :key="d.id" class="list-group-item">
            <div class="d-flex justify-content-between">
              <div>
                <strong>{{ d.nombre }}</strong> <span class="badge text-bg-secondary">{{ d.proveedor }}</span>
                <div class="small text-secondary">Última sincronización: {{ fechaHora(d.ultima_sincronizacion) }}</div>
              </div>
              <button class="btn btn-link btn-sm text-danger" @click="desvincular(d)">Desvincular</button>
            </div>
            <div class="d-flex gap-2 mt-2 align-items-center">
              <select v-model="diasSync" class="form-select form-select-sm w-auto" aria-label="Días a sincronizar">
                <option v-for="n in [1, 3, 7, 14, 30]" :key="n" :value="n">Últimos {{ n }} día(s)</option>
              </select>
              <button class="btn btn-dark btn-sm" :disabled="sincronizando === d.id" @click="sincronizar(d)">
                {{ sincronizando === d.id ? "Sincronizando…" : "Sincronizar ahora" }}
              </button>
            </div>
          </li>
          <li v-if="!dispositivos.length" class="list-group-item text-secondary">No tiene dispositivos vinculados.</li>
        </ul>

        <form class="row g-2" @submit.prevent="vincular">
          <div class="col-6"><input v-model="nuevo.nombre" class="form-control form-control-sm" placeholder="Nombre del dispositivo" minlength="2" maxlength="80" required /></div>
          <div class="col-4">
            <select v-model="nuevo.proveedor" class="form-select form-select-sm" aria-label="Proveedor">
              <option v-for="p in PROVEEDORES" :key="p">{{ p }}</option>
            </select>
          </div>
          <div class="col-2"><button class="btn btn-outline-dark btn-sm w-100">Vincular</button></div>
        </form>
      </div>

      <div class="col-lg-6">
        <h2 class="h5">Registrar una lectura manual</h2>
        <p class="small text-secondary">Útil si no tiene dispositivo o para probar sus alertas.</p>
        <form class="row g-2" @submit.prevent="registrarLectura">
          <div class="col-6">
            <select v-model="lectura.tipo" class="form-select form-select-sm" aria-label="Métrica">
              <option v-for="t in tipos" :key="t" :value="t">{{ ETIQUETAS_METRICA[t] }}</option>
            </select>
          </div>
          <div class="col-4"><input v-model="lectura.valor" type="number" step="0.1" class="form-control form-control-sm" placeholder="Valor" required /></div>
          <div class="col-2"><button class="btn btn-outline-dark btn-sm w-100">Guardar</button></div>
        </form>
      </div>
    </div>

    <h2 class="h5 mt-4">Historial de métricas</h2>
    <div class="d-flex gap-2 mb-2">
      <select v-model="filtro.tipo" class="form-select form-select-sm w-auto" aria-label="Filtrar por métrica" @change="cargarMetricas">
        <option value="">Todas las métricas</option>
        <option v-for="t in tipos" :key="t" :value="t">{{ ETIQUETAS_METRICA[t] }}</option>
      </select>
      <select v-model="filtro.dias" class="form-select form-select-sm w-auto" aria-label="Periodo" @change="cargarMetricas">
        <option v-for="n in [1, 3, 7, 14, 30, 90]" :key="n" :value="n">Últimos {{ n }} día(s)</option>
      </select>
    </div>
    <div class="table-responsive" style="max-height: 360px; overflow: auto">
      <table class="table table-sm table-striped">
        <thead><tr><th>Métrica</th><th>Valor</th><th>Fecha</th><th>Origen</th></tr></thead>
        <tbody>
          <tr v-for="m in metricas" :key="m.id">
            <td>{{ ETIQUETAS_METRICA[m.tipo] }}</td>
            <td>{{ textoMetrica(m.tipo, m.valor) }}</td>
            <td>{{ fechaHora(m.medido_en) }}</td>
            <td>{{ m.fuente === "wearable" ? "Dispositivo" : "Manual" }}</td>
          </tr>
          <tr v-if="!metricas.length"><td colspan="4" class="text-secondary">Sin métricas en este periodo. Sincronice un dispositivo.</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
