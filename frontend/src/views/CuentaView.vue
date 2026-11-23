<script setup>
import { onMounted, ref } from "vue";
import Mensaje from "@/components/Mensaje.vue";
import { api } from "@/api";
import { fecha, ROLES } from "@/formato";
import { sesion } from "@/sesion";

const cuenta = ref(null);
const edicion = ref({ nombre: "", especialidad: "", descripcion: "", tarifa_creditos: 20 });
const claves = ref({ password_actual: "", password_nueva: "" });
const mensaje = ref("");
const error = ref("");
const mensajeClave = ref("");
const errorClave = ref("");

function cargarFormulario() {
  edicion.value.nombre = cuenta.value.nombre;
  if (cuenta.value.profesional) Object.assign(edicion.value, cuenta.value.profesional);
}

onMounted(async () => {
  try {
    cuenta.value = (await api("/perfil")).cuenta;
    cargarFormulario();
  } catch (e) {
    error.value = e.message;
  }
});

async function guardar() {
  mensaje.value = error.value = "";
  const cuerpo = { nombre: edicion.value.nombre };
  if (cuenta.value.profesional) {
    cuerpo.especialidad = edicion.value.especialidad;
    cuerpo.descripcion = edicion.value.descripcion;
    cuerpo.tarifa_creditos = Number(edicion.value.tarifa_creditos);
  }
  try {
    cuenta.value = (await api("/perfil", { metodo: "PUT", cuerpo })).cuenta;
    sesion.usuario = { ...sesion.usuario, nombre: cuenta.value.nombre };
    mensaje.value = "Perfil actualizado.";
  } catch (e) {
    error.value = e.message;
  }
}

async function cambiarClave() {
  mensajeClave.value = errorClave.value = "";
  try {
    const datos = await api("/auth/cambiar-password", { metodo: "POST", cuerpo: claves.value });
    sesion.iniciar(sesion.usuario, datos.csrf_token);
    claves.value = { password_actual: "", password_nueva: "" };
    mensajeClave.value = "Contraseña actualizada. Se cerraron las demás sesiones abiertas.";
  } catch (e) {
    errorClave.value = e.message;
  }
}
</script>

<template>
  <div class="col-lg-8" v-if="cuenta">
    <h1 class="h3">Mi cuenta</h1>
    <dl class="row">
      <dt class="col-sm-4">Correo</dt><dd class="col-sm-8">{{ cuenta.email }}</dd>
      <dt class="col-sm-4">Tipo de cuenta</dt><dd class="col-sm-8">{{ ROLES[cuenta.rol] }}</dd>
      <dt class="col-sm-4">Nacimiento</dt><dd class="col-sm-8">{{ fecha(cuenta.fecha_nacimiento) }}</dd>
      <template v-if="cuenta.saldo_creditos !== null">
        <dt class="col-sm-4">Créditos</dt><dd class="col-sm-8">{{ cuenta.saldo_creditos }}</dd>
        <dt class="col-sm-4">Puntos</dt><dd class="col-sm-8">{{ cuenta.puntos }}</dd>
        <dt class="col-sm-4">Premium hasta</dt><dd class="col-sm-8">{{ cuenta.premium_hasta ? fecha(cuenta.premium_hasta) : "No tiene premium" }}</dd>
      </template>
    </dl>

    <h2 class="h5 mt-4">Editar perfil</h2>
    <form @submit.prevent="guardar" class="mb-3">
      <div class="mb-3">
        <label class="form-label" for="nombre">Nombre</label>
        <input id="nombre" v-model="edicion.nombre" class="form-control" maxlength="100" required />
      </div>
      <template v-if="cuenta.profesional">
        <div class="mb-3">
          <label class="form-label" for="esp">Especialidad</label>
          <input id="esp" v-model="edicion.especialidad" class="form-control" maxlength="80" required />
        </div>
        <div class="mb-3">
          <label class="form-label" for="desc">Descripción</label>
          <textarea id="desc" v-model="edicion.descripcion" class="form-control" rows="3" maxlength="500"></textarea>
        </div>
        <div class="mb-3">
          <label class="form-label" for="tarifa">Tarifa por consulta (créditos)</label>
          <input id="tarifa" v-model="edicion.tarifa_creditos" type="number" min="1" max="1000" class="form-control" required />
        </div>
      </template>
      <Mensaje :texto="mensaje" tipo="success" />
      <Mensaje :texto="error" />
      <button class="btn btn-dark">Guardar cambios</button>
    </form>

    <h2 class="h5 mt-4">Cambiar contraseña</h2>
    <form @submit.prevent="cambiarClave">
      <div class="row g-2 mb-2">
        <div class="col-md-6">
          <input v-model="claves.password_actual" type="password" class="form-control" placeholder="Contraseña actual" autocomplete="current-password" required />
        </div>
        <div class="col-md-6">
          <input v-model="claves.password_nueva" type="password" class="form-control" placeholder="Contraseña nueva (mín. 10)" minlength="10" autocomplete="new-password" required />
        </div>
      </div>
      <Mensaje :texto="mensajeClave" tipo="success" />
      <Mensaje :texto="errorClave" />
      <button class="btn btn-outline-dark btn-sm">Cambiar contraseña</button>
    </form>
  </div>
  <Mensaje v-else :texto="error" />
</template>
