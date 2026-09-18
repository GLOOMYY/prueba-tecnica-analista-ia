# Plan de cierre: pendientes 1–6 de la plataforma

## Alcance y punto de partida

Esta numeración corresponde a los seis pendientes del resumen conversado,
no a los puntos originales del enunciado. El despliegue (7) avanza por separado;
la presentación y entrega (8) se preparan al final. El aislamiento entre empresas
del enunciado sí se verifica durante este plan: no se posterga.

Ya existen notebooks, pipeline, persistencia histórica, reglas compartidas,
alta manual con score, API, formularios, tablero, asignador y pruebas locales.
La evidencia final es de **81 pruebas locales**: 21 de dominio, 14 del pipeline
y 46 de Django. Se añadieron pruebas reales de PostgreSQL, concurrencia,
recarga completa, restauración y una llamada Gemini con el contrato compartido.
Actualizado el 2026-09-18; ver comandos y límites en el reporte operativo.

Objetivo: cerrar los recorridos funcionales y demostrar que pueden coexistir
con los datos históricos, sin pérdida de información ni cruces de empresa.
No reentrenar modelos ni modificar notebooks como parte de este cierre.

## Estado de cierre

| Fase | Estado | Evidencia |
|---|---|---|
| C1 | Verificada | Bootstrap permanente, rol restringido, tres cuentas y matriz de empresas/roles en PostgreSQL. |
| C2 | Verificada | Recargas de 1451 leads, identidad web/lote estable, fuentes inmutables y propuesta supervisada de prioridad. |
| C3 | Verificada | Contrato compartido, caché durable, cuota SQL, lease y publicación atómica; Gemini sintético validado. |
| C4 | Verificada | Revisión y transferencias, capacidad física, auditoría; transferencia/gestión simultáneas. |
| C5 | Verificada en alcance local | Filtros, paginación, SLA, OpenAPI y recorrido HTTP; inspección visual básica escritorio/móvil. |
| C6 | Verificada | Matriz AC01–AC20, concurrencia, backup de 42 tablas, entorno web limpio y revisión de secretos. |

La validación alojada en Render corresponde a la fase 7. No se declara una
prueba de carga masiva, una auditoría completa de accesibilidad ni una
exactitud universal de Gemini. Se verificaron los casos y límites concretos de
[estado real](../operacion/ESTADO_REAL.md) y
[aceptación](../operacion/ACEPTACION.md).

## Orden y coordinación

| Fase | Dependencia | Responsable técnico | Revisión |
|---|---|---|---|
| C1. Django–PostgreSQL y permisos | Entorno SQL de prueba accesible | Backend/DB | Seguridad y QA |
| C2. Convivencia web y lote | Contrato SQL de C1 | Datos/backend | QA de integridad |
| C3. IA individual durable | Revisión de entradas definida en C2 | IA/backend | Datos y QA |
| C4. Revisiones y cartera | C1; usa contratos de C2/C3 | Backend/producto | Seguridad y QA |
| C5. Tablero, API y experiencia | C2/C4; estados IA de C3 | Backend/interfaz | Producto y QA |
| C6. Aceptación integral | C1–C5 integradas | QA/integración | Seguridad y responsables |

Los roles describen responsabilidades; no implican que ya haya agentes
ejecutándose. Si se distribuye el trabajo, acordar antes nombres de tablas,
estados, contratos y archivos a modificar. C4 y C3 pueden desarrollarse en
paralelo una vez fijado C2; el diseño visual de C5 puede avanzar antes de su
integración. Las pruebas se escriben con cada fase, no solo al llegar a C6.

## C1. Integrar Django con PostgreSQL y verificar aislamiento

### Trabajo

- [x] Diagnosticar conexión del destino configurado sin mostrar secretos.
- [x] Preparar esquemas aleatorios separados de los datos de entrega y aplicar las
      migraciones Django allí.
- [x] Conciliar migraciones SQL históricas y Django: ordenar el bootstrap,
      establecer quién aplica cada migración y evitar cambios a la inicial.
- [x] Configurar conexión web con rol de mínimo privilegio, separada del rol
      administrativo/cargador; revisar `search_path`, SSL y límites de tiempo.
- [x] Revisar permisos de autenticación, tablas operativas, tablas históricas,
      vistas y secuencias; cerrar rutas que permitan omitir el filtro de empresa.
- [x] Crear fixtures sintéticas de tres empresas, asesores, supervisores y
      operador; incluir un cliente con el mismo contacto en empresas diferentes.
- [x] Verificar contexto de empresa dentro de transacciones y su limpieza al
      reutilizar conexiones; una petición no debe heredar el ámbito anterior.
- [x] Conciliar estados operativos de leads históricos para que puedan aparecer
      en el tablero y la cola conforme a sus permisos.
