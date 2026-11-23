<script setup>
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import Mensaje from "@/components/Mensaje.vue";
import { api } from "@/api";

const route = useRoute();
const roles = ref({});
const formulario = ref({
  nombre: "",
  email: "",
  password: "",
  fecha_nacimiento: "",
  rol: "paciente",
  especialidad: "",
  codigo_referido: typeof route.query.ref === "string" ? route.query.ref : "",
});
const tarjeta = ref(null);
const mensaje = ref("");
const error = ref("");
const enviando = ref(false);

const esProfesional = computed(() => formulario.value.rol === "profesional");

onMounted(async () => {
  try {
    roles.value = (await api("/config")).roles;
  } catch (e) {
    error.value = e.message;
  }
});

function elegirArchivo(evento) {
  tarjeta.value = evento.target.files[0] ?? null;
}

async function registrar() {
  mensaje.value = "";
  error.value = "";
  if (esProfesional.value && !tarjeta.value) {
    error.value = "Adjunte la foto de su tarjeta profesional.";
    return;
  }
  // multipart/form-data: permite enviar la foto junto con los demás campos.
  const datos = new FormData();
  for (const [clave, valor] of Object.entries(formulario.value)) {
    if (clave === "especialidad" && !esProfesional.value) continue;
    datos.append(clave, valor);
  }
  if (esProfesional.value) datos.append("tarjeta", tarjeta.value);

  enviando.value = true;
  try {
    mensaje.value = (await api("/auth/registro", { metodo: "POST", formulario: datos })).mensaje;
    formulario.value.password = "";
  } catch (e) {
    error.value = e.message;
  } finally {
    enviando.value = false;
  }
}
</script>

<template>
  <div class="col-md-7 col-lg-6">
    <h1 class="h3 mb-3">Crear una cuenta</h1>
    <form @submit.prevent="registrar">
      <div class="mb-3">
        <label class="form-label" for="rol">Tipo de cuenta</label>
        <select id="rol" v-model="formulario.rol" class="form-select">
          <option v-for="(datos, clave) in roles" :key="clave" :value="clave">{{ datos.etiqueta }}</option>
        </select>
      </div>
      <div class="mb-3">
        <label class="form-label" for="nombre">Nombre completo</label>
        <input id="nombre" v-model="formulario.nombre" class="form-control" maxlength="100" required />
      </div>
      <div class="mb-3">
        <label class="form-label" for="email">Correo</label>
        <input id="email" v-model="formulario.email" type="email" class="form-control" autocomplete="email" required />
      </div>
      <div class="mb-3">
        <label class="form-label" for="password">Contraseña</label>
        <input id="password" v-model="formulario.password" type="password" class="form-control" minlength="10" autocomplete="new-password" required />
        <div class="form-text">Mínimo 10 caracteres, con letras y números.</div>
      </div>
      <div class="mb-3">
        <label class="form-label" for="nacimiento">Fecha de nacimiento</label>
        <input id="nacimiento" v-model="formulario.fecha_nacimiento" type="date" class="form-control" required />
        <div class="form-text">Debe ser mayor de 18 años.</div>
      </div>

      <template v-if="esProfesional">
        <div class="mb-3">
          <label class="form-label" for="especialidad">Especialidad</label>
          <input id="especialidad" v-model="formulario.especialidad" class="form-control" maxlength="80" placeholder="Ej.: Cardiología" />
        </div>
        <div class="mb-3">
          <label class="form-label" for="tarjeta">Foto de su tarjeta profesional</label>
          <input id="tarjeta" type="file" class="form-control" accept="image/png,image/jpeg" @change="elegirArchivo" required />
          <div class="form-text">PNG o JPEG de hasta 2 MB. Su cuenta se activará cuando validemos la tarjeta.</div>
        </div>
      </template>

      <div class="mb-3">
        <label class="form-label" for="referido">Código de referidos (opcional)</label>
        <input id="referido" v-model="formulario.codigo_referido" class="form-control" maxlength="20" />
      </div>

      <Mensaje :texto="mensaje" tipo="success" />
      <Mensaje :texto="error" />
      <button class="btn btn-dark" :disabled="enviando">Registrarse</button>
      <RouterLink v-if="mensaje" class="btn btn-link" to="/ingresar">Ir a ingresar</RouterLink>
    </form>
  </div>
</template>
