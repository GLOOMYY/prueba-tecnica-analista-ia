# Protocolo de trabajo entre agentes

Este documento organiza la futura ejecución del [plan maestro](PLAN_MAESTRO.md).
No inicia agentes ni afirma que hayan aprobado decisiones. La guía obligatoria
del repositorio sigue siendo [AGENTS.md](../../AGENTS.md); este archivo describe
roles, coordinación y entregas para la plataforma.

## 1. Reglas de coordinación

1. Un coordinador mantiene el alcance, contratos, dependencias y estado real.
2. Una tarea tiene un responsable de entrega y al menos un revisor distinto.
3. Un archivo tiene un escritor activo. Un colaborador propone cambios al dueño;
   no modifica a la vez migraciones, settings o servicios compartidos.
4. Se delegan tareas acotadas con entradas, archivos, aceptación y exclusiones.
   «Haz el backend» no es una asignación suficientemente concreta.
5. Los agentes pueden avanzar sobre contratos ratificados y fixtures acordados;
   no inventan interfaces incompatibles esperando arreglarlas al integrar.
6. No dar por aprobada una propuesta porque nadie respondió. Registrar revisiones
   recibidas y diferencias abiertas; A0 decide dentro del alcance autorizado.
7. No fingir consenso, resultados de pruebas, historial de commits o despliegues.
8. Mantener la distinción entre código escrito, ejecutado y verificado.

## 2. Roles especializados

Son **roles de trabajo**, no nueve procesos que deban ejecutarse simultáneamente.
Una misma persona/agente puede asumir roles en momentos distintos; la revisión
independiente de cambios críticos debe conservarse.

| Rol | Responsabilidad | Entrega principal | No decide por su cuenta |
|---|---|---|---|
| A0 — Coordinación e integración | Alcance, dependencias, contratos, conflictos, integración y reporte. | Tablero vigente, decisiones y versión integrada verificable. | Cambiar reglas de negocio aprobadas para simplificar una tarea. |
| A1 — Producto y análisis de negocio | Flujos, términos, criterios de aceptación, UX y sustentación. | Historias, estados de pantalla, métricas y guion. | Inventar declaraciones del cliente, capacidad o evidencia de resultados. |
| A2 — Datos y PostgreSQL | Modelo físico, migraciones, integridad, vigencia por lead y convivencia con lote. | SQL versionado, adaptadores y pruebas de integridad. | Reescribir la migración inicial o borrar datos para resolver incompatibilidades. |
| A3 — Identidad y seguridad | Usuarios, membresías, contexto, permisos, RLS y revisión de exposición. | Acceso por empresa probado y configuración segura. | Abrir acceso global porque el dataset sea sintético. |
| A4 — Dominio, scoring y servicios | Normalización reutilizable, identidad, alta, prioridad, asignación y gestión. | Servicios con contratos explícitos y pruebas de paridad. | Cambiar pesos/modelo o sustituir evidencia por intuición. |
| A5 — Interfaz Django | HTML, formularios, navegación, estados y accesibilidad. | Tablero, cola, detalle y alta integrados. | Duplicar score, permisos o deduplicación en JavaScript. |
| A6 — Automatización y despliegue | Trabajos durables, runner, almacenamiento, release, observabilidad y recuperación. | Flujo alojado y despliegue reproducible. | Migrar tablas con otra autoridad, contratar servicios o consumir cuota sin alcance autorizado. |
| A7 — QA e integración independiente | Casos adversos, concurrencia, paridad, permisos y recorrido externo. | Evidencias reproducibles y defectos priorizados. | Aprobar por capturas cuando faltan comprobaciones de persistencia/aislamiento. |
| A8 — API y consultas | Serializers, endpoints, filtros, agregados y OpenAPI. | API consumible y consultas compartidas con HTML. | Exponer CRUD de todas las tablas o ejecutar reglas distintas de A4. |

### Entradas mínimas por rol

