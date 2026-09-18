-- Ejecutar una vez como administrador de PostgreSQL, fuera de Django.
-- Reemplazar plataforma_web por un rol LOGIN de aplicación, sin BYPASSRLS,
-- CREATEDB, CREATEROLE ni propiedad de tablas. No incluir contraseñas aquí.

GRANT USAGE ON SCHEMA crm TO plataforma_web;
SET search_path TO crm, pg_catalog;
GRANT SELECT ON empresas, puntos_venta, asesores, marcas, modelos_moto,
    disponibilidad_modelo, conversaciones, mensajes, v_prioridad_vigente,
    v_leads_actuales, v_conversaciones_utilizables, v_cola_priorizada
    TO plataforma_web;
GRANT SELECT, INSERT ON leads, consultas, priorizaciones, ejecuciones,
    extracciones_ia, intereses_modelo TO plataforma_web;
GRANT SELECT, INSERT, UPDATE ON prioridades_publicadas TO plataforma_web;
GRANT SELECT ON cuentas_usuario, cuentas_membresiaempresa, auth_group,
    auth_permission, cuentas_usuario_groups, cuentas_usuario_user_permissions,
    auth_group_permissions, django_content_type, authtoken_token
    TO plataforma_web;
GRANT UPDATE (last_login) ON cuentas_usuario TO plataforma_web;
GRANT SELECT, INSERT, UPDATE, DELETE ON django_session TO plataforma_web;
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
