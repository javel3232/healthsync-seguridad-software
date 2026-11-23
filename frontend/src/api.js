// Cliente del backend. Todas las rutas son relativas (/api/...).
//
// Seguridad: la sesión viaja en una cookie HttpOnly que JavaScript no puede leer. Para las
// peticiones que modifican datos se envía además el token CSRF (cabecera X-CSRF-Token),
// que el backend entrega al iniciar sesión y se guarda solo en memoria.

export class ErrorApi extends Error {
  constructor(mensaje, estado) {
    super(mensaje);
    this.estado = estado;
  }
}

let tokenCsrf = null;
let alExpirar = () => {};

export function fijarCsrf(token) {
  tokenCsrf = token;
}

// Permite a sesion.js enterarse cuando el servidor responde 401 en una sesión que creíamos abierta.
export function registrarAlExpirar(funcion) {
  alExpirar = funcion;
}

/**
 * @param {string} ruta     Ruta que sigue a /api, por ejemplo "/consultas".
 * @param {object} opciones { metodo, cuerpo (objeto JSON), formulario (FormData) }
 */
export async function api(ruta, { metodo = "GET", cuerpo, formulario } = {}) {
  const opciones = { method: metodo, credentials: "same-origin", headers: { Accept: "application/json" } };
  if (metodo !== "GET") {
    if (tokenCsrf) opciones.headers["X-CSRF-Token"] = tokenCsrf;
    if (formulario) {
      opciones.body = formulario; // el navegador fija el Content-Type multipart con su límite
    } else {
      opciones.headers["Content-Type"] = "application/json";
      opciones.body = JSON.stringify(cuerpo ?? {});
    }
  }
  let respuesta;
  try {
    respuesta = await fetch(`/api${ruta}`, opciones);
  } catch {
    throw new ErrorApi("No hay conexión con el servidor.", 0);
  }
  const datos = await respuesta.json().catch(() => ({}));
  if (!respuesta.ok) {
    if (respuesta.status === 401 && !ruta.startsWith("/auth/")) alExpirar();
    throw new ErrorApi(datos.error || `Error ${respuesta.status}`, respuesta.status);
  }
  return datos;
}
