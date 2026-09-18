-- Aislamiento del histórico para un rol web sin propiedad ni BYPASSRLS.
-- Las ejecuciones por lote pueden abarcar empresas; las nuevas ejecuciones
-- web declaran su empresa. Las tablas operativas mantienen migraciones Django.
ALTER TABLE ejecuciones ADD COLUMN empresa_id text REFERENCES empresas;

DO $$
DECLARE tabla text;
BEGIN
    FOREACH tabla IN ARRAY ARRAY[
        'empresas', 'puntos_venta', 'asesores', 'leads', 'consultas',
        'conversaciones', 'priorizaciones', 'historico_cierres',
        'incidencias', 'trazabilidad_registros'
    ] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', tabla);
        EXECUTE format(
            'CREATE POLICY web_empresa ON %I '
            'USING (empresa_id = current_setting(''app.empresa_id'', true)) '
            'WITH CHECK (empresa_id = current_setting(''app.empresa_id'', true))',
            tabla
        );
    END LOOP;
END $$;

CREATE POLICY web_conversacion ON mensajes
    USING (EXISTS (
        SELECT 1 FROM conversaciones c
        WHERE c.conversacion_id = mensajes.conversacion_id
          AND c.empresa_id = current_setting('app.empresa_id', true)
    ));
CREATE POLICY web_extraccion ON extracciones_ia
    USING (EXISTS (
        SELECT 1 FROM conversaciones c
        WHERE c.conversacion_id = extracciones_ia.conversacion_id
          AND c.empresa_id = current_setting('app.empresa_id', true)
    ));
CREATE POLICY web_interes ON intereses_modelo
    USING (EXISTS (
        SELECT 1 FROM extracciones_ia e
        WHERE e.extraccion_id = intereses_modelo.extraccion_id
    ));
CREATE POLICY web_disponibilidad ON disponibilidad_modelo
    FOR SELECT USING (EXISTS (
        SELECT 1 FROM puntos_venta p
        WHERE p.punto_venta_id = disponibilidad_modelo.punto_venta_id
          AND p.empresa_id = current_setting('app.empresa_id', true)
    ));
CREATE POLICY web_catalogo ON modelos_moto FOR SELECT
    USING (current_setting('app.empresa_id', true) <> '');
CREATE POLICY web_marcas ON marcas FOR SELECT
    USING (current_setting('app.empresa_id', true) <> '');
CREATE POLICY web_ejecucion_lectura ON ejecuciones FOR SELECT
    USING (
        empresa_id = current_setting('app.empresa_id', true)
        OR EXISTS (
            SELECT 1 FROM priorizaciones p
            WHERE p.ejecucion_id = ejecuciones.ejecucion_id
              AND p.empresa_id = current_setting('app.empresa_id', true)
        )
    );
CREATE POLICY web_ejecucion_insertar ON ejecuciones FOR INSERT
    WITH CHECK (empresa_id = current_setting('app.empresa_id', true));