- **Todos:** guía raíz, plan maestro, contratos v1, tarea asignada y estado real
  del código. No copiar secretos en los mensajes de coordinación.
- **A1:** enunciado, decisiones del usuario y ejemplos sintéticos de asesor/supervisor.
- **A2:** SQL actual, ledger, plan de carga, vistas, manifiestos y conteos de referencia.
- **A3:** configuración Django, esquema de usuarios propuesto y matriz de endpoints.
- **A4:** normalizadores, consolidación, extracción, reglas y artefactos del punto 4.
- **A5:** contratos de consultas/comandos, diseño de estados y permisos de cada pantalla.
- **A6:** runner, checkpoints, caché, verificación remota y restricciones del hosting.
- **A7:** AC01–AC20, fixtures acordados y comandos reales de ejecución.
- **A8:** servicios de A4, adaptadores de A2 y autorización de A3.

## 3. Propiedad de archivos propuesta

Las rutas nuevas son una propuesta; A0 confirma las reales en T00 y registra el
mapa antes de delegar. No crear todos los módulos por anticipación: dividir solo
cuando haya responsabilidad concreta. Se preserva el paquete `plataforma`, sin
renombrarlo a `config`.

| Área/ruta | Escritor principal | Revisores y coordinación |
|---|---|---|
| `AGENTS.md`, configuración global, dependencias, `pyproject.toml` | A0 | Roles afectados envían cambios concretos. |
| `plataforma/plataforma/settings.py`, `urls.py` y configuración de release común | A0 | A3 seguridad; A6 hosting; A8 rutas. |
| `plataforma/cuentas/` | A3 | A2 revisa esquema y orden de migraciones. |
| `plataforma/crm/models.py`, `migrations/`, `sql/` y adaptadores de persistencia | A2 | A3 permisos; A4 semántica; A7 pruebas SQL. |
| `dominio/` | A4 | A2 identidad; A7 paridad; sin dependencias HTTP. |
| `plataforma/crm/services/` | A4 | A2 transacciones; A3 ámbito autorizado. |
| `plataforma/crm/api/` y `selectors/` | A8 | A3 autorización; A4 contrato; A7 API. |
| `plataforma/crm/forms.py`, vistas HTML, templates y estáticos propios | A5 | A1 experiencia; A3 formularios/CSRF; A8 lecturas compartidas. |
| `auto-inicio-datos/utils/persistencia/` | A2 durante T08 | A6 integra con runner, sin escritura simultánea. |
| Resto de `auto-inicio-datos`, `run.py`, procesos de trabajos y configuración de despliegue | A6 | A4 revisa extracción de reglas; A2 persistencia. |
| `tests/` de integración transversal y fixtures comunes | A7 | Cada dueño mantiene sus pruebas unitarias locales. |
| Documentación funcional, manual de demo y presentación | A1 | A0 valida coherencia; autores técnicos revisan sus secciones. |
| Contratos y tablero de este plan | A0 | Cambios mediante decisión registrada. |
| `inicio-datos/` | Sin escritura para estas fases | Solo cambios documentales expresamente necesarios; preservar notebooks y salidas. |

Las migraciones de `cuentas` y `crm` requieren orden común: A3 escribe las de
usuarios, A2 las comerciales; A0 integra el grafo después de revisión cruzada.
Nunca generar dos migraciones «siguientes» independientes sobre la misma app.
La migración inicial SQL existente permanece inmutable.

## 4. Acuerdos antes de programar: puerta G0

### Decisiones que deben quedar escritas

