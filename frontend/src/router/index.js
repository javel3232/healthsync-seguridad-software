import { createRouter, createWebHistory } from "vue-router";
import { sesion } from "@/sesion";

// Las vistas se cargan bajo demanda: el navegador solo descarga la que se visita.
// meta.requiereSesion / meta.roles: la interfaz oculta lo que no corresponde, pero la
// autorización real siempre la decide el backend.
const routes = [
  { path: "/", name: "inicio", component: () => import("@/views/InicioView.vue") },
  { path: "/ingresar", name: "ingresar", component: () => import("@/views/IngresarView.vue") },
  { path: "/registro", name: "registro", component: () => import("@/views/RegistroView.vue") },
  { path: "/cuenta", name: "cuenta", component: () => import("@/views/CuentaView.vue"), meta: { requiereSesion: true } },
  {
    path: "/directorio",
    name: "directorio",
    component: () => import("@/views/DirectorioView.vue"),
    meta: { requiereSesion: true, roles: ["paciente", "profesional"] },
  },
  {
    path: "/consultas",
    name: "consultas",
    component: () => import("@/views/ConsultasView.vue"),
    meta: { requiereSesion: true, roles: ["paciente", "profesional"] },
  },
  {
    path: "/consultas/:id(\\d+)",
    name: "consulta",
    component: () => import("@/views/ConsultaDetalleView.vue"),
    meta: { requiereSesion: true, roles: ["paciente", "profesional"] },
  },
  {
    path: "/wearables",
    name: "wearables",
    component: () => import("@/views/WearablesView.vue"),
    meta: { requiereSesion: true, roles: ["paciente"] },
  },
  {
    path: "/alertas",
    name: "alertas",
    component: () => import("@/views/AlertasView.vue"),
    meta: { requiereSesion: true, roles: ["paciente", "profesional"] },
  },
  {
    path: "/creditos",
    name: "creditos",
    component: () => import("@/views/CreditosView.vue"),
    meta: { requiereSesion: true, roles: ["paciente", "profesional"] },
  },
  {
    path: "/referidos",
    name: "referidos",
    component: () => import("@/views/ReferidosView.vue"),
    meta: { requiereSesion: true, roles: ["paciente", "profesional"] },
  },
  { path: "/admin", name: "admin", component: () => import("@/views/AdminView.vue"), meta: { requiereSesion: true, roles: ["admin"] } },
  { path: "/:resto(.*)*", redirect: { name: "inicio" } },
];

const router = createRouter({ history: createWebHistory(), routes });

router.beforeEach(async (destino) => {
  await sesion.cargar();
  if (!destino.meta.requiereSesion) return true;
  if (!sesion.usuario) return { name: "ingresar" };
  if (destino.meta.roles && !destino.meta.roles.includes(sesion.usuario.rol)) return { name: "inicio" };
  return true;
});

export default router;
