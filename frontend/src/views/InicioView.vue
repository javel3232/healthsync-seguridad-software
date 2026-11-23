<script setup>
import { sesion } from "@/sesion";
</script>

<template>
  <div class="col-lg-9">
    <h1 class="h3">HealthSync</h1>
    <p class="lead">
      Plataforma de salud digital: sincronice los datos de su wearable, consulte a profesionales verificados por
      video y reciba alertas cuando sus indicadores se salgan de rango.
    </p>

    <div v-if="!sesion.usuario" class="d-flex gap-2 mb-4">
      <RouterLink class="btn btn-dark" to="/ingresar">Ingresar</RouterLink>
      <RouterLink class="btn btn-outline-dark" to="/registro">Crear una cuenta</RouterLink>
    </div>
    <p v-else class="mb-4">Hola, <strong>{{ sesion.usuario.nombre }}</strong>. Use el menú superior para continuar.</p>

    <div class="row g-3">
      <div class="col-md-6">
        <div class="card h-100"><div class="card-body">
          <h2 class="h6">Wearables</h2>
          <p class="small mb-0">Vincule su dispositivo y guarde su historial de frecuencia cardíaca, pasos, oxígeno y sueño.</p>
        </div></div>
      </div>
      <div class="col-md-6">
        <div class="card h-100"><div class="card-body">
          <h2 class="h6">Consultas virtuales</h2>
          <p class="small mb-0">Agende con profesionales validados. Usted decide si comparte sus métricas en cada consulta.</p>
        </div></div>
      </div>
      <div class="col-md-6">
        <div class="card h-100"><div class="card-body">
          <h2 class="h6">Alertas de salud</h2>
          <p class="small mb-0">Un monitor revisa sus lecturas cada segundo y le avisa por correo cuando superan sus umbrales.</p>
        </div></div>
      </div>
      <div class="col-md-6">
        <div class="card h-100"><div class="card-body">
          <h2 class="h6">Créditos y referidos</h2>
          <p class="small mb-0">Pague consultas con créditos, transfiera a otros usuarios y gane premium invitando personas.</p>
        </div></div>
      </div>
    </div>
  </div>
</template>
