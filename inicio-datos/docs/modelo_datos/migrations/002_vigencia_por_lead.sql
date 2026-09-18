-- Evolución aditiva: la carga histórica deja de ser la única fuente de vigencia.
-- Las altas web deberán declarar origen_registro = 'web'; no se modifica 001.

ALTER TABLE leads
    ADD COLUMN origen_registro text NOT NULL DEFAULT 'lote'
    CHECK (origen_registro IN ('lote', 'web'));

ALTER TABLE consultas
    ADD COLUMN origen_registro text NOT NULL DEFAULT 'lote'
    CHECK (origen_registro IN ('lote', 'web'));

CREATE INDEX leads_origen_registro_idx
    ON leads (origen_registro, empresa_id, lead_consolidado_id);
CREATE INDEX consultas_origen_registro_idx
    ON consultas (origen_registro, empresa_id, lead_consolidado_id);
CREATE INDEX prioridades_vigencia_lead_idx
    ON priorizaciones (empresa_id, lead_consolidado_id, ejecucion_id);

CREATE OR REPLACE VIEW v_prioridad_vigente WITH (security_invoker = true) AS
    SELECT DISTINCT ON (p.empresa_id, p.lead_consolidado_id) p.*
    FROM priorizaciones p
    JOIN ejecuciones e ON e.ejecucion_id = p.ejecucion_id
    WHERE e.estado = 'completada'
    ORDER BY p.empresa_id, p.lead_consolidado_id,
        e.registrada_en DESC, e.ejecucion_id DESC, p.priorizacion_id DESC;
