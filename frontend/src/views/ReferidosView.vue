<script setup>
import { onMounted, ref } from "vue";
import Mensaje from "@/components/Mensaje.vue";
import { api } from "@/api";
import { fecha, fechaHora } from "@/formato";

const datos = ref(null);
const meses = ref(1);
const mensaje = ref("");
const error = ref("");

const ESTADOS = { pendiente: "Pendiente de validación", completado: "Completado", cancelado: "Cancelado" };

async function cargar() {
  try {
    datos.value = await api("/referidos");
  } catch (e) {
    error.value = e.message;
  }
}

async function canjear() {
  mensaje.value = error.value = "";
  try {
    mensaje.value = (await api("/referidos/canjear", { metodo: "POST", cuerpo: { meses: Number(meses.value) } })).mensaje;
    await cargar();
  } catch (e) {
    error.value = e.message;
  }
}

onMounted(cargar);
</script>

<template>
  <div class="col-lg-9" v-if="datos">
    <h1 class="h3 mb-3">Programa de referidos</h1>

    <div class="row g-3 mb-4">
      <div class="col-md-4"><div class="card h-100"><div class="card-body">
        <div class="small text-secondary">Su código</div>
        <div class="fs-4 font-monospace">{{ datos.codigo }}</div>
        <div class="small text-secondary">Gane {{ datos.puntos_por_referido }} puntos por cada persona que se registre con él y active su cuenta.</div>
      </div></div></div>
      <div class="col-md-4"><div class="card h-100"><div class="card-body">
        <div class="small text-secondary">Sus puntos</div>
        <div class="fs-4">{{ datos.puntos }}</div>
      </div></div></div>
      <div class="col-md-4"><div class="card h-100"><div class="card-body">
        <div class="small text-secondary">Premium hasta</div>
        <div class="fs-5">{{ datos.premium_hasta ? fecha(datos.premium_hasta) : "Sin premium" }}</div>
      </div></div></div>
    </div>

    <h2 class="h5">Canjear puntos</h2>
    <p class="small text-secondary">Cada mes de suscripción premium cuesta {{ datos.puntos_por_mes }} puntos.</p>
    <form class="d-flex gap-2 align-items-center mb-2" @submit.prevent="canjear">
      <select v-model="meses" class="form-select w-auto" aria-label="Meses">
        <option v-for="n in [1, 2, 3, 6, 12]" :key="n" :value="n">{{ n }} mes(es) — {{ n * datos.puntos_por_mes }} puntos</option>
      </select>
      <button class="btn btn-dark">Canjear</button>
    </form>
    <Mensaje :texto="mensaje" tipo="success" />
    <Mensaje :texto="error" />

    <h2 class="h5 mt-4">Mis referidos</h2>
    <table class="table table-sm">
      <thead><tr><th>Persona</th><th>Estado</th><th class="text-end">Puntos</th><th>Registro</th></tr></thead>
      <tbody>
        <tr v-for="r in datos.referidos" :key="r.id">
          <td>{{ r.nombre }}</td><td>{{ ESTADOS[r.estado] }}</td><td class="text-end">{{ r.puntos }}</td><td>{{ fechaHora(r.creado_en) }}</td>
        </tr>
        <tr v-if="!datos.referidos.length"><td colspan="4" class="text-secondary">Aún no tiene referidos.</td></tr>
      </tbody>
    </table>
  </div>
  <Mensaje v-else :texto="error" />
</template>
