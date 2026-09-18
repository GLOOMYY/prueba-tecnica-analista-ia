-- Ejecutar una vez como administrador de PostgreSQL, fuera de Django.
-- Reemplazar plataforma_web por un rol LOGIN de aplicación, sin BYPASSRLS,
-- CREATEDB, CREATEROLE ni propiedad de tablas. No incluir contraseñas aquí.

GRANT USAGE ON SCHEMA crm TO plataforma_web;
GRANT SELECT, INSERT, UPDATE, DELETE
    ON TABLE
        crm_asignaciondiaria,
        crm_capturaestructurada,
        crm_capturarevision,
        crm_estadooperativolead,
        crm_eventoauditoria,
        crm_gestioncomercial,
        crm_solicitudidempotente,
        crm_trabajoprocesamiento
    TO plataforma_web;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA crm TO plataforma_web;

-- El rol de carga y el rol de migración se aprovisionan por separado. El rol
-- web no recibe ownership de tablas ni privilegios globales sobre el esquema.