| Decisión | Propone | Revisión requerida | Registro |
|---|---|---|---|
| Semántica de hoy, cartera, estados y capacidad | A1/A4 | A2, A5, A7 | C06–C07 y casos sintéticos. |
| Alta, identidad, ambigüedad e idempotencia | A4 | A2, A3, A8, A7 | C02–C03 y diagrama de transacción. |
| Contexto de score y resultados tardíos | A4 | A2, A6, A7 | C04–C05 y control de revisión. |
| Empresa, roles y alcance SQL/HTTP | A3 | A2, A8, A7 | C01 y matriz negativa. |
| Modelo físico y autoridad de migraciones | A2 | A3, A6 | DDL propuesto, bootstrap y actualización. |
| API, errores y representación de datos | A8 | A3, A4, A5 | C08 y ejemplos/esquema inicial. |
| Procesador, almacenamiento y disparador | A6 | A2, A3, A7 | C09–C10 y prueba de recuperación propuesta. |
| Proveedor, recursos y presupuesto | A0/A6 | A3; usuario si falta presupuesto indispensable | Decisión de despliegue con documentación vigente. |

### Procedimiento de decisión

1. El proponente abre una decisión `D-XX` con problema concreto, requisito,
   alternativa recomendada, otra alternativa razonable y consecuencias.
2. Adjunta ejemplos de entradas/salidas, entidades afectadas y pruebas que
   demostrarían que la propuesta funciona. No basta una preferencia de framework.
3. Cada revisor indica: conforme, conforme con cambio concreto o bloqueo motivado.
4. A0 resuelve diferencias dentro de los requisitos y registra la decisión final.
   Una objeción fundada de fuga de datos, pérdida de información o incumplimiento
   del usuario impide integrar hasta corregirla; no se resuelve por mayoría.
5. Actualizar el contrato, tablero y todos los consumidores afectados. Un cambio
   compatible puede mantener v1; un cambio incompatible requiere nueva versión
   o migración explícita y actualización de fixtures.
6. Preguntar al usuario solo por una decisión indispensable no deducible del
   contexto. Mientras tanto, avanzar tareas independientes; no convertir cada
   revisión técnica en una solicitud de permiso al usuario.

Plantilla de decisión:

```text
D-XX — Título
Estado: propuesta / aceptada / sustituida
Problema y requisito:
Contrato y tareas afectados:
Alternativa recomendada y motivo:
Alternativa descartada y coste:
Ejemplos y casos de fallo:
Compatibilidad/migración:
Revisores y observaciones recibidas:
Decisión final y fecha:
Evidencia o condición pendiente:
```

El documento creado ahora no contiene firmas simuladas. G0 empieza pendiente.
Las decisiones técnicas pueden ratificarlas los agentes en trabajo posterior;
eso no amplía autorización para publicar, contratar o modificar datos remotos.

## 5. Paralelismo con cuatro espacios de ejecución

Si la herramienta permite cuatro agentes activos, usar **A0 + hasta tres
trabajadores**. Rotar especialidades por oleada; no bloquear el plan suponiendo
que hay nueve agentes simultáneos. Antes de abrir un agente debe existir una
tarea independiente y útil que pueda completar con sus entradas disponibles.

| Oleada | Trabajador 1 | Trabajador 2 | Trabajador 3 | Integración de A0 |
|---|---|---|---|---|
| W0 — Diagnóstico | A1: criterios y UX. | A2: inventario SQL/identidad. | A3: amenazas/permisos. | Reúne T00–T02; incorpora revisión de A4/A6/A8 por turnos. |
| W1 — Base | A2: esquema y bootstrap. | A3: usuario/membresía según contrato. | A7: fixtures y pruebas negativas. | Coordina migraciones; no integrar RLS comercial antes del DDL. |
| W2 — Dominio | A4: reglas y alta. | A2: convivencia lote/vigencia. | A6: trabajos y recuperación sobre contrato. | Integra revisiones/versiones y prueba G2. |
| W3 — Producto/API | A8: endpoints/consultas. | A4: asignación y gestión. | A5: layout y páginas con fixtures ratificados. | Integra rutas y estados; no declarar UI funcional con mocks. |
| W4 — Preparación nube | A5: integración final HTML. | A6: empaquetado/almacenamiento. | A7: API/concurrencia/E2E local. | Corrige defectos antes del release. |
| W5 — Verificación | A6: despliegue y disparador autorizados. | A3: auditoría de acceso. | A1: documentación/presentación. | A7 rota para prueba externa; cierra G5/G6 con evidencia. |

