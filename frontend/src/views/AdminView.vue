<script setup>
import { onMounted, ref } from "vue";
import Mensaje from "@/components/Mensaje.vue";
import { api } from "@/api";
import { fecha, fechaHora, ROLES } from "@/formato";

const pestana = ref("solicitudes");
const estado = ref("pendiente");
const solicitudes = ref([]);
const cuentas = ref([]);
const abierta = ref(null); // solicitud con la tarjeta desplegada
const motivo = ref("");
const mensaje = ref("");
const error = ref("");

async function cargar() {
  error.value = "";
  try {
    if (pestana.value === "solicitudes") {
      solicitudes.value = (await api(`/admin/solicitudes?estado=${estado.value}`)).solicitudes;
    } else {
      cuentas.value = (await api("/admin/cuentas")).cuentas;
    }
  } catch (e) {
    error.value = e.message;
  }
}

function cambiarPestana(nombre) {
  pestana.value = nombre;
  cargar();
}

async function resolver(solicitud, accion) {
  mensaje.value = error.value = "";
  try {
    const cuerpo = accion === "rechazar" ? { motivo: motivo.value } : {};
    mensaje.value = (await api(`/admin/solicitudes/${solicitud.id}/${accion}`, { metodo: "POST", cuerpo })).mensaje;
    abierta.value = null;
    motivo.value = "";
    await cargar();
  } catch (e) {
    error.value = e.message;
  }
}

function alternar(solicitud) {
  abierta.value = abierta.value === solicitud.id ? null : solicitud.id;
  motivo.value = "";
}

onMounted(cargar);
</script>

<template>
  <div class="col-lg-11">
    <h1 class="h3 mb-3">Administración</h1>
    <ul class="nav nav-tabs mb-3">
      <li class="nav-item"><button class="nav-link" :class="{ active: pestana === 'solicitudes' }" @click="cambiarPestana('solicitudes')">Solicitudes de profesionales</button></li>
      <li class="nav-item"><button class="nav-link" :class="{ active: pestana === 'cuentas' }" @click="cambiarPestana('cuentas')">Todas las cuentas</button></li>
    </ul>
    <Mensaje :texto="mensaje" tipo="success" />
    <Mensaje :texto="error" />

    <template v-if="pestana === 'solicitudes'">
      <div class="mb-3 d-flex gap-2 align-items-center">
        <label class="small" for="estado">Mostrar:</label>
        <select id="estado" v-model="estado" class="form-select form-select-sm w-auto" @change="cargar">
          <option value="pendiente">Pendientes</option>
          <option value="activo">Aprobadas</option>
          <option value="rechazado">Rechazadas</option>
          <option value="todos">Todas</option>
        </select>
      </div>

      <div v-for="s in solicitudes" :key="s.id" class="card mb-2">
        <div class="card-body">
          <div class="d-flex justify-content-between align-items-start flex-wrap gap-2">
            <div>
              <strong>{{ s.nombre }}</strong> <span class="badge text-bg-info">{{ s.especialidad }}</span>
              <div class="small text-secondary">{{ s.email }} · nacimiento {{ fecha(s.fecha_nacimiento) }} · solicitud {{ fechaHora(s.creado_en) }}</div>
              <div class="small">
                Documentación:
                <span :class="s.documentacion_completa ? 'text-success' : 'text-danger'">{{ s.documentacion_completa ? "completa" : "incompleta" }}</span>
                <span v-if="s.estado === 'activo'"> · aprobada {{ s.revisado_por_bot ? "por el robot de validación" : "por un administrador" }}</span>
                <span v-if="s.estado === 'rechazado'"> · rechazada: {{ s.motivo_rechazo }}</span>
              </div>
            </div>
            <div class="d-flex gap-2 align-items-center">
              <span class="badge" :class="{ 'text-bg-warning': s.estado === 'pendiente', 'text-bg-success': s.estado === 'activo', 'text-bg-secondary': s.estado === 'rechazado' }">{{ s.estado }}</span>
              <button class="btn btn-outline-dark btn-sm" @click="alternar(s)">{{ abierta === s.id ? "Cerrar" : "Revisar" }}</button>
            </div>
          </div>

          <div v-if="abierta === s.id" class="border-top mt-3 pt-3">
            <div class="row g-3">
              <div class="col-md-5">
                <div class="small text-secondary mb-1">Tarjeta profesional</div>
                <img v-if="s.documentacion_completa" :src="`/api/admin/solicitudes/${s.id}/tarjeta`" alt="Foto de la tarjeta profesional" class="img-fluid border rounded" />
                <div v-else class="text-danger small">No adjuntó la tarjeta profesional.</div>
              </div>
              <div class="col-md-7" v-if="s.estado === 'pendiente'">
                <button class="btn btn-success btn-sm mb-3" :disabled="!s.documentacion_completa" @click="resolver(s, 'aprobar')">Aprobar y activar cuenta</button>
                <div class="input-group input-group-sm">
                  <input v-model="motivo" class="form-control" placeholder="Motivo del rechazo (obligatorio)" minlength="5" maxlength="300" aria-label="Motivo del rechazo" />
                  <button class="btn btn-outline-danger" @click="resolver(s, 'rechazar')">Rechazar</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <p v-if="!solicitudes.length" class="text-secondary">No hay solicitudes en este estado.</p>
    </template>

    <div v-else class="table-responsive">
      <table class="table table-sm">
        <thead><tr><th>#</th><th>Nombre</th><th>Correo</th><th>Rol</th><th>Estado</th><th>Creada</th></tr></thead>
        <tbody>
          <tr v-for="c in cuentas" :key="c.id">
            <td>{{ c.id }}</td><td>{{ c.nombre }}</td><td>{{ c.email }}</td><td>{{ ROLES[c.rol] }}</td><td>{{ c.estado }}</td><td>{{ fechaHora(c.creado_en) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
