<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import Mensaje from "@/components/Mensaje.vue";
import { api } from "@/api";
import { sesion } from "@/sesion";

const router = useRouter();
const email = ref("");
const password = ref("");
const error = ref("");
const enviando = ref(false);

async function ingresar() {
  error.value = "";
  enviando.value = true;
  try {
    const datos = await api("/auth/ingresar", { metodo: "POST", cuerpo: { email: email.value, password: password.value } });
    sesion.iniciar(datos.usuario, datos.csrf_token);
    router.push({ name: datos.usuario.rol === "admin" ? "admin" : "consultas" });
  } catch (e) {
    error.value = e.message;
  } finally {
    enviando.value = false;
  }
}
</script>

<template>
  <div class="col-md-5">
    <h1 class="h3 mb-3">Ingresar</h1>
    <form @submit.prevent="ingresar">
      <div class="mb-3">
        <label class="form-label" for="email">Correo</label>
        <input id="email" v-model="email" type="email" class="form-control" autocomplete="username" required />
      </div>
      <div class="mb-3">
        <label class="form-label" for="password">Contraseña</label>
        <input id="password" v-model="password" type="password" class="form-control" autocomplete="current-password" required />
      </div>
      <Mensaje :texto="error" />
      <button class="btn btn-dark" :disabled="enviando">Ingresar</button>
      <RouterLink class="btn btn-link" to="/registro">Crear una cuenta</RouterLink>
    </form>
  </div>
</template>
