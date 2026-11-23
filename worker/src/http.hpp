// Cliente HTTP mínimo (libcurl) para hablar con los endpoints internos del backend.
#pragma once

#include <string>

struct Respuesta {
    long codigo = 0;      // 0 si no hubo respuesta (error de red)
    std::string cuerpo;
};

class ClienteHttp {
public:
    // `base`: URL del backend (p. ej. http://backend:8000). `token`: valor de X-Internal-Token.
    ClienteHttp(std::string base, std::string token);

    Respuesta get(const std::string& ruta) const;
    // `formulario`: cuerpo application/x-www-form-urlencoded (puede ir vacío).
    Respuesta post(const std::string& ruta, const std::string& formulario) const;

private:
    Respuesta ejecutar(const std::string& ruta, const std::string* formulario) const;

    std::string base_;
    std::string token_;
};