- [x] Documentar bootstrap de usuarios y membresías sin publicar credenciales.

### Criterio de cierre

Alta, lectura, gestión y rollback funcionan en PostgreSQL con el rol web real.
Las pruebas negativas cubren listas, detalle, hijos, agregados y escritura entre
empresas y carteras. Una migración repetida no altera ni duplica datos.

**Evidencia:** comandos reproducibles, versiones de migración, conteos y reporte
de permisos sin valores privados. No marcar cerrado por pruebas SQLite.

## C2. Asegurar convivencia de capturas web y cargas automáticas

### Trabajo

- [x] Definir procedencia de captura manual y revisión de entrada para publicar
      una prioridad vigente.
- [x] Diseñar el mapeo estable entre IDs de fuente y entidades consolidadas.
      Nunca utilizar un teléfono como identidad global entre empresas.
- [x] Impedir que un resultado con revisión antigua desplace una prioridad
      vigente más reciente en la capa operativa.
- [x] Aplicar la misma regla de vigencia al detalle, API, tablero y asignador.
- [x] Preservar gestiones, responsables, descartes y seguimiento al repetir lotes.
- [x] Unificar coordinación entre procesos mediante PostgreSQL; documentar
      orden de adquisición de bloqueos para evitar interbloqueos.
- [x] Mantener historial de prioridades y fuente de cada decisión.
- [x] Añadir migraciones aditivas y un procedimiento de conciliación si hace
      falta adaptar datos existentes; no reescribir silenciosamente su historia.

### Criterio de cierre

Probar: lote → alta web → repetición del lote; alta web → lote nuevo; resultado
tardío de IA; dos actualizaciones simultáneas; fallo a mitad de escritura.
La prioridad vigente corresponde a la revisión aceptada, no se pierden cambios
comerciales y los reintentos no crean consultas ni prioridades duplicadas.

**Evidencia:** fixtures, pruebas de integración y lectura posterior de historia
y estado vigente. Comparar cantidades y relaciones, no solo salida exitosa.

## C3. Completar extracción IA por conversación

### Trabajo

- [x] Extraer del pipeline un servicio reutilizable para una conversación,
      preservando el contrato de JSON y las validaciones ya acordadas.
- [x] Mantener todos los modelos mencionados, importes con evidencia, desconocidos
      explícitos y distinción entre ofrecimiento del asesor y petición del cliente.
- [x] Validar emisor, referencia y texto de evidencia; no aceptar información
      inventada ni mensajes que intenten cambiar las instrucciones del extractor.
- [x] Encolar trabajos con empresa, identidad, revisión y huella de contenido,
      prompt y modelo. Respetar el tratamiento de conversaciones descartadas.
- [x] Implementar reclamación atómica, vencimiento, token de lease y recuperación
      de trabajos; un worker vencido no puede publicar resultados.
- [x] Limitar reintentos y registrar categorías sanitizadas. Una prueba sintética
      Gemini pasó con el contrato completo; cuota SQL y caché durable verificadas.
- [x] Persistir resultado y actualizar score únicamente si la revisión todavía
      es vigente. Conservar trazabilidad de resultados tardíos sin activarlos.
- [x] Mostrar estados de trabajos y categorías de error en el detalle del lead.
- [x] Habilitar `procesar_trabajos` para reclamar y ejecutar una extracción.

### Criterio de cierre

Con un proveedor simulado: éxito, JSON inválido, evidencia falsa, cuota agotada,
timeout, caída del trabajador, doble reclamación y respuesta atrasada. Después,
una prueba acotada real con el modelo disponible y cuota comprobada, sin procesar
todo el histórico ni introducir servicios de pago.

**Evidencia:** resultado estructurado validado, una sola publicación por revisión,
estado durable del trabajo y registros sanitizados. Las pruebas automáticas no
consumen cuota de Gemini.

## C4. Cerrar revisiones, transferencias y capacidad diaria

### Trabajo

- [x] Definir acciones supervisoras para capturas ambiguas: vincular a un lead
      de la misma empresa, crear uno distinto cuando corresponda o descartar
      con motivo. Conservar captura original, actor y decisión.
- [x] Implementar servicio y API de revisión con validación del estado e
      idempotencia para vincular, crear identidad distinta o rechazar.
- [x] Mantener las conversaciones sin vínculo verificable fuera de las tablas
      comerciales; no crear leads/empresas ficticios para importarlas.
- [x] Integrar transferencia con sede, asesor activo, cartera y asignación del
      día. Acordar y documentar cómo cuentan tareas ya completadas en la capacidad.
- [x] Evitar que varias membresías del mismo asesor multipliquen sus cupos.
- [x] Actualizar propietario y asignación de forma atómica; preservar auditoría
      y posiciones únicas. Rechazar destinos incompatibles o sin cupo.
