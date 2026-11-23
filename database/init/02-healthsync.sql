-- Esquema del caso HealthSync (módulos de negocio).
-- Se ejecuta después de 01-esquema-base.sql, solo al crear el volumen de la base de datos.
--
-- Convenciones:
--   * Todas las fechas y horas se guardan en UTC.
--   * Los saldos y puntos son UNSIGNED: la base de datos rechaza un valor negativo
--     aunque falle una validación de la aplicación (defensa en profundidad).
--   * Las tablas de movimientos son un libro contable: solo se insertan filas.

-- ---------------------------------------------------------------------------
-- Extensión de la tabla base de cuentas
-- ---------------------------------------------------------------------------
ALTER TABLE cuentas
    ADD COLUMN fecha_nacimiento  DATE              NULL AFTER rol,
    ADD COLUMN codigo_referido   CHAR(10)          NULL,
    ADD COLUMN intentos_fallidos TINYINT UNSIGNED  NOT NULL DEFAULT 0,
    ADD COLUMN bloqueado_hasta   DATETIME          NULL,
    ADD COLUMN version_sesion    INT UNSIGNED      NOT NULL DEFAULT 0,
    ADD CONSTRAINT uq_cuentas_codigo_referido UNIQUE (codigo_referido);

-- ---------------------------------------------------------------------------
-- Módulo 1: registro y verificación
-- ---------------------------------------------------------------------------