Una oleada no equivale a una fase terminada. Tareas dependientes se activan solo
cuando su interfaz esté disponible; se puede avanzar diseño/pruebas sintéticas
sin fingir que la integración ya está lista. No mantener agentes ociosos esperando
una respuesta que puede resolver A0.

## 6. Ciclo de una tarea

Estados: `pendiente → lista → en_curso → en_revision → terminada`. `bloqueada`
requiere causa y dependencia concreta; no equivale a «difícil».

### Preparación

- A0 comprueba autorización, archivos actuales y dependencias.
- Asigna dueño, revisor, archivos permitidos, criterios de aceptación y límites.
- Si existen Git e historial utilizables, pueden usarse ramas/worktrees para
  aislamiento. No asumir que ya existen commits o remoto válido. Publicar/crear
  commits se rige por las instrucciones del usuario, no por este plan.
- En directorio compartido, el mapa de escritor único es obligatorio. Un cambio
  en archivo ajeno se solicita al dueño con un diff/propuesta precisa.

### Desarrollo

- Funciones pequeñas, contratos tipados y docstrings Google según guía raíz.
- Pruebas de riesgos reales, sin reentrenar o llamar Gemini en tests unitarios.
- Mantener fixtures sintéticos comunes de tres empresas y desconocidos explícitos.
- Comunicar pronto cambios de contrato; detener solo la parte dependiente.
- Documentar decisiones y resultados útiles para que el usuario estudie el código.

### Revisión e integración

- El revisor contrasta comportamiento con contrato, no solo estilo.
- A0 integra unidades pequeñas, ejecuta las comprobaciones pertinentes y resuelve
  conflictos preservando cambios ajenos. No reescribe notebooks históricos.
- Repetir pruebas solo por cambios nuevos, fallos o dudas pendientes. No reejecutar
  todo el entrenamiento para validar una pantalla.
- La tarea termina con evidencia y documentación. Si faltó conexión remota,
  distinguir «implementación lista» de «verificación de producción pendiente».
- Una puerta G exige todas sus tareas críticas verificadas y sin defectos que
  permitan fuga de empresa, pérdida de datos o falso éxito del procesamiento.

## 7. Entrega entre agentes

```text
Tarea: TXX — nombre
Responsable / revisor:
Estado real:
Contrato aplicado y decisiones D-XX:
Cambios y motivo:
Archivos modificados:
Interfaces/entradas/salidas entregadas:
Migración o compatibilidad:
Comandos ejecutados y resultado resumido:
Casos AC cubiertos / evidencia:
Qué no se ejecutó y por qué:
Riesgos o bloqueos concretos:
Tarea siguiente habilitada:
Cambios solicitados a propietarios de archivos compartidos:
```

No adjuntar `.env`, cuerpos de conversaciones, contraseñas o tokens. Usar IDs
técnicos y ejemplos sintéticos. Guardar evidencias finales sanitizadas bajo
`docs/evidencias/` cuando existan; no crear informes de éxito anticipados.

## 8. Mensajes listos para delegar

Son plantillas para ejecutar después de ratificar las dependencias. A0 debe
completar archivos y contratos concretos antes de enviarlas.

### Datos — A2

> Trabaja únicamente T03/T08 en los archivos de datos asignados. Lee el SQL y
> cargador existentes; conserva la migración inicial. Implementa extensiones
> aditivas y vigencia por lead para que una captura web sobreviva a recargas.
> Acuerda usuario/membresía con A3 y revisión de entrada con A4 antes de escribir
> migraciones. Entrega pruebas PostgreSQL de bootstrap, actualización, rollback
> y alta+recarga. No ejecutes migraciones remotas fuera del alcance autorizado.

### Seguridad — A3

> Implementa T04 con C01 y el modelo acordado en T03. Tu propiedad es cuentas y
> autorización; solicita a A0 cambios de settings/rutas y a A2 cambios SQL. Prueba
> acceso entre tres empresas en listado, detalle, creación, hijos y agregados.
> No habilites un admin comercial global. Entrega la matriz de permisos y
> evidencia con rol SQL web, distinguiendo comprobaciones pendientes.

