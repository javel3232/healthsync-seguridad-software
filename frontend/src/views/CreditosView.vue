<script setup>
import { onMounted, ref } from "vue";
import Mensaje from "@/components/Mensaje.vue";
import { api } from "@/api";
import { fechaHora, TIPOS_MOVIMIENTO } from "@/formato";

const saldo = ref(0);
const maximo = ref(0);
const movimientos = ref([]);
const form = ref({ email: "", monto: "", nota: "" });
const mensaje = ref("");
const error = ref("");
const enviando = ref(false);

async function cargar() {
  try {
    const datos = await api("/creditos");
    saldo.value = datos.saldo;
    maximo.value = datos.maximo_transferencia;
    movimientos.value = datos.movimientos;
  } catch (e) {
    error.value = e.message;
  }
}

async function transferir() {
  mensaje.value = error.value = "";
  enviando.value = true; // evita enviar dos veces la misma transferencia con un doble clic
  try {
    mensaje.value = (await api("/creditos/transferir", { metodo: "POST", cuerpo: { email: form.value.email, monto: Number(form.value.monto), nota: form.value.nota } })).mensaje;
    form.value = { email: "", monto: "", nota: "" };
    await cargar();
  } catch (e) {
    error.value = e.message;
  } finally {
    enviando.value = false;
  }
}

onMounted(cargar);
</script>

<template>
  <div class="col-lg-9">
    <h1 class="h3 mb-3">Mis créditos</h1>
    <div class="card mb-4"><div class="card-body">
      <div class="small text-secondary">Saldo disponible</div>
      <div class="display-6">{{ saldo }} <small class="fs-6 text-secondary">créditos</small></div>
    </div></div>

    <h2 class="h5">Transferir créditos</h2>
    <form class="row g-2 mb-2" @submit.prevent="transferir">
      <div class="col-md-5"><input v-model="form.email" type="email" class="form-control" placeholder="Correo del destinatario" required /></div>
      <div class="col-md-2"><input v-model="form.monto" type="number" min="1" :max="maximo" step="1" class="form-control" placeholder="Monto" required /></div>
      <div class="col-md-3"><input v-model="form.nota" class="form-control" placeholder="Nota (opcional)" maxlength="140" /></div>
      <div class="col-md-2"><button class="btn btn-dark w-100" :disabled="enviando">Transferir</button></div>
    </form>
    <div class="form-text mb-2">Máximo {{ maximo }} créditos por transferencia.</div>
    <Mensaje :texto="mensaje" tipo="success" />
    <Mensaje :texto="error" />

    <h2 class="h5 mt-4">Movimientos</h2>
    <div class="table-responsive">
      <table class="table table-sm">
        <thead><tr><th>Fecha</th><th>Concepto</th><th>Con</th><th class="text-end">Monto</th><th class="text-end">Saldo</th></tr></thead>
        <tbody>
          <tr v-for="m in movimientos" :key="m.id">
            <td class="text-nowrap">{{ fechaHora(m.creado_en) }}</td>
            <td>{{ TIPOS_MOVIMIENTO[m.tipo] }}<span v-if="m.nota" class="text-secondary"> — {{ m.nota }}</span></td>
            <td>{{ m.contraparte || "—" }}</td>
            <td class="text-end" :class="m.monto > 0 ? 'text-success' : 'text-danger'">{{ m.monto > 0 ? "+" : "" }}{{ m.monto }}</td>
            <td class="text-end">{{ m.saldo_posterior }}</td>
          </tr>
          <tr v-if="!movimientos.length"><td colspan="5" class="text-secondary">Sin movimientos.</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
