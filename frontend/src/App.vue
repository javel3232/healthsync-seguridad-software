<script setup>
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { api } from "@/api";
import { ROLES } from "@/formato";
import { sesion } from "@/sesion";

const router = useRouter();
const nombreCaso = ref("HealthSync");

onMounted(async () => {
  try {
    nombreCaso.value = (await api("/config")).nombre;
  } catch {
    /* El backend aún no responde; se mantiene el nombre por defecto. */
  }
});

async function salir() {
  await sesion.salir();
  router.push({ name: "inicio" });
}
</script>

<template>
  <nav class="navbar navbar-expand-lg navbar-dark bg-dark mb-4">
    <div class="container">
      <RouterLink class="navbar-brand" to="/">{{ nombreCaso }}</RouterLink>
      <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#menu" aria-label="Menú">
        <span class="navbar-toggler-icon"></span>
      </button>
      <div id="menu" class="collapse navbar-collapse">
        <!-- El menú muestra solo lo que corresponde al rol; el backend vuelve a verificar cada acción. -->
        <ul class="navbar-nav me-auto" v-if="sesion.usuario">
          <template v-if="sesion.tieneRol('paciente', 'profesional')">
            <li class="nav-item"><RouterLink class="nav-link" to="/directorio">Directorio</RouterLink></li>
            <li class="nav-item"><RouterLink class="nav-link" to="/consultas">Consultas</RouterLink></li>
            <li class="nav-item" v-if="sesion.tieneRol('paciente')">
              <RouterLink class="nav-link" to="/wearables">Wearables</RouterLink>
            </li>
            <li class="nav-item"><RouterLink class="nav-link" to="/alertas">Alertas</RouterLink></li>
            <li class="nav-item"><RouterLink class="nav-link" to="/creditos">Créditos</RouterLink></li>
            <li class="nav-item"><RouterLink class="nav-link" to="/referidos">Referidos</RouterLink></li>
          </template>
          <li class="nav-item" v-if="sesion.tieneRol('admin')">
            <RouterLink class="nav-link" to="/admin">Administración</RouterLink>
          </li>
        </ul>
        <div v-else class="me-auto"></div>

        <div v-if="sesion.usuario" class="d-flex align-items-center gap-3 text-white">
          <RouterLink class="text-white text-decoration-none" to="/cuenta">
            {{ sesion.usuario.nombre }} <small class="text-secondary">({{ ROLES[sesion.usuario.rol] }})</small>
          </RouterLink>
          <button class="btn btn-outline-light btn-sm" @click="salir">Salir</button>
        </div>
        <div v-else class="d-flex gap-2">
          <RouterLink class="btn btn-outline-light btn-sm" to="/ingresar">Ingresar</RouterLink>
          <RouterLink class="btn btn-light btn-sm" to="/registro">Registrarse</RouterLink>
        </div>
      </div>
    </div>
  </nav>
  <main class="container pb-5">
    <RouterView />
  </main>
</template>