### Dominio — A4

> Implementa T06/T07 en dominio y servicios asignados. Conserva paridad de las
> reglas actuales, incluyendo ausencia/cero, temperatura por señales y contexto
> temporal verificable. Alta idempotente y transaccional; sin Gemini ni
> entrenamiento dentro del request. Revisa con A2 la identidad canónica y la
> prioridad vigente. Entrega AC01–AC08 y casos de concurrencia pertinentes.

### API — A8

> Implementa T10/T11 con C08, usando servicios de A4 y contexto de A3. No copies
> reglas en serializers. Pagina, valida filtros y prueba empresa/cartera antes
> de agregados. Entrega OpenAPI, ejemplos sintéticos, errores y pruebas de
> contrato. Coordina con A5 el mismo resultado de lectura para HTML.

### Interfaz — A5

> Implementa T13/T14 con los servicios y consultas acordados. Construye tablero,
> mis leads, detalle y alta en Django, con estados vacío/error/revisión y campos
> desconocidos claros. No recalcules score ni decidas empresa en JavaScript.
> Verifica móvil, teclado, CSRF, doble envío y captura coincidente restringida.
> Entrega el recorrido funcional, sin presentar mocks como integración real.

### Automatización — A6

> Implementa T09/T15 dentro del alcance autorizado. Trabajos durables por
> revisión, reclamo exclusivo, cuota acotada y caché persistente. Prepara web y
> proceso de datos para despliegue; no dependas de un disco local permanente.
> Acuerda migraciones con A2. Entrega prueba de reinicio, resultado tardío y
> configuración sin secretos. Separa preparación de publicación real.

### QA — A7

> Revisa los cambios integrados contra AC01–AC20. Prioriza fugas de empresa,
> duplicados concurrentes, score obsoleto y recarga que borre altas web. Usa
> PostgreSQL de prueba aislado y fixtures sintéticos. Reporta reproducción,
> impacto, esperado/observado y tarea dueña. No corrijas producción dentro de una
> revisión sin coordinar la propiedad del archivo. No apruebes por solo ver código.

### Producto/documentación — A1

> Prepara criterios de pantalla y T19. Explica hoy, score, capacidad, desconocidos
> y estados de revisión de manera comprensible. Contrasta con enunciado y
> decisiones del usuario. Entrega documentación y guion de hasta ocho diapositivas
> con resultados reales; no declares ML superior ni nube funcionando sin evidencia.

## 9. Bloqueos, desacuerdos y defectos

- **Bloqueo técnico:** dueño indica evidencia, dependencia y alternativa segura.
  A0 mueve trabajo independiente; no simula conexión o ejecución faltante.
- **Cambio de negocio:** A1 y A4 formulan el impacto con un ejemplo. A0 decide
  dentro de instrucciones existentes o consulta al usuario si es indispensable.
- **Fallo de aislamiento/integridad:** detener integración afectada; A3/A2 revisan
  y A7 reproduce. No compensarlo con un aviso en la interfaz.
- **Fallo de infraestructura:** reintento limitado y diagnóstico sanitizado. Si
  una revisión automática bloquea una acción, reportar acción y motivo; no evadirla.
- **Conflicto de archivos:** devolver al escritor dueño; A0 integra, preservando
  cambios existentes. No restaurar archivos completos a una versión antigua.
- **Desborde de alcance:** mantener los cuatro recorridos pedidos; posponer
  mejoras opcionales antes que permisos, persistencia, automatización o pruebas.

## 10. Cierre de coordinación

A0 entrega al usuario qué quedó implementado, dónde, qué se ejecutó, evidencia y
pendientes reales. El cierre de cada puerta lo firma quien integra con revisión
independiente registrada; el usuario no necesita aprobar cada función para que
los agentes continúen dentro de una implementación ya autorizada.
