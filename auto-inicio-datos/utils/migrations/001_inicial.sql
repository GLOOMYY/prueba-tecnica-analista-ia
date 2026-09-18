-- Migración inmutable. El ejecutor fija search_path al esquema privado.
-- Veinte tablas de dominio; el ejecutor administra schema_migrations aparte.

CREATE TABLE empresas (
    empresa_id text PRIMARY KEY,
    nombre text
);

CREATE TABLE puntos_venta (
    punto_venta_id text PRIMARY KEY,
    empresa_id text NOT NULL REFERENCES empresas,
    nombre text,
    ubicacion text,
    UNIQUE (empresa_id, punto_venta_id)
);

CREATE TABLE asesores (
    asesor_id text PRIMARY KEY,
    empresa_id text NOT NULL REFERENCES empresas,
    punto_venta_id text NOT NULL,
    nombre text NOT NULL,
    capacidad_diaria_leads integer CHECK (capacidad_diaria_leads >= 0),
    activo boolean,
    fecha_ingreso date,
    fecha_ingreso_hora time,
    fecha_ingreso_precision text,
    datos_originales jsonb NOT NULL,
    FOREIGN KEY (empresa_id, punto_venta_id)
        REFERENCES puntos_venta (empresa_id, punto_venta_id)
);

CREATE TABLE marcas (
    marca_id text PRIMARY KEY,
    nombre text NOT NULL UNIQUE
);

CREATE TABLE modelos_moto (
    sku text PRIMARY KEY,
    marca_id text NOT NULL REFERENCES marcas,
    linea text NOT NULL,
    cilindraje integer CHECK (cilindraje >= 0),
    segmento text,
    precio_lista numeric(18,2) CHECK (precio_lista >= 0),
    unidades_disponibles integer CHECK (unidades_disponibles >= 0),
    datos_originales jsonb NOT NULL
);

CREATE TABLE disponibilidad_modelo (
    sku text REFERENCES modelos_moto,
    punto_venta_id text REFERENCES puntos_venta,
    PRIMARY KEY (sku, punto_venta_id)
);

CREATE TABLE leads (
    lead_consolidado_id text PRIMARY KEY,
    empresa_id text NOT NULL REFERENCES empresas,
    nombre_presentacion text,
    primera_fecha_registro date,
    primera_fecha_registro_hora time,
    primera_fecha_registro_precision text,
    ultima_fecha_registro date,
    ultima_fecha_registro_hora time,
    ultima_fecha_registro_precision text,
    reglas_identidad jsonb NOT NULL,
    datos_originales jsonb NOT NULL,
    UNIQUE (empresa_id, lead_consolidado_id)
);

CREATE TABLE consultas (
    lead_id_origen text PRIMARY KEY,
    lead_consolidado_id text NOT NULL,
    empresa_id text NOT NULL REFERENCES empresas,
    punto_venta_id text,
    canal text,
    campania text,
    nombre_declarado text,
    telefono text,
    email text,
    ciudad text,
    modelo_declarado text,
    modelo_sku text REFERENCES modelos_moto,
    estado_gestion text,
    fecha_registro date,
    fecha_registro_hora time,
    fecha_registro_precision text,
    fecha_primer_contacto date,
    fecha_primer_contacto_hora time,
    fecha_primer_contacto_precision text,
    calidad jsonb NOT NULL,
    datos_originales jsonb NOT NULL,
    FOREIGN KEY (empresa_id, lead_consolidado_id)
        REFERENCES leads (empresa_id, lead_consolidado_id),
    FOREIGN KEY (empresa_id, punto_venta_id)
        REFERENCES puntos_venta (empresa_id, punto_venta_id),
    UNIQUE (empresa_id, lead_id_origen),
    UNIQUE (empresa_id, lead_consolidado_id, lead_id_origen)
);

CREATE TABLE conversaciones (
    conversacion_id text PRIMARY KEY,
    lead_id_origen text NOT NULL,
    lead_consolidado_id text NOT NULL,
    empresa_id text NOT NULL REFERENCES empresas,
    canal text,
    fecha_inicio date,
    fecha_inicio_hora time,
    fecha_inicio_precision text,
    lead_id_recibido text,
    descartada boolean NOT NULL,
    motivos_descarte jsonb NOT NULL DEFAULT '[]',
    fecha_descarte timestamptz,
    politica_descarte text,
    datos_originales jsonb NOT NULL,
    CHECK (jsonb_typeof(motivos_descarte) = 'array'),
    CHECK (NOT descartada OR jsonb_array_length(motivos_descarte) > 0),
    FOREIGN KEY (empresa_id, lead_consolidado_id, lead_id_origen)
        REFERENCES consultas
            (empresa_id, lead_consolidado_id, lead_id_origen),
    UNIQUE (empresa_id, lead_consolidado_id, conversacion_id),
    UNIQUE (empresa_id, lead_consolidado_id, lead_id_origen, conversacion_id)
);

