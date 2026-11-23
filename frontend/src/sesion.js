// Estado de la sesión en el navegador.
//
// La fuente de verdad es el servidor: al cargar la aplicación se consulta /auth/yo.
// No se guarda nada en localStorage (ni el usuario ni el token), así que no hay datos
// de sesión que un script malicioso pueda robar.
import { reactive } from "vue";
import { api, fijarCsrf, registrarAlExpirar } from "./api";

export const sesion = reactive({
  usuario: null,
  cargada: false,

  // Consulta al servidor quién está autenticado. Se hace una sola vez por carga de página.
  async cargar() {
    if (this.cargada) return;
    try {
      const datos = await api("/auth/yo");
      this.usuario = datos.usuario;
      fijarCsrf(datos.csrf_token);
    } catch {
      this.usuario = null;
    }
    this.cargada = true;
  },

  iniciar(usuario, tokenCsrf) {
    this.usuario = usuario;
    this.cargada = true;
    fijarCsrf(tokenCsrf);
  },

  async salir() {
    await api("/auth/salir", { metodo: "POST" }).catch(() => {});
    this.limpiar();
  },

  limpiar() {
    this.usuario = null;
    fijarCsrf(null);
  },

  tieneRol(...roles) {
    return this.usuario !== null && roles.includes(this.usuario.rol);
  },
});

// Si el servidor dice que la sesión ya no es válida (caducó o se cerró en otro lado), volver al login.
registrarAlExpirar(() => {
  if (sesion.usuario) {
    sesion.limpiar();
    window.location.assign("/ingresar");
  }
});