- [x] Probar conflictos entre transferencia, asignador, resolución y gestión.

### Criterio de cierre

Solo un supervisor autorizado resuelve o transfiere. No hay cruces de empresa,
duplicación de leads, pérdida de gestiones ni exceso de capacidad. Los motivos
de rechazo son claros sin revelar datos de otra cartera.

**Evidencia:** pruebas de permisos, doble envío, rollback y concurrencia real.

## C5. Completar tablero, consultas, API y pantallas

### Trabajo

- [x] Conciliar indicadores con SQL e incluir correctamente datos históricos
      y manuales; documentar denominador y periodo de cada indicador.
- [x] Definir medición de atención en 24 horas sin inventar hora para fechas
      incompletas; separar los casos no medibles.
- [x] Completar filtros de negocio y orden estable de la cola; respetar cartera,
      empresa, estado, seguimiento y prioridad vigente en todas las consultas.
- [x] Paginar historias extensas y evitar consultas repetidas por cada fila.
- [x] Ampliar OpenAPI con cuerpos, idempotencia, revisión, asignación y
      transferencia y respuestas tipadas de detalle.
- [x] Revisar formularios y validación estricta de booleanos, dinero y fechas;
      mostrar desconocidos sin convertirlos en negativas o importes cero.
- [x] Comprobar navegación de alta → score/motivos → gestión → cola/tablero.
- [x] Revisar en navegador escritorio y móvil: vacíos, errores, revisión,
      pendiente IA y formularios mediante pruebas HTTP. La inspección visual
      cubrió navegación básica, vacíos y alta; no todos los estados de error.

### Criterio de cierre

El mismo lead y sus permisos producen resultados coherentes en HTML y API.
Los indicadores coinciden con consultas de control; los ejemplos del contrato
son ejecutables y no contienen secretos. El asesor entiende por qué contactar
al lead y cuál es la siguiente acción.

**Evidencia:** pruebas HTTP, conciliación de indicadores y revisión visual real.

## C6. Aceptación integral y recuperación

### Trabajo

- [x] Mapear AC01–AC20 del plan maestro a pruebas concretas y su evidencia;
      corregir checklists obsoletas sin marcar requisitos no comprobados.
- [x] Ejecutar un entorno limpio con dependencias declaradas, PostgreSQL aislado,
      datos sintéticos y secretos fuera del repositorio. El entorno nuevo
      verificó dependencias web; las pruebas SQL usaron el entorno del proyecto.
- [x] Recorrer fuentes → limpieza → IA → prioridad → SQL → asignación → pantalla
      y API → gestión; repetir y comprobar idempotencia.
- [x] Ejecutar la matriz de tres empresas y roles, incluyendo objetos hijos,
      agregados, autenticación fallida y membresías revocadas.
- [x] Probar carreras, desconexiones, procesos interrumpidos, trabajos vencidos,
      respuestas tardías y reanudación sin publicaciones parciales. Fallos y
      vencimientos se inyectan en pruebas; no se cortó la red de producción.
- [x] Verificar copia de seguridad y restauración en destino aislado.
- [x] Medir consultas y tiempos con volumen representativo; corregir problemas
      observados sin introducir infraestructura innecesaria.
- [x] Revisar secretos, logs, dependencias, exclusiones y notebooks versionados.
- [x] Actualizar README, diagrama, estado real y reporte de aceptación con
      comandos, versiones, resultados y limitaciones pendientes.

### Criterio de cierre

Cero fallos críticos abiertos de aislamiento, integridad y recuperación. Las
pruebas relevantes pasan sobre PostgreSQL y el recorrido local es reproducible
sin editar fuentes ni ejecutar notebooks. Las pruebas externas de URL y ejecución
alojada quedan coordinadas con el punto 7, sin declararlas realizadas aquí.

## Reglas de ejecución y entrega por fase

1. Confirmar estado actual antes de modificar; no repetir trabajo validado.
2. Implementar una unidad revisable con sus pruebas y explicación de decisiones.
3. Registrar evidencia real y actualizar estado: pendiente, en curso, bloqueado
   o verificado. Un bloqueo remoto no impide desarrollar pruebas con fixtures.
4. Crear commits pequeños y coherentes con Conventional Commits, sin secretos,
   datos fuente ni salidas de notebooks. No inventar fechas ni resultados.
5. No hacer push ni cambios de despliegue como consecuencia automática de un
   commit local; coordinar las acciones del punto 7 con el usuario.

## Resultado y siguiente paso

C1–C6 quedan cerradas en el alcance y las verificaciones descritas arriba.
Los commits registran cambios reales por componente y no se han enviado al
remoto en esta intervención. El siguiente bloque es publicar y comprobar
Render (7), seguido de la presentación y entrega (8).