-- Datos propios de los profesionales de salud y estado de su verificación.
CREATE TABLE perfiles_profesionales (
    cuenta_id        BIGINT UNSIGNED NOT NULL PRIMARY KEY,
    especialidad     VARCHAR(80)     NOT NULL DEFAULT 'Medicina general',
    descripcion      VARCHAR(500)    NOT NULL DEFAULT '',
    tarifa_creditos  INT UNSIGNED    NOT NULL DEFAULT 20,
    -- Foto de la tarjeta profesional: nombre aleatorio del archivo en disco y su tipo.
    tarjeta_archivo  VARCHAR(64)     NULL,
    tarjeta_mime     VARCHAR(30)     NULL,
    -- Resultado de la revisión: quién validó (administrador o robot) y cuándo.
    revisado_por     BIGINT UNSIGNED NULL,
    revisado_por_bot TINYINT(1)      NOT NULL DEFAULT 0,
    revisado_en      DATETIME        NULL,
    motivo_rechazo   VARCHAR(300)    NULL,
    CONSTRAINT fk_perfil_cuenta   FOREIGN KEY (cuenta_id)    REFERENCES cuentas (id) ON DELETE CASCADE,
    CONSTRAINT fk_perfil_revisor  FOREIGN KEY (revisado_por) REFERENCES cuentas (id) ON DELETE SET NULL,
    CONSTRAINT ck_perfil_tarifa   CHECK (tarifa_creditos BETWEEN 1 AND 1000)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Saldo de créditos, puntos de referidos y suscripción premium de cada cuenta activa.
CREATE TABLE billeteras (
    cuenta_id      BIGINT UNSIGNED NOT NULL PRIMARY KEY,
    saldo_creditos INT UNSIGNED    NOT NULL DEFAULT 0,
    puntos         INT UNSIGNED    NOT NULL DEFAULT 0,
    premium_hasta  DATE            NULL,
    CONSTRAINT fk_billetera_cuenta FOREIGN KEY (cuenta_id) REFERENCES cuentas (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Programa de referidos: una fila por cuenta que se registró con un código.
CREATE TABLE referidos (
    id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    referidor_id  BIGINT UNSIGNED NOT NULL,
    referido_id   BIGINT UNSIGNED NOT NULL,
    estado        ENUM('pendiente', 'completado', 'cancelado') NOT NULL DEFAULT 'pendiente',
    puntos        INT UNSIGNED    NOT NULL DEFAULT 0,
    creado_en     TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completado_en DATETIME        NULL,
    CONSTRAINT uq_referidos_referido UNIQUE (referido_id),
    INDEX ix_referidos_referidor (referidor_id),
    CONSTRAINT fk_referidos_referidor FOREIGN KEY (referidor_id) REFERENCES cuentas (id) ON DELETE CASCADE,
    CONSTRAINT fk_referidos_referido  FOREIGN KEY (referido_id)  REFERENCES cuentas (id) ON DELETE CASCADE
    -- Que alguien no se refiera a sí mismo lo garantiza la aplicación: el código solo existe en cuentas ya activas.
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Libro de puntos (positivo = ganados, negativo = canjeados).
CREATE TABLE movimientos_puntos (
    id         BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    cuenta_id  BIGINT UNSIGNED NOT NULL,
    tipo       ENUM('referido', 'canje') NOT NULL,
    puntos     INT             NOT NULL,
    referencia VARCHAR(60)     NULL,
    creado_en  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_mov_puntos_cuenta (cuenta_id, id),
    CONSTRAINT fk_mov_puntos_cuenta FOREIGN KEY (cuenta_id) REFERENCES cuentas (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------------
-- Libro de créditos (compartido por transferencias, consultas y bonos)
-- ---------------------------------------------------------------------------
CREATE TABLE movimientos_credito (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    cuenta_id       BIGINT UNSIGNED NOT NULL,
    tipo            ENUM('bono', 'transferencia_enviada', 'transferencia_recibida',
                         'pago_consulta', 'cobro_consulta', 'reembolso_consulta') NOT NULL,
    -- Positivo = entra saldo, negativo = sale saldo.
    monto           INT             NOT NULL,
    saldo_posterior INT UNSIGNED    NOT NULL,
    contraparte_id  BIGINT UNSIGNED NULL,
    referencia      VARCHAR(60)     NULL,
    nota            VARCHAR(140)    NULL,
    creado_en       TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_mov_credito_cuenta (cuenta_id, id),
    CONSTRAINT fk_mov_credito_cuenta FOREIGN KEY (cuenta_id) REFERENCES cuentas (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------------
-- Módulo 2: wearables
-- ---------------------------------------------------------------------------
CREATE TABLE dispositivos (
    id                    BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    paciente_id           BIGINT UNSIGNED NOT NULL,
    nombre                VARCHAR(80)     NOT NULL,
    proveedor             VARCHAR(40)     NOT NULL,
    -- Identificador que se envía a la API externa (no es dato personal).
    id_externo            VARCHAR(64)     NOT NULL,
    vinculado_en          TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ultima_sincronizacion DATETIME        NULL,
    CONSTRAINT uq_dispositivos_externo UNIQUE (id_externo),
    INDEX ix_dispositivos_paciente (paciente_id),
    CONSTRAINT fk_dispositivos_paciente FOREIGN KEY (paciente_id) REFERENCES cuentas (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Métricas de salud normalizadas. El nombre del tipo es el esquema de Open mHealth.
CREATE TABLE metricas (
    id             BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    paciente_id    BIGINT UNSIGNED NOT NULL,
    dispositivo_id BIGINT UNSIGNED NULL,
    tipo           ENUM('heart-rate', 'step-count', 'oxygen-saturation', 'sleep-duration') NOT NULL,
    valor          DECIMAL(10, 2)  NOT NULL,
    unidad         VARCHAR(20)     NOT NULL,
    medido_en      DATETIME        NOT NULL,
    fuente         ENUM('wearable', 'manual') NOT NULL DEFAULT 'wearable',
    -- Identificador de la lectura en la API externa (trazabilidad).
    origen_id      VARCHAR(64)     NULL,
    creado_en      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- Una lectura por dispositivo, tipo y momento: sincronizar dos veces no duplica datos.
    CONSTRAINT uq_metricas_lectura UNIQUE (dispositivo_id, tipo, medido_en),
    INDEX ix_metricas_paciente_tipo (paciente_id, tipo, medido_en),
    CONSTRAINT fk_metricas_paciente    FOREIGN KEY (paciente_id)    REFERENCES cuentas (id) ON DELETE CASCADE,
    CONSTRAINT fk_metricas_dispositivo FOREIGN KEY (dispositivo_id) REFERENCES dispositivos (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------------
-- Módulo 3: consultas médicas virtuales
-- ---------------------------------------------------------------------------
CREATE TABLE consultas (
    id                     BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    paciente_id            BIGINT UNSIGNED NOT NULL,
    profesional_id         BIGINT UNSIGNED NOT NULL,
    inicio                 DATETIME        NOT NULL,
    motivo                 VARCHAR(300)    NOT NULL,
    estado                 ENUM('confirmada', 'en_curso', 'completada', 'cancelada') NOT NULL DEFAULT 'confirmada',
    -- Créditos cobrados al paciente al confirmar. Quedan retenidos hasta completar o cancelar.
    costo_creditos         INT UNSIGNED    NOT NULL,
    -- Consentimiento explícito del paciente para que el profesional vea sus métricas.
    consentimiento_metricas TINYINT(1)     NOT NULL DEFAULT 0,
    consentimiento_en      DATETIME        NULL,
    diagnostico_resumido   VARCHAR(255)    NULL,
    notas_clinicas         TEXT            NULL,
    creado_en              TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en         TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX ix_consultas_paciente (paciente_id, inicio),
    INDEX ix_consultas_profesional (profesional_id, inicio),
    CONSTRAINT fk_consultas_paciente    FOREIGN KEY (paciente_id)    REFERENCES cuentas (id),
    CONSTRAINT fk_consultas_profesional FOREIGN KEY (profesional_id) REFERENCES cuentas (id),
    CONSTRAINT ck_consultas_distintos   CHECK (paciente_id <> profesional_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------------
-- Módulo 4: alertas de salud
-- ---------------------------------------------------------------------------
CREATE TABLE alertas (
    id                   BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    paciente_id          BIGINT UNSIGNED NOT NULL,
    tipo_metrica         ENUM('heart-rate', 'step-count', 'oxygen-saturation', 'sleep-duration') NOT NULL,
    operador             ENUM('mayor', 'menor') NOT NULL,
    umbral               DECIMAL(10, 2)  NOT NULL,
    activa               TINYINT(1)      NOT NULL DEFAULT 1,
    -- Autorización del paciente para avisar también a un profesional vinculado.
    notificar_profesional TINYINT(1)     NOT NULL DEFAULT 0,
    profesional_id       BIGINT UNSIGNED NULL,
    creado_en            TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_alertas_paciente (paciente_id),
    INDEX ix_alertas_activa (activa),
    CONSTRAINT fk_alertas_paciente    FOREIGN KEY (paciente_id)    REFERENCES cuentas (id) ON DELETE CASCADE,
    -- Sin acción ON DELETE: MySQL no permite un CHECK sobre una columna con acción referencial.
    CONSTRAINT fk_alertas_profesional FOREIGN KEY (profesional_id) REFERENCES cuentas (id),
    CONSTRAINT ck_alertas_profesional CHECK (notificar_profesional = 0 OR profesional_id IS NOT NULL)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Cada vez que el robot dispara una alerta se guarda una fila. La restricción única
-- garantiza que una misma lectura no genera dos avisos para la misma alerta.
CREATE TABLE alertas_disparos (
    id                  BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    alerta_id           BIGINT UNSIGNED NOT NULL,
    metrica_id          BIGINT UNSIGNED NOT NULL,
    paciente_id         BIGINT UNSIGNED NOT NULL,
    profesional_id      BIGINT UNSIGNED NULL,
    tipo_metrica        VARCHAR(30)     NOT NULL,
    operador            VARCHAR(10)     NOT NULL,
    umbral              DECIMAL(10, 2)  NOT NULL,
    valor               DECIMAL(10, 2)  NOT NULL,
    medido_en           DATETIME        NOT NULL,
    correo_paciente     TINYINT(1)      NOT NULL DEFAULT 0,
    correo_profesional  TINYINT(1)      NOT NULL DEFAULT 0,
    disparada_en        TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_disparos_alerta_metrica UNIQUE (alerta_id, metrica_id),
    INDEX ix_disparos_paciente (paciente_id, id),
    INDEX ix_disparos_profesional (profesional_id, id),
    CONSTRAINT fk_disparos_alerta  FOREIGN KEY (alerta_id)  REFERENCES alertas (id) ON DELETE CASCADE,
    CONSTRAINT fk_disparos_metrica FOREIGN KEY (metrica_id) REFERENCES metricas (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------------
-- Transversal: registro de eventos de seguridad
-- ---------------------------------------------------------------------------
CREATE TABLE eventos_seguridad (
    id        BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    cuenta_id BIGINT UNSIGNED NULL,
    evento    VARCHAR(40)     NOT NULL,
    detalle   VARCHAR(255)    NOT NULL DEFAULT '',
    ip        VARCHAR(45)     NULL,
    creado_en TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_eventos_cuenta (cuenta_id),
    INDEX ix_eventos_evento (evento, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
