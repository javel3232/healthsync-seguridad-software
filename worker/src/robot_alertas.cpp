// Robot de monitoreo de alertas de salud.
//
// Protocolo con el backend (texto, campos separados por tabulador):
//   GET  /api/internal/alertas/evaluar
//          -> <alerta_id> TAB <metrica_id> TAB <mayor|menor> TAB <umbral> TAB <valor>
//   POST /api/internal/alertas/<alerta_id>/disparar   (cuerpo: metrica_id=<id>)
//
// Aquí se decide si la lectura supera el umbral; el backend lo vuelve a comprobar antes
// de registrar el disparo y enviar los correos.
#include <iostream>
#include <sstream>

#include "robots.hpp"
#include "texto.hpp"

namespace {

bool supera_umbral(const std::string& operador, double valor, double umbral) {
    if (operador == "mayor") return valor > umbral;
    if (operador == "menor") return valor < umbral;
    return false;
}

}  // namespace

void ciclo_alertas(const ClienteHttp& http) {
    Respuesta lista = http.get("/api/internal/alertas/evaluar");
    if (lista.codigo != 200) {
        std::cout << "[alertas] El backend respondió " << lista.codigo << std::endl;
        return;
    }

    std::istringstream lineas(lista.cuerpo);
    std::string linea;
    while (std::getline(lineas, linea)) {
        auto campos = texto::separar(linea, '\t');
        double umbral = 0, valor = 0;
        if (campos.size() != 5 || !texto::es_identificador(campos[0]) || !texto::es_identificador(campos[1]) ||
            !texto::leer_numero(campos[3], &umbral) || !texto::leer_numero(campos[4], &valor)) {
            continue;  // línea inesperada: se ignora
        }
        if (!supera_umbral(campos[2], valor, umbral)) continue;

        Respuesta resultado = http.post("/api/internal/alertas/" + campos[0] + "/disparar", "metrica_id=" + campos[1]);
        std::cout << "[alertas] Alerta #" << campos[0] << " superada (valor " << valor << ", umbral " << umbral
                  << "): HTTP " << resultado.codigo << std::endl;
    }
}
