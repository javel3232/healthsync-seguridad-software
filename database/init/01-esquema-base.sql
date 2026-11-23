-- Esquema base común a los dos casos.
-- Este script se ejecuta automáticamente SOLO cuando el volumen de la base
-- de datos se crea por primera vez. Si lo modifica, recree el volumen:
--     docker compose down -v && docker compose up --build
--
-- Agregue las tablas de sus módulos en archivos nuevos de esta carpeta,
-- por ejemplo 02-modulos.sql (se ejecutan en orden alfabético).

CREATE TABLE IF NOT EXISTS cuentas (
    id             BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    nombre         VARCHAR(120)  NOT NULL,
    email          VARCHAR(254)  NOT NULL,
    password_hash  VARCHAR(255)  NOT NULL,
    -- Los roles válidos dependen del caso: ver casos/<caso>/caso.json
    rol            VARCHAR(30)   NOT NULL,
    estado         ENUM('pendiente', 'activo', 'rechazado', 'suspendido') NOT NULL DEFAULT 'pendiente',
    creado_en      TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_cuentas_email UNIQUE (email),
    INDEX ix_cuentas_estado (estado)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