CREATE TABLE mensajes (
    mensaje_id text PRIMARY KEY,
    conversacion_id text NOT NULL REFERENCES conversaciones,
    posicion integer NOT NULL CHECK (posicion > 0),
    emisor text NOT NULL,
    hora_original text,
    texto text NOT NULL,
    UNIQUE (conversacion_id, posicion)
);

CREATE TABLE ejecuciones (
    ejecucion_id text PRIMARY KEY,
    etapa text NOT NULL,
    version_codigo text NOT NULL,
    huella_entrada text NOT NULL,
    importada boolean NOT NULL DEFAULT false,
    inicio timestamptz,
    fin timestamptz,
    estado text NOT NULL CHECK (estado IN ('completada', 'en_curso', 'fallida')),
    configuracion jsonb NOT NULL,
    conteos jsonb NOT NULL,
    errores jsonb NOT NULL DEFAULT '[]',
    registrada_en timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE extracciones_ia (
    extraccion_id text PRIMARY KEY,
    conversacion_id text NOT NULL REFERENCES conversaciones,
    ejecucion_id text NOT NULL REFERENCES ejecuciones,
    proveedor text NOT NULL,
    modelo_ia text NOT NULL,
    version_prompt text NOT NULL,
    version_normalizador text NOT NULL,
    estado_validacion text,
    revision_semantica text,
    huella_conversacion text,
    huella_configuracion text,
    resultado jsonb NOT NULL,
    datos_originales jsonb NOT NULL,
    UNIQUE (conversacion_id, ejecucion_id)
);

CREATE TABLE intereses_modelo (
    interes_id text PRIMARY KEY,
    extraccion_id text NOT NULL REFERENCES extracciones_ia,
    texto_mencionado text NOT NULL,
    modelo_sku text REFERENCES modelos_moto,
    estado_identificacion text NOT NULL,
    evidencias jsonb NOT NULL
);

CREATE TABLE modelos_ml (
    modelo_ml_id text PRIMARY KEY,
    ejecucion_id text NOT NULL REFERENCES ejecuciones,
    algoritmo text NOT NULL,
    version text NOT NULL,
    ruta_artefacto text NOT NULL,
    hash_artefacto text NOT NULL,
    estado text NOT NULL,
    configuracion jsonb NOT NULL,
    metricas jsonb NOT NULL,
    limitaciones jsonb NOT NULL
);

CREATE TABLE priorizaciones (
    priorizacion_id text PRIMARY KEY,
    lead_consolidado_id text NOT NULL,
    empresa_id text NOT NULL REFERENCES empresas,
    ejecucion_id text NOT NULL REFERENCES ejecuciones,
    lead_id_contexto text,
    conversacion_id_contexto text,
    modelo_ml_id text REFERENCES modelos_ml,
    score_prioridad numeric(8,4) NOT NULL CHECK (score_prioridad BETWEEN 0 AND 100),
    score_modelo_experimental numeric(8,4)
        CHECK (score_modelo_experimental BETWEEN 0 AND 100),
    temperatura text NOT NULL,
    cola text NOT NULL,
    explicacion text NOT NULL,
    accion_sugerida text,
    version_reglas text NOT NULL,
    contexto jsonb NOT NULL,
    datos_originales jsonb NOT NULL,
    FOREIGN KEY (empresa_id, lead_consolidado_id)
        REFERENCES leads (empresa_id, lead_consolidado_id),
    FOREIGN KEY (empresa_id, lead_consolidado_id, lead_id_contexto)
        REFERENCES consultas
            (empresa_id, lead_consolidado_id, lead_id_origen),
    FOREIGN KEY (empresa_id, lead_consolidado_id, conversacion_id_contexto)
        REFERENCES conversaciones
            (empresa_id, lead_consolidado_id, conversacion_id),
    FOREIGN KEY (empresa_id, lead_consolidado_id, lead_id_contexto,
                 conversacion_id_contexto)
        REFERENCES conversaciones
            (empresa_id, lead_consolidado_id, lead_id_origen, conversacion_id),
    CHECK (conversacion_id_contexto IS NULL OR lead_id_contexto IS NOT NULL),
    CHECK (score_modelo_experimental IS NULL OR modelo_ml_id IS NOT NULL),
    UNIQUE (empresa_id, lead_consolidado_id, ejecucion_id)
);

CREATE TABLE historico_cierres (
    historico_id text PRIMARY KEY,
    empresa_id text NOT NULL REFERENCES empresas,
    punto_venta_id text,
    modelo_sku text REFERENCES modelos_moto,
    modelo_cotizado text,
    fecha_registro date,
    fecha_registro_hora time,
    fecha_registro_precision text,
    canal text,
    precio_lista numeric(18,2) CHECK (precio_lista >= 0),
    horas_al_primer_contacto numeric CHECK (horas_al_primer_contacto >= 0),
    numero_contactos integer CHECK (numero_contactos >= 0),
    manifesto_cuota_inicial text,
    forma_pago_declarada text,
    pidio_cita text,
    desenlace text CHECK (desenlace IN ('Cerrado', 'Perdido', 'Sin gestión')),
    datos_originales jsonb NOT NULL,
    FOREIGN KEY (empresa_id, punto_venta_id)
        REFERENCES puntos_venta (empresa_id, punto_venta_id)
);

CREATE TABLE archivos_fuente (
    archivo_id text PRIMARY KEY,
    nombre text NOT NULL,
    ruta text NOT NULL,
    hash_contenido text NOT NULL,
    UNIQUE (ruta, hash_contenido)
);

CREATE TABLE ejecucion_archivos (
    ejecucion_id text REFERENCES ejecuciones,
    archivo_id text REFERENCES archivos_fuente,
    funcion text NOT NULL,
    PRIMARY KEY (ejecucion_id, archivo_id)
);

CREATE TABLE trazabilidad_registros (
    trazabilidad_id text PRIMARY KEY,
    archivo_id text NOT NULL REFERENCES archivos_fuente,
    ejecucion_id text NOT NULL REFERENCES ejecuciones,
    empresa_id text REFERENCES empresas,
    referencia_origen text NOT NULL,
    entidad_destino text,
    identificador_destino text,
    accion text NOT NULL,
    motivo text,
    detalle jsonb NOT NULL
);

CREATE TABLE incidencias (
    incidencia_id text PRIMARY KEY,
    ejecucion_id text NOT NULL REFERENCES ejecuciones,
    empresa_id text REFERENCES empresas,
    entidad_afectada text,
    identificador_afectado text,
    campo text,
    tipo text NOT NULL,
    decision text,
    estado text,
    fecha timestamptz,
    antes jsonb,
    despues jsonb,
    detalle jsonb NOT NULL
);

CREATE INDEX conversaciones_empresa_descarte
    ON conversaciones (empresa_id, descartada);
CREATE INDEX consultas_empresa_lead
    ON consultas (empresa_id, lead_consolidado_id);
CREATE INDEX consultas_empresa_fecha ON consultas (empresa_id, fecha_registro);
CREATE INDEX intereses_modelo_sku ON intereses_modelo (modelo_sku, extraccion_id);
CREATE INDEX prioridades_cola
    ON priorizaciones (empresa_id, ejecucion_id, cola, score_prioridad DESC);
CREATE INDEX historico_empresa_fecha
    ON historico_cierres (empresa_id, fecha_registro);
CREATE INDEX incidencias_empresa_estado ON incidencias (empresa_id, estado, tipo);

CREATE VIEW v_leads_actuales WITH (security_invoker = true) AS
    SELECT l.*, COALESCE(c.contactos, '[]'::jsonb) AS contactos
    FROM leads l
    LEFT JOIN LATERAL (
        SELECT jsonb_agg(jsonb_build_object(
            'lead_id_origen', q.lead_id_origen, 'telefono', q.telefono,
            'email', q.email, 'ciudad', q.ciudad
        ) ORDER BY q.lead_id_origen) AS contactos
        FROM consultas q
        WHERE q.empresa_id = l.empresa_id
          AND q.lead_consolidado_id = l.lead_consolidado_id
    ) c ON true;

CREATE VIEW v_conversaciones_utilizables WITH (security_invoker = true) AS
    SELECT * FROM conversaciones WHERE descartada = false;

-- La carga es una instantánea completa de las empresas entregadas.
-- Una ejecución importada finalizada solo se ve después del COMMIT de la carga.
CREATE VIEW v_prioridad_vigente WITH (security_invoker = true) AS
    SELECT p.* FROM priorizaciones p
    WHERE p.ejecucion_id = (
        SELECT e.ejecucion_id FROM ejecuciones e
        WHERE e.etapa = 'clasificacion_importada' AND e.estado = 'completada'
        ORDER BY e.registrada_en DESC, e.ejecucion_id DESC LIMIT 1
    );

CREATE VIEW v_cola_priorizada WITH (security_invoker = true) AS
    SELECT p.*, row_number() OVER (
        PARTITION BY p.empresa_id, p.cola
        ORDER BY p.score_prioridad DESC,
            l.primera_fecha_registro ASC NULLS LAST,
            l.primera_fecha_registro_hora ASC NULLS FIRST,
            p.lead_consolidado_id
    ) AS posicion_en_cola_empresa
    FROM v_prioridad_vigente p
    JOIN leads l ON l.empresa_id = p.empresa_id
        AND l.lead_consolidado_id = p.lead_consolidado_id;
