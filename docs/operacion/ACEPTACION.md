# Checklist de aceptación

## Evidencia local disponible

- Ruff, `manage.py check`, pruebas Django y pruebas del pipeline.
- Reglas de identidad y prioridad compartidas.
- RLS y migraciones SQL preparados, sin aplicación remota declarada.
- API, tablero, cola y gestión sobre tablas operativas locales.

## Antes de la demo final

- [ ] Aplicar migraciones y probar RLS con tres empresas en PostgreSQL.
- [ ] Completar adaptador transaccional de alta y prueba de recarga del lote.
- [ ] Conectar worker a Gemini y comprobar reintentos/cuotas.
- [ ] Desplegar web y disparador en proveedor elegido.
- [ ] Probar URL externa, API autenticada, estáticos y recuperación.
- [ ] Ejecutar escenarios AC01–AC20 con datos sintéticos.
