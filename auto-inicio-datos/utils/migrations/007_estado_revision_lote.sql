-- Resolver un conflicto no debe dejar bloqueada para siempre la cartera,
-- ni borrar una revisión de datos que existía antes de recibir el lote.
ALTER TABLE prioridades_publicadas ADD COLUMN revision_antes_conflicto boolean;

CREATE FUNCTION recordar_revision_lote() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.conflicto_lote AND NOT OLD.conflicto_lote
       AND to_regclass('crm_estadooperativolead') IS NOT NULL THEN
        EXECUTE 'SELECT requiere_revision FROM crm_estadooperativolead
                 WHERE empresa_id=$1 AND lead_consolidado_id=$2'
        INTO NEW.revision_antes_conflicto
        USING NEW.empresa_id,NEW.lead_consolidado_id;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER recordar_revision_lote
    BEFORE UPDATE ON prioridades_publicadas
    FOR EACH ROW EXECUTE FUNCTION recordar_revision_lote();

CREATE FUNCTION restaurar_revision_lote() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.conflicto_lote AND NOT NEW.conflicto_lote
       AND to_regclass('crm_estadooperativolead') IS NOT NULL THEN
        EXECUTE 'UPDATE crm_estadooperativolead
            SET requiere_revision=$3 OR EXISTS (
                SELECT 1 FROM priorizaciones WHERE priorizacion_id=$4
                AND cola LIKE ''revision%''
            ) WHERE empresa_id=$1 AND lead_consolidado_id=$2
              AND revision_entrada=$5'
        USING NEW.empresa_id,NEW.lead_consolidado_id,
              COALESCE(OLD.revision_antes_conflicto,true),
              NEW.priorizacion_id,NEW.revision_entrada;
    END IF;
    RETURN NEW;
END $$;
-- PostgreSQL ejecuta triggers del mismo evento por orden alfabético:
-- primero sincronizar, después restaurar el estado previo a este conflicto.
CREATE TRIGGER z_restaurar_revision_lote
    AFTER UPDATE ON prioridades_publicadas
    FOR EACH ROW EXECUTE FUNCTION restaurar_revision_lote();
