-- Sin una secuencia fiable de fuentes, un lote distinto requiere arbitraje.
ALTER TABLE prioridades_publicadas ADD COLUMN propuesta_lote_id text;
ALTER TABLE prioridades_publicadas ADD CONSTRAINT propuesta_misma_empresa
    FOREIGN KEY (empresa_id,lead_consolidado_id,propuesta_lote_id)
    REFERENCES priorizaciones
        (empresa_id,lead_consolidado_id,priorizacion_id);
