<script setup>
// Banner de estado reutilizable. El texto se interpola (nunca se inserta como HTML),
// de modo que un mensaje con etiquetas se muestra literal y no se ejecuta.
defineProps({
  texto: { type: String, default: "" },
  tipo: { type: String, default: "danger" }, // danger | success | info | warning
});
</script>

<template>
  <div v-if="texto" :class="`alert alert-${tipo} py-2`" role="alert">{{ texto }}</div>
</template>
