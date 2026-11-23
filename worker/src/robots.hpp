// Los dos robots del sistema. Cada uno expone una función que ejecuta UN ciclo.
//
//   validacion: simula a un administrador. Cada minuto revisa las solicitudes de
//               profesionales pendientes y valida las que tienen la documentación completa.
//   alertas:    cada segundo evalúa la lectura más reciente de cada paciente contra
//               los umbrales de sus alertas y pide al backend dispararlas.
//
// Los robots proponen y el backend decide: el backend vuelve a comprobar cada condición.
#pragma once

#include "http.hpp"

void ciclo_validacion(const ClienteHttp& http);
void ciclo_alertas(const ClienteHttp& http);
