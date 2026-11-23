// Robot de validación de profesionales de salud.
//
// Protocolo con el backend (texto, una fila por línea, campos separados por tabulador):
//   GET  /api/internal/validacion/pendientes     ->  <id> TAB <1 si la documentación está completa | 0>
//   POST /api/internal/validacion/<id>/validar   ->  activa la cuenta (el backend la revalida)
#include <iostream>
#include <sstream>

#include "robots.hpp"
#include "texto.hpp"

void ciclo_validacion(const ClienteHttp& http) {
    Respuesta lista = http.get("/api/internal/validacion/pendientes");
    if (lista.codigo != 200) {
        std::cout << "[validacion] El backend respondió " << lista.codigo << std::endl;
        return;
    }

    int validadas = 0, incompletas = 0, fallidas = 0;
    std::istringstream lineas(lista.cuerpo);
    std::string linea;
    while (std::getline(lineas, linea)) {
        auto campos = texto::separar(linea, '\t');
        if (campos.size() != 2 || !texto::es_identificador(campos[0])) continue;  // línea inesperada: se ignora

        if (campos[1] != "1") {
            incompletas++;  // documentación incompleta: queda para revisión manual del administrador
            continue;
        }
        Respuesta resultado = http.post("/api/internal/validacion/" + campos[0] + "/validar", "");
        if (resultado.codigo == 200) {
            validadas++;
            std::cout << "[validacion] Solicitud #" << campos[0] << " validada." << std::endl;
        } else {
            fallidas++;
            std::cout << "[validacion] Solicitud #" << campos[0] << " no validada (HTTP " << resultado.codigo << ")." << std::endl;
        }
    }
    std::cout << "[validacion] Ciclo terminado. Validadas: " << validadas << ", incompletas: " << incompletas
              << ", con error: " << fallidas << std::endl;
}
