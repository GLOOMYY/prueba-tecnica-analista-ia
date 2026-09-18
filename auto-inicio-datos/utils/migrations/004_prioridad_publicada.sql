-- Una sola referencia publicada, independiente de cuándo termina un proceso.
ALTER TABLE priorizaciones ADD CONSTRAINT prioridad_empresa_lead_id_unica
    UNIQUE (empresa_id, lead_consolidado_id, priorizacion_id);
CREATE TABLE prioridades_publicadas (
    empresa_id text NOT NULL,
    lead_consolidado_id text NOT NULL,
    priorizacion_id text NOT NULL,
    revision_entrada integer NOT NULL CHECK (revision_entrada > 0),
    origen text NOT NULL,
    conflicto_lote boolean NOT NULL DEFAULT false,
    PRIMARY KEY (empresa_id, lead_consolidado_id),
    FOREIGN KEY (empresa_id, lead_consolidado_id, priorizacion_id)
        REFERENCES priorizaciones
            (empresa_id, lead_consolidado_id, priorizacion_id)
);
INSERT INTO prioridades_publicadas
    (empresa_id, lead_consolidado_id, priorizacion_id, revision_entrada, origen)
SELECT p.empresa_id, p.lead_consolidado_id, p.priorizacion_id, 1,
    CASE WHEN e.etapa = 'clasificacion_importada' THEN 'lote'
         ELSE 'captura_manual' END
FROM v_prioridad_vigente p JOIN ejecuciones e USING (ejecucion_id);

ALTER TABLE prioridades_publicadas ENABLE ROW LEVEL SECURITY;
CREATE POLICY web_empresa ON prioridades_publicadas
    USING (empresa_id = current_setting('app.empresa_id', true))
    WITH CHECK (empresa_id = current_setting('app.empresa_id', true));

CREATE OR REPLACE VIEW v_prioridad_vigente WITH (security_invoker = true) AS
    SELECT p.* FROM priorizaciones p
    JOIN prioridades_publicadas v
      ON (v.empresa_id, v.lead_consolidado_id, v.priorizacion_id) =
         (p.empresa_id, p.lead_consolidado_id, p.priorizacion_id)
    JOIN ejecuciones e USING (ejecucion_id)
    WHERE e.estado = 'completada';

CREATE FUNCTION sincronizar_prioridad_operativa() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    -- El pipeline también funciona antes de instalar las tablas Django.
    IF to_regclass('crm_estadooperativolead') IS NOT NULL THEN
        EXECUTE '
            INSERT INTO crm_estadooperativolead
                (empresa_id, lead_consolidado_id, estado, revision_entrada,
                 priorizacion_vigente_id, priorizacion_revision_entrada,
                 priorizacion_origen, requiere_revision,
                 creado_en, actualizado_en)
            VALUES ($1,$2,''abierto'',$3,$4,$3,$5,$6,now(),now())
            ON CONFLICT (empresa_id,lead_consolidado_id) DO UPDATE SET
                revision_entrada = EXCLUDED.revision_entrada,
                priorizacion_vigente_id = EXCLUDED.priorizacion_vigente_id,
                priorizacion_revision_entrada = EXCLUDED.revision_entrada,
                priorizacion_origen = EXCLUDED.priorizacion_origen,
                requiere_revision = crm_estadooperativolead.requiere_revision
                    OR EXCLUDED.requiere_revision,
                actualizado_en = now()
            WHERE crm_estadooperativolead.revision_entrada
                <= EXCLUDED.revision_entrada'
        USING NEW.empresa_id, NEW.lead_consolidado_id, NEW.revision_entrada,
              NEW.priorizacion_id, NEW.origen, NEW.conflicto_lote;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER publicar_estado_operativo
    AFTER INSERT OR UPDATE ON prioridades_publicadas
    FOR EACH ROW EXECUTE FUNCTION sincronizar_prioridad_operativa();
