# Guía para el grupo auditor

Usted recibió el ZIP de otro grupo. Esta guía explica cómo levantar esa aplicación en su máquina para auditarla.

## 1. Verificar que el archivo es el entregado

Calcule la huella SHA-256 del ZIP y compárela con la que el grupo registró en la plataforma. Si no coincide, no audite ese archivo y avise al docente.

| Sistema | Comando |
|---|---|
| Windows (PowerShell) | `Get-FileHash .\grupoXX-AAAAMMDD-HHMM.zip -Algorithm SHA256` |
| macOS | `shasum -a 256 grupoXX-AAAAMMDD-HHMM.zip` |
| Linux | `sha256sum grupoXX-AAAAMMDD-HHMM.zip` |

Registre en su informe el nombre del archivo y su huella.

## 2. Descomprimir y crear el `.env`

Descomprima en una carpeta nueva y, desde la raíz del proyecto:

```bash
cp .env.example .env              # Windows PowerShell: Copy-Item .env.example .env
```

Verifique que `CASO` en `.env` coincida con el caso del `ENTREGA.md` del grupo. Las credenciales del administrador y de las cuentas de prueba están en `.env`, y los correos de las cuentas de prueba en el `ENTREGA.md` del grupo.

## 3. Levantar la aplicación

```bash
docker compose up --build
```

La primera vez tarda varios minutos porque descarga imágenes y librerías. Cuando termine:

- Aplicación: http://localhost:8080
- Correos que envía la aplicación: http://localhost:8025

Si el grupo indicó pasos adicionales en `ENTREGA.md`, sígalos. Opcionalmente, `python scripts/prueba_flujos.py` ejecuta pruebas de flujo funcionales (no son pruebas de seguridad).

## 4. Reiniciar el estado

Si sus pruebas dejan la aplicación en un estado inservible:

```bash
docker compose down -v
docker compose up --build
```

Esto borra la base de datos y vuelve a crear las cuentas de prueba.

## 5. Reglas de la actividad

- Audite únicamente la copia que corre en su máquina. No ataque equipos ni servicios de otros grupos.
- No redistribuya el código ni lo publique fuera del curso.
- No use llaves reales de servicios pagos con esta aplicación.
- Si encuentra secretos reales dentro del ZIP (por ejemplo una llave de API), repórtelos como hallazgo y no los use.
- Documente cada hallazgo con evidencia reproducible, como lo pide la rúbrica de la fase 2.

## 6. Problemas comunes

| Síntoma | Qué revisar |
|---|---|
| `env file ... not found` | No creó el `.env`. |
| Un puerto está ocupado (8080 o 8025) | Cambie el puerto de la izquierda en la sección `ports` del servicio en `docker-compose.yml`. |
| `seed` o `backend` no arrancan | `docker compose logs seed` y `docker compose logs backend`. Si el error está en el código del grupo, regístrelo y avise al docente. |
| La aplicación no arranca en absoluto | Avise al docente con el log. Que una entrega no arranque también es un hallazgo. |
