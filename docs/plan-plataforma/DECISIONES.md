# Decisiones de implementación

Este registro separa las decisiones tomadas al iniciar la ejecución de las
hipótesis originales. Cada decisión indica su alcance y evidencia disponible.

## D-01 — Usuario propio y membresía antes de migrar

**Estado:** aceptada para implementación local.

**Decisión:** Django usará `cuentas.Usuario`, derivado de `AbstractUser`, como
modelo de autenticación. La pertenencia a una empresa será una entidad separada
con rol y estado activo. No se usará Supabase Auth ni se agregará un campo de
empresa directamente al usuario.

**Motivo:** una persona puede pertenecer a más de una empresa y el ámbito debe
resolverse desde una membresía autorizada. Configurar un usuario personalizado
antes de la primera migración evita una sustitución posterior de alto riesgo.

**Impacto:** `AUTH_USER_MODEL` debe existir antes de ejecutar `migrate` en un
entorno que use la plataforma. Las claves reales y usuarios de evaluación siguen
pendientes; este cambio no crea cuentas ni modifica Supabase.

**Pruebas requeridas:** membresía inactiva revoca acceso; usuario con dos
membresías debe escoger una empresa; una empresa nunca se toma de un cuerpo HTTP.

## D-02 — Servicio único y reglas de dominio compartidas

**Estado:** aceptada para implementación.

**Decisión:** HTML Django y DRF llamarán servicios Python comunes. Las reglas de
normalización, identidad, score, asignación y gestión se moverán de forma gradual
a `dominio/`, sin HTTP interno entre pantalla y API.

**Motivo:** evita que formulario, serializer y lote calculen prioridades o
duplicados distintos. `inicio-datos` conserva evidencia y `auto-inicio-datos`
conserva su entrada CLI.

**Pruebas requeridas:** misma entrada normalizada produce mismo resultado por
lote, servicio, HTML y API; imports del dominio no realizan E/S ni leen secretos.

## D-03 — Migraciones nuevas bajo Django; base histórica inmutable

**Estado:** aceptada para preparación local; aplicación remota pendiente.

**Decisión:** `001_inicial.sql` del modelo histórico se conserva inmutable. Las
evoluciones de plataforma se entregarán en migraciones Django versionadas, con
SQL explícito cuando las claves compuestas o políticas PostgreSQL lo requieran.
El pipeline valida y carga datos; no ejecuta migraciones nuevas por cada lote.

**Motivo:** evita dos autoridades que modifiquen el mismo esquema y permite
actualizar desde una copia poblada sin recrear datos.

**Pruebas requeridas:** bootstrap desde cero, actualización desde datos existentes,
rollback ante fallo y verificación de que web, carga y migración usan roles SQL
distintos.

## D-04 — Prioridad vigente por lead, no por última ejecución global

**Estado:** implementada en migración local; aplicación PostgreSQL pendiente.

**Decisión:** una prioridad vigente se resuelve por `(empresa_id,
lead_consolidado_id)` y una ejecución completada. La migración aditiva
`002_vigencia_por_lead.sql` sustituye la vista global por la última prioridad de
cada lead, sin alterar la migración histórica inicial.

**Motivo:** una alta web o un resultado IA individual no puede ocultar las
prioridades de todos los demás leads, ni desaparecer en la siguiente recarga.

**Pendiente:** aplicar y probar en PostgreSQL la creación/actualización de un
lead individual, repetir un lote y comprobar que las prioridades no afectadas
permanecen vigentes.

## D-11 — Snapshot limitado al origen lote

**Estado:** implementado localmente; prueba PostgreSQL pendiente.

**Decisión:** `leads` y `consultas` tienen `origen_registro`, con valor histórico
`lote` y futuro valor `web`. La verificación de omisiones del cargador compara
solo los registros de origen `lote`; por tanto, sigue detectando bajas de fuente
sin exigir que el CSV incluya altas creadas por la plataforma.

**Límite:** el alta web aún no persiste esas columnas porque falta el adaptador
transaccional. La migración debe aplicarse antes de habilitar esa escritura.

## D-12 — Trabajo durable antes de integración Gemini

**Estado:** implementado localmente; worker y persistencia PostgreSQL pendientes.

**Decisión:** las solicitudes no llaman Gemini directamente. Un trabajo se crea
con una clave lógica de empresa, entidad, tipo y revisión; un worker reclama una
fila mediante bloqueo y el lease vencido vuelve a reintento.

**Límite:** todavía no existe el comando worker que invoca Gemini, valida su JSON
y publica resultados contra la revisión de entrada vigente.

## D-05 — Captura y posible duplicado sin fuga de cartera

**Estado:** aceptada para implementación en T07.

**Decisión:** una coincidencia inequívoca de la misma empresa añade una consulta
al lead existente. Si la coincidencia es ambigua, o pertenece a una cartera que
el asesor no puede consultar, se guarda una captura pendiente de revisión sin
mostrar datos del posible candidato ni crear un duplicado.

**Motivo:** conserva el trabajo del asesor, evita fusionar por intuición y mantiene
el aislamiento comercial.

**Pruebas requeridas:** mismos datos en empresas distintas, teléfono compartido,
reintento HTTP, doble envío concurrente y coincidencia con cartera ajena.

