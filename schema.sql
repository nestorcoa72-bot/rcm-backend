-- ============================================================
-- RCM Motores — Esquema PostgreSQL
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ---------- VARIADORES DE FRECUENCIA ----------
CREATE TABLE variadores_vfd (
    id_variador         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    marca_modelo        VARCHAR(120) NOT NULL,
    frecuencia_portadora_khz FLOAT CHECK (frecuencia_portadora_khz > 0),
    filtro_dv_dt        BOOLEAN DEFAULT FALSE,
    filtro_modo_comun   BOOLEAN DEFAULT FALSE,
    creado_en           TIMESTAMPTZ DEFAULT now()
);

-- ---------- MOTORES ----------
CREATE TABLE motores (
    id_motor            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tag_equipo          VARCHAR(50) UNIQUE NOT NULL,
    potencia_kw         FLOAT NOT NULL CHECK (potencia_kw > 0),
    voltaje_v           INT NOT NULL,
    corriente_nominal_a FLOAT,
    rpm_nominal         INT NOT NULL,
    tipo_rodamiento_de  VARCHAR(60),
    tipo_rodamiento_nde VARCHAR(60),
    clase_aislamiento   VARCHAR(5) CHECK (clase_aislamiento IN ('B','F','H')),
    id_variador         UUID REFERENCES variadores_vfd(id_variador) ON DELETE SET NULL,
    criticidad          CHAR(1) NOT NULL CHECK (criticidad IN ('A','B','C')),
    fecha_instalacion   DATE NOT NULL,
    activo              BOOLEAN DEFAULT TRUE,
    creado_en           TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_motores_criticidad ON motores(criticidad) WHERE activo = TRUE;
CREATE INDEX idx_motores_variador ON motores(id_variador);

-- ---------- LECTURAS VFD EN EL TIEMPO (frecuencia real de operación) ----------
CREATE TABLE vfd_lecturas (
    id_lectura      BIGSERIAL PRIMARY KEY,
    id_motor        UUID NOT NULL REFERENCES motores(id_motor) ON DELETE CASCADE,
    fecha           TIMESTAMPTZ NOT NULL,
    frecuencia_hz   FLOAT,
    thd_v_pct       FLOAT,
    thd_i_pct       FLOAT
);
CREATE INDEX idx_vfd_lecturas_motor_fecha ON vfd_lecturas(id_motor, fecha DESC);

-- ---------- HISTORIAL OPERATIVO (series de tiempo de condición) ----------
CREATE TABLE historial_operativo (
    id_registro                 BIGSERIAL PRIMARY KEY,
    id_motor                    UUID NOT NULL REFERENCES motores(id_motor) ON DELETE CASCADE,
    fecha                       TIMESTAMPTZ NOT NULL,
    horas_operacion_acumuladas  FLOAT NOT NULL CHECK (horas_operacion_acumuladas >= 0),
    temperatura_carcasa_c       FLOAT,
    vibracion_mm_s              FLOAT,
    corriente_operativa_a       FLOAT
);
CREATE INDEX idx_historial_operativo_motor_fecha ON historial_operativo(id_motor, fecha DESC);
-- Consulta más frecuente del sistema: "última lectura de horas por motor"
CREATE INDEX idx_historial_operativo_horas ON historial_operativo(id_motor, horas_operacion_acumuladas DESC);

-- ---------- CATÁLOGO DE MODOS DE FALLA (AMEF) ----------
CREATE TABLE catalogo_modos_falla (
    id_modo             SERIAL PRIMARY KEY,
    clave               VARCHAR(30) UNIQUE NOT NULL,   -- ej. 'rodamientos'
    nombre              VARCHAR(150) NOT NULL,
    severidad_default   SMALLINT NOT NULL CHECK (severidad_default BETWEEN 1 AND 10),
    deteccion_default   SMALLINT NOT NULL CHECK (deteccion_default BETWEEN 1 AND 10),
    tecnica_deteccion   VARCHAR(200)
);

INSERT INTO catalogo_modos_falla (clave, nombre, severidad_default, deteccion_default, tecnica_deteccion) VALUES
('rodamientos',    'Falla de rodamientos (fatiga/lubricación)',              7, 3, 'Análisis de vibraciones'),
('aislamiento',    'Falla de aislamiento del devanado (dv/dt del VFD)',      9, 6, 'Termografía + resistencia de aislamiento (Megger)'),
('desalineacion',  'Desalineación eje motor-carga',                         5, 4, 'Análisis de vibraciones (1x RPM)'),
('desbalanceo',    'Desbalanceo de rotor',                                  5, 4, 'Análisis de vibraciones'),
('corrienteseje',  'Corrientes de eje (bearing currents por conmutación VFD)', 8, 7, 'Medición de corriente/voltaje de eje, análisis de grasa');

-- ---------- HISTORIAL DE FALLAS (dato central: alimenta Weibull) ----------
CREATE TABLE historial_fallas (
    id_falla                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    id_motor                    UUID NOT NULL REFERENCES motores(id_motor) ON DELETE CASCADE,
    id_modo                     INT NOT NULL REFERENCES catalogo_modos_falla(id_modo),
    fecha_falla                 TIMESTAMPTZ,                       -- NULL si censurado=TRUE
    horas_operacion_al_evento   FLOAT NOT NULL CHECK (horas_operacion_al_evento >= 0),
    fecha_fin_reparacion        TIMESTAMPTZ,
    causa_raiz                  TEXT,
    censurado                   BOOLEAN NOT NULL DEFAULT FALSE,     -- TRUE = sigue operando sin fallar
    creado_en                   TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT chk_fecha_falla CHECK (censurado = TRUE OR fecha_falla IS NOT NULL)
);
-- Índice clave: es la consulta que dispara el ajuste de Weibull en cada simulación
CREATE INDEX idx_historial_fallas_modo ON historial_fallas(id_modo, censurado);
CREATE INDEX idx_historial_fallas_motor ON historial_fallas(id_motor);

-- ---------- AMEF: OVERRIDES DE JUICIO EXPERTO POR MOTOR+MODO ----------
CREATE TABLE amef_overrides (
    id_motor        UUID NOT NULL REFERENCES motores(id_motor) ON DELETE CASCADE,
    id_modo         INT NOT NULL REFERENCES catalogo_modos_falla(id_modo),
    severidad       SMALLINT CHECK (severidad BETWEEN 1 AND 10),
    ocurrencia_manual SMALLINT CHECK (ocurrencia_manual BETWEEN 1 AND 10), -- solo si no hay datos suficientes
    deteccion       SMALLINT CHECK (deteccion BETWEEN 1 AND 10),
    actualizado_en  TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (id_motor, id_modo)
);

-- ---------- COSTOS ----------
CREATE TABLE costos (
    id_motor                    UUID PRIMARY KEY REFERENCES motores(id_motor) ON DELETE CASCADE,
    costo_hora_preventivo       NUMERIC(12,2) NOT NULL,
    costo_hora_correctivo       NUMERIC(12,2) NOT NULL,
    costo_hora_parada_produccion NUMERIC(12,2) NOT NULL,
    costo_mano_obra_hora        NUMERIC(12,2),
    actualizado_en              TIMESTAMPTZ DEFAULT now()
);

-- ---------- RESULTADOS DE SIMULACIÓN (cacheados para no recalcular en cada consulta) ----------
CREATE TABLE simulaciones_weibull (
    id_simulacion       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    id_modo             INT NOT NULL REFERENCES catalogo_modos_falla(id_modo),
    id_motor            UUID REFERENCES motores(id_motor) ON DELETE CASCADE, -- NULL = análisis a nivel flota
    beta                FLOAT NOT NULL,
    eta                 FLOAT NOT NULL,
    beta_ic_inferior    FLOAT,
    beta_ic_superior    FLOAT,
    n_fallas_usadas     INT NOT NULL,
    n_censurados_usados INT NOT NULL,
    mtbf_simulado       FLOAT,
    mttr_simulado       FLOAT,
    b10_life            FLOAT,
    n_iteraciones       INT NOT NULL,
    ejecutado_en        TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_simulaciones_modo_motor ON simulaciones_weibull(id_modo, id_motor, ejecutado_en DESC);

-- ---------- PLAN RCM GENERADO (auditoría de recomendaciones) ----------
CREATE TABLE planes_rcm (
    id_plan                 UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    id_simulacion           UUID NOT NULL REFERENCES simulaciones_weibull(id_simulacion),
    id_motor                UUID NOT NULL REFERENCES motores(id_motor) ON DELETE CASCADE,
    id_modo                 INT NOT NULL REFERENCES catalogo_modos_falla(id_modo),
    npr_calculado           INT NOT NULL,
    intervalo_optimo_horas  FLOAT NOT NULL,
    costo_total_esperado    NUMERIC(14,2) NOT NULL,
    estrategia              VARCHAR(60) NOT NULL,
    vigente                 BOOLEAN DEFAULT TRUE,
    generado_en             TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_planes_rcm_motor_vigente ON planes_rcm(id_motor, vigente);

-- ---------- COVARIABLES DEL EVENTO (para el modelo de Cox) ----------
-- Se registran junto con cada falla/censura: condición de operación real
-- en ese momento, no un promedio genérico. Esto es lo que permite responder
-- "¿qué pasa si cambio la frecuencia de conmutación?" en vez de solo
-- "¿cuándo va a fallar en promedio?"
CREATE TABLE covariables_evento (
    id_falla                UUID PRIMARY KEY REFERENCES historial_fallas(id_falla) ON DELETE CASCADE,
    frecuencia_khz          FLOAT,   -- frecuencia de conmutación del VFD en ese periodo
    thd_pct                 FLOAT,   -- distorsión armónica total promedio
    temperatura_promedio_c  FLOAT,   -- temperatura de carcasa promedio hasta el evento
    carga_relativa_pct      FLOAT    -- corriente operativa / corriente nominal, promedio
);
CREATE INDEX idx_covariables_evento_falla ON covariables_evento(id_falla);

-- ---------- RESULTADOS DE MODELOS DE COX (auditoría) ----------
CREATE TABLE modelos_cox (
    id_modelo           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    id_modo             INT NOT NULL REFERENCES catalogo_modos_falla(id_modo),
    covariables_usadas  TEXT[] NOT NULL,
    hazard_ratios       JSONB NOT NULL,   -- {"frecuencia_khz": 1.27, "thd_pct": 1.33, ...}
    p_values            JSONB NOT NULL,
    concordance_index   FLOAT NOT NULL,
    n_observaciones     INT NOT NULL,
    n_eventos           INT NOT NULL,
    ejecutado_en        TIMESTAMPTZ DEFAULT now()
);
CREATE VIEW v_amef_vivo AS
SELECT
    m.id_motor, m.tag_equipo, cmf.id_modo, cmf.nombre AS modo_falla,
    COALESCE(ov.severidad, cmf.severidad_default) AS severidad,
    COALESCE(ov.deteccion, cmf.deteccion_default) AS deteccion,
    ov.ocurrencia_manual
FROM motores m
CROSS JOIN catalogo_modos_falla cmf
LEFT JOIN amef_overrides ov ON ov.id_motor = m.id_motor AND ov.id_modo = cmf.id_modo
WHERE m.activo = TRUE;
