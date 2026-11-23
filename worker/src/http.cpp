#include "http.hpp"

#include <curl/curl.h>

namespace {

// Las respuestas internas son pequeñas: se corta si alguna crece de forma anormal.
constexpr size_t kTamanoMaximo = 2 * 1024 * 1024;

size_t acumular(char* datos, size_t tam, size_t n, void* destino) {
    auto* cuerpo = static_cast<std::string*>(destino);
    size_t recibido = tam * n;
    if (cuerpo->size() + recibido > kTamanoMaximo) return 0;  // 0 hace fallar la transferencia
    cuerpo->append(datos, recibido);
    return recibido;
}

}  // namespace

ClienteHttp::ClienteHttp(std::string base, std::string token) : base_(std::move(base)), token_(std::move(token)) {}

Respuesta ClienteHttp::get(const std::string& ruta) const { return ejecutar(ruta, nullptr); }

Respuesta ClienteHttp::post(const std::string& ruta, const std::string& formulario) const {
    return ejecutar(ruta, &formulario);
}

Respuesta ClienteHttp::ejecutar(const std::string& ruta, const std::string* formulario) const {
    Respuesta respuesta;
    CURL* curl = curl_easy_init();
    if (!curl) return respuesta;

    const std::string url = base_ + ruta;
    const std::string encabezado = "X-Internal-Token: " + token_;
    curl_slist* encabezados = curl_slist_append(nullptr, encabezado.c_str());

    curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, encabezados);
    curl_easy_setopt(curl, CURLOPT_CONNECTTIMEOUT, 3L);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, 15L);
    curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 0L);  // nunca seguir redirecciones
    curl_easy_setopt(curl, CURLOPT_PROTOCOLS_STR, "http,https");
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, acumular);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &respuesta.cuerpo);
    if (formulario) {
        curl_easy_setopt(curl, CURLOPT_POST, 1L);
        curl_easy_setopt(curl, CURLOPT_POSTFIELDS, formulario->c_str());
        curl_easy_setopt(curl, CURLOPT_POSTFIELDSIZE, static_cast<long>(formulario->size()));
    }

    if (curl_easy_perform(curl) == CURLE_OK) {
        curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &respuesta.codigo);
    }
    curl_slist_free_all(encabezados);
    curl_easy_cleanup(curl);
    return respuesta;
}
