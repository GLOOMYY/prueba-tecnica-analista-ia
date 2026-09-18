-- Presupuesto conservador compartido por lote y workers del mismo proyecto.
CREATE TABLE ia_reservas (modelo text NOT NULL, instante timestamptz NOT NULL);
CREATE INDEX ia_reservas_modelo_instante ON ia_reservas (modelo, instante);
REVOKE ALL ON ia_reservas FROM PUBLIC;
CREATE FUNCTION reservar_cuota_ia(modelo_solicitado text) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path FROM CURRENT AS $$
DECLARE ahora timestamptz := clock_timestamp();
BEGIN
    PERFORM pg_advisory_xact_lock(hashtext('crm_cuota_gemini'));
    IF (SELECT count(*) FROM ia_reservas
        WHERE modelo = modelo_solicitado AND instante > ahora - interval '24 hours') >= 240
       OR (SELECT count(*) FROM ia_reservas
        WHERE modelo = modelo_solicitado AND instante > ahora - interval '1 minute') >= 8 THEN
        RETURN false;
    END IF;
    INSERT INTO ia_reservas VALUES (modelo_solicitado, ahora);
    RETURN true;
END $$;
