// Robots periódicos (servicio "worker" y "worker-alertas" de docker-compose.yml).
//
// El mismo ejecutable cumple dos funciones según la variable ROBOT:
//   ROBOT=validacion  -> valida solicitudes de profesionales (por defecto, cada 60 s)
//   ROBOT=alertas     -> evalúa alertas de salud (cada 1 s)
// Variables: BACKEND_URL, WORKER_TOKEN, WORKER_INTERVAL_SECONDS.
#include <curl/curl.h>
#include <unistd.h>

#include <csignal>
#include <cstdlib>
#include <iostream>
#include <string>

#include "http.hpp"
#include "robots.hpp"

namespace {

volatile std::sig_atomic_t detener = 0;

void manejar_senal(int) { detener = 1; }

std::string variable(const char* nombre, const std::string& defecto) {
    const char* valor = std::getenv(nombre);
    return (valor && *valor) ? valor : defecto;
}

}  // namespace

int main() {
    std::signal(SIGTERM, manejar_senal);
    std::signal(SIGINT, manejar_senal);

    const std::string robot = variable("ROBOT", "validacion");
    const std::string token = variable("WORKER_TOKEN", "");
    if (robot != "validacion" && robot != "alertas") {
        std::cerr << "[robot] ROBOT debe ser 'validacion' o 'alertas' (recibido: " << robot << ")" << std::endl;
        return 1;
    }
    if (token.size() < 16) {
        std::cerr << "[robot] WORKER_TOKEN no está definido o es demasiado corto." << std::endl;
        return 1;
    }
    int intervalo = std::atoi(variable("WORKER_INTERVAL_SECONDS", "60").c_str());
    if (intervalo < 1 || intervalo > 3600) intervalo = (robot == "alertas") ? 1 : 60;

    curl_global_init(CURL_GLOBAL_DEFAULT);
    const ClienteHttp http(variable("BACKEND_URL", "http://backend:8000"), token);
    std::cout << "[" << robot << "] Iniciado. Intervalo: " << intervalo << " s" << std::endl;

    long ciclos = 0;
    while (!detener) {
        if (robot == "validacion") {
            ciclo_validacion(http);
        } else {
            ciclo_alertas(http);
            // Latido cada 5 minutos: confirma que el robot sigue vivo sin llenar el log (corre cada segundo).
            if (++ciclos % (300 / intervalo) == 0) std::cout << "[alertas] Activo. Ciclos ejecutados: " << ciclos << std::endl;
        }
        // Espera en tramos de 200 ms para responder rápido a SIGTERM.
        for (int i = 0; i < intervalo * 5 && !detener; i++) usleep(200000);
    }

    curl_global_cleanup();
    std::cout << "[" << robot << "] Detenido." << std::endl;
    return 0;
}
