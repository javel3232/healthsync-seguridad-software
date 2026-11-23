// Utilidades de texto para interpretar las respuestas del backend.
#pragma once

#include <cstdlib>
#include <string>
#include <vector>

namespace texto {

// Divide `texto` por el separador `sep`. Conserva los campos vacíos.
inline std::vector<std::string> separar(const std::string& texto, char sep) {
    std::vector<std::string> partes;
    std::string actual;
    for (char c : texto) {
        if (c == sep) {
            partes.push_back(actual);
            actual.clear();
        } else {
            actual.push_back(c);
        }
    }
    partes.push_back(actual);
    return partes;
}

// ¿Es una cadena no vacía de dígitos de longitud razonable? (identificadores numéricos)
inline bool es_identificador(const std::string& s) {
    if (s.empty() || s.size() > 18) return false;
    for (char c : s) {
        if (c < '0' || c > '9') return false;
    }
    return true;
}

// Convierte `s` a número. Devuelve false si no es un número completo y válido.
inline bool leer_numero(const std::string& s, double* resultado) {
    if (s.empty()) return false;
    char* fin = nullptr;
    double valor = std::strtod(s.c_str(), &fin);
    if (fin == s.c_str() || *fin != '\0') return false;
    *resultado = valor;
    return true;
}

}  // namespace texto
