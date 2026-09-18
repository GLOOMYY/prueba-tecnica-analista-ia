# Estado de integración y evidencia

Actualizado el 2026-09-17. Render fue elegido; el usuario pospuso publicar y
conectar un repositorio. Este documento reemplaza afirmaciones previas de
«listo» que solo correspondían a código preliminar.

## Implementado y probado localmente

- Login/logout, elección de empresa y revalidación de membresías.
- Selectores comunes: asesor ve su cartera y capturas propias sin asignar;
  supervisor ve empresa; operador no tiene acceso comercial.
- Alta SQL atómica mediante API/formulario: lead, consulta, captura, prioridad,
  estado, auditoría y respuesta idempotente.
- Teléfono compartido incompatible: revisión persistida sin revelar candidato.
- Misma persona en distintas empresas: identidades separadas.
- Gestión: motivos, seguimiento futuro, cierre confirmado y reintento protegido.
- Asignador: capacidad y sede históricas, propietario conservado, reintento
  sin duplicados. La concurrencia PostgreSQL sigue pendiente.
- Detalle con score y contribuciones; tablero sobre cartera autorizada.
- Lecturas SQL del catálogo, sedes, conversaciones e historia de prioridades.
- Autenticación DRF por sesión y token. OpenAPI básico autenticado.
- Docker excluye secretos y copia solo código web/dominio; WhiteNoise sirve
  estáticos. Render tiene Blueprint web y arranque con comprobación de seguridad.

## Evidencia ejecutada

`python plataforma/manage.py test cuentas crm`: 23 pruebas correctas.
Incluyen rollback posterior a escrituras SQL, altas, deduplicación por empresa,
reintentos, capacidad uno y denegación de cartera ajena.

`python -m unittest discover -s auto-inicio-datos/tests`: 14 correctas.
`python -m unittest discover -s tests`: 14 correctas.
Ruff correcto en los módulos modificados; `collectstatic` ejecutado localmente.
La comprobación de producción con configuración sintética deja advertencias
W005/W021 de HSTS para subdominios/precarga; no verifica conexión ni despliegue.

Las tablas SQL de `test_alta_sql.py` son un contrato mínimo sobre SQLite.
**No prueban RLS, claves compuestas ni concurrencia PostgreSQL.**

## Pendientes reales para terminar

1. Supabase: DNS del host configurado no resolvió en dos intentos, incluyendo
   ejecución fuera del sandbox. No se aplicó ninguna migración ni carga remota.
   Falta `DJANGO_DATABASE_URL` con rol web; las políticas históricas y permisos
   de autenticación deben integrarse y verificarse.
2. T08: la selección por última ejecución aún requiere protección por revisión
   de entrada. Recargar una instantánea antigua después de una captura manual
   no debe desplazar la prioridad manual. Faltan pruebas mixtas y mapeos de origen.
3. T09: falta adaptar extracción Gemini a conversación individual, con validación
   de evidencias, reintentos acotados y publicación contra revisión vigente.
   `procesar_trabajos` falla antes de reclamar: no es un worker terminado.
4. Revisiones: falta resolución supervisora idempotente. Se conservan capturas;
   todavía no hay un recorrido de resolución completo.
5. Cartera: falta integrar transferencia con asignaciones/cupos de ese día y
   probar carreras entre alta, asignación, transferencia y gestión.
6. Indicadores: falta conciliar datos históricos, SLA con precisión temporal,
   filtros completos y paginación de historias extensas. OpenAPI no describe
   todavía transferencia/asignación ni respuestas de detalle completas.
7. Despliegue: diferido por el usuario. Docker CLI existe, pero no hay daemon
   activo; no se construyó la imagen. No hay repositorio remoto, URL ni horario
   alojado. Fuentes/caché necesitan almacenamiento durable fuera del contenedor web.
8. Entrega: falta auditoría PostgreSQL, AC01–AC20 completos, presentación final
   renderizada y ensayo sobre URL externa.

## Orden de cierre

Restablecer PostgreSQL de prueba → restricciones y revisiones → convivencia
lote/web → worker → aceptación integral → publicar en Render cuando se retome.