## D-06 — Hosting y disparador

**Estado:** pendiente de selección al llegar a T15.

**Opciones preseleccionadas:** Railway o Render para el servicio Django y proceso
programado; Supabase PostgreSQL existente; almacenamiento privado durable para
fuentes y caché. La decisión depende de la información vigente de plan, límites,
coste y acceso del evaluador en el momento de desplegar.

**Razón para no fijarla ahora:** no existe todavía un artefacto web desplegable y
elegir una cuenta/proveedor no mejora las tareas locales de dominio, seguridad y
persistencia. No se ha creado una cuenta, URL ni servicio.

## D-07 — Tablas operativas aditivas, sin recrear fuentes históricas

**Estado:** implementada localmente; pendiente de aplicar y complementar en
PostgreSQL.

**Decisión:** el CRM introduce tablas Django para estado operativo, captura
manual, idempotencia, trabajos, asignación, gestión, revisión y auditoría. Los
IDs de empresa, lead, consulta y prioridad se conservan como referencias a las
tablas históricas existentes; no se copian leads ni conversaciones a una segunda
estructura administrada por Django.

**Motivo:** permite incorporar trabajo diario y altas web sin perder la evidencia
importada ni reescribir `001_inicial.sql`.

**Límite actual:** las restricciones locales ya impiden duplicar estado, asignación
o clave idempotente. T05 añadirá referencias PostgreSQL, rol web y RLS para que
una referencia histórica inválida o una relación entre empresas no pueda llegar a
producción solo por omitir una validación de aplicación.

## D-08 — Credencial web y contexto transaccional de empresa

**Estado:** implementado localmente; validación PostgreSQL remota pendiente.

**Decisión:** Django solo usa `DJANGO_DATABASE_URL` para conectarse a PostgreSQL.
No toma `SUPABASE_DB_URL`, que pertenece al cargador administrativo. Antes de
cualquier consulta comercial, la aplicación resuelve una membresía activa y abre
una transacción que fija `app.empresa_id` con alcance local.

**Motivo:** una variable separada permite otorgar al servicio web únicamente los
permisos necesarios. El contexto local evita que un pool reutilice la empresa de
una solicitud anterior.

**Implementación:** `0002_rls_empresa` activa RLS en las tablas operativas y la
política compara cada `empresa_id` con el contexto SQL. La configuración mantiene
SQLite para desarrollo local y exige SSL para una URL PostgreSQL web configurada.

**Pendiente:** crear/probar roles reales de migración, carga y web; aplicar RLS
en Supabase con la credencial web; probar lectura, conteos, hijos y escrituras
cruzadas entre tres empresas en PostgreSQL aislado.

## D-09 — Identidad conservadora compartida

**Estado:** implementada localmente; integración transaccional pendiente.

**Decisión:** la limpieza de texto, teléfono móvil colombiano, comparación de
nombres e ID consolidado viven en `dominio.identidad`. El lote conserva el
adaptador de pandas para ausencias tabulares, pero delega las mismas decisiones
al dominio. La coincidencia nunca es global: el ID contiene la empresa y una
compatibilidad de nombre no autoriza por sí sola una fusión.

**Motivo:** impide que la futura alta web y el proceso automático acepten o
rechacen identidades de forma distinta. Los teléfonos no verificables siguen
marcados con su razón y no se inventan contactos.

**Pruebas requeridas:** paridad entre lote y dominio para formatos de teléfono,
ID diferente para la misma referencia en empresas distintas, y alta que cree
revisión cuando haya ambigüedad.

## D-10 — Alta primero como servicio puro

**Estado:** implementada localmente; persistencia transaccional pendiente.

**Decisión:** `dominio.alta` valida la captura manual, conserva una incidencia
de teléfono inválido cuando existe correo válido, calcula `reglas_evidencia_v1`
y resuelve solo tres resultados: lead nuevo, nueva consulta en una identidad
visible o revisión restringida. Recibe candidatos ya acotados a una empresa y
rechaza un adaptador que mezcle otra empresa.

**Motivo:** la regla puede demostrarse antes de conectar las tablas históricas a
Django. HTML, API y proceso SQL podrán llamar una única decisión y la revisión
no filtrará el identificador ni información de una cartera ajena.

**Límite actual:** no hay todavía adaptador transaccional contra las tablas
históricas ni clave idempotente aplicada de extremo a extremo. Eso depende de
resolver la coexistencia web/lote de T08.

## Baseline verificado el 2026-09-17

- `manage.py check`: correcto.
- Pruebas actuales de `auto-inicio-datos`: 14 correctas.
- Pruebas locales nuevas: 4 de membresía/acceso, 6 de modelos/configuración y 4
  de reglas compartidas, todas correctas al momento de esta actualización.
- Git: rama `main` sin commits ni remoto configurado; todos los archivos son
  actualmente no rastreados. No se creó historial artificial.
- Persisten los dos cambios necesarios de integración: `v_prioridad_vigente`
  depende de una ejecución global y `verificar_base_operativa` exige que el lote
  contenga toda entidad operacional ya persistida.
- No se ejecutaron migraciones, cargas, llamadas Gemini ni operaciones remotas
  durante este baseline.
