# Modelo de datos — punto 05

## Estado y propósito

Modelo relacional acordado para persistir la ingestión, limpieza, extracción de IA y priorización de leads. Los scripts de creación y carga se ejecutaron y verificaron en PostgreSQL de Supabase el 2026-09-17. El esquema `crm` contiene 20 tablas de dominio, una tabla de migraciones y cuatro vistas. Se verificaron lectura posterior, repetición sin duplicados, claves foráneas, reversión de escrituras de prueba y acceso denegado a los roles públicos. El punto 05 de persistencia está completado; la autorización de usuarios por empresa se implementará con la aplicación. Consultar [evidencia y ejecución](EJECUCION_05.md).

- [Diagrama entidad–relación en Mermaid](modelo_datos.mmd).
- Este documento describe las 20 tablas, sus campos, relaciones, fuentes, restricciones y decisiones.
- [Ejecución del punto 05](EJECUCION_05.md): entorno, comandos, validación y límites.
- [Crear esquema](05_crear_db.py) y [cargar datos](05_cargar_db.py).
- [Migración SQL inicial](migrations/001_inicial.sql): definición física completa.

El diagrama conserva la propuesta presentada en la conversación. Muestra campos principales y tipos conceptuales, no un esquema SQL exhaustivo. Los campos adicionales descritos aquí —por ejemplo, precisión de fechas, teléfonos y versiones— deben incluirse en la implementación. Las relaciones compuestas que comprueban empresa se detallan más adelante.

## 1. Decisiones acordadas

1. **Identidad por empresa:** una misma persona en dos empresas conserva identidades independientes. No se fusiona ni se comparte su información entre comercializadoras.
2. **Cliente, consulta y conversación son conceptos distintos:** un cliente consolidado puede tener varias consultas y cada consulta varias conversaciones.
3. **Conversaciones descartadas con vínculo válido:** se guardan con `descartada = true`, motivos y fecha del descarte cuando se conozca. Sus mensajes y extracciones se conservan para auditoría y se excluyen de las vistas utilizables.
4. **Conversaciones sin vínculo verificable:** quedan en archivos externos de revisión. No se cargan la conversación, sus mensajes, extracciones ni intereses en la base. No se crea una empresa o un lead ficticio para alojarlas.
5. **Catálogo explícito:** marcas, modelos de moto y disponibilidad por punto de venta son tablas independientes.
6. **Todos los modelos mencionados se conservan:** si una mención no coincide con el catálogo, se guarda su texto con SKU nulo; no se inventa una referencia del catálogo.
7. **Reglas y aprendizaje automático separados:** la prioridad operativa se basa en reglas explicables. La regresión logística sin pesos se conserva como referencia experimental, sin convertir su score en una probabilidad validada de compra.
8. **Datos desconocidos como `NULL`:** no se rellenan por intuición ni se confunde ausencia con cero, negativa o rechazo.
9. **Auditoría y versiones:** las transformaciones, incidencias, fuentes y ejecuciones deben permitir reconstruir por qué existe cada resultado.
10. **Carga repetible:** repetir la misma entrada y versión no debe duplicar entidades ni resultados. Una ejecución nueva con método distinto puede generar otra versión de extracción o prioridad.

## 2. Inventario de las 20 tablas

| Nº | Tabla | Una fila representa | Contenido principal |
|---|---|---|---|
| 1 | `empresas` | Una comercializadora. | ID, nombre disponible. |
| 2 | `puntos_venta` | Una sede de una empresa. | ID, empresa, nombre y ubicación disponibles. |
| 3 | `asesores` | Un asesor comercial. | ID, empresa, sede, nombre, capacidad diaria, activo, ingreso. |
| 4 | `marcas` | Una marca del catálogo. | ID y nombre normalizado. |
| 5 | `modelos_moto` | Una referencia identificada por SKU. | Marca, línea, cilindraje, segmento, precio y unidades informadas. |
| 6 | `disponibilidad_modelo` | La oferta de un SKU en un punto de venta. | SKU y punto de venta. |
| 7 | `leads` | Un cliente consolidado dentro de una empresa. | ID consolidado, empresa, nombre, fechas y reglas de identidad. |
| 8 | `consultas` | Una entrada original conservada del cliente. | Lead, empresa, sede, canal, campaña, contactos, ciudad, modelo declarado, gestión, fechas, calidad y originales. |
| 9 | `conversaciones` | Una conversación con vínculo válido. | Consulta, empresa, canal, fecha, referencia original, flag y motivos de descarte. |
| 10 | `mensajes` | Un mensaje ordenado dentro de una conversación. | Conversación, posición, emisor, hora original y texto. |
| 11 | `extracciones_ia` | Un resultado de extracción versionado de una conversación. | Ejecución, modelo de IA, versiones, JSON estructurado, evidencias, validación y huellas. |
| 12 | `intereses_modelo` | Una mención de modelo en una extracción. | Texto, SKU opcional, identificación y evidencias. |
| 13 | `priorizaciones` | Una clasificación de un lead en una ejecución. | Scores separados, temperatura, cola, explicación, acción, contexto y versiones. |
| 14 | `modelos_ml` | Una versión de un modelo predictivo entrenado. | Algoritmo, configuración, variables, entrenamiento, métricas, límites y referencia al artefacto. |
| 15 | `historico_cierres` | Un registro del conjunto histórico. | Identidad histórica, empresa, características, desenlace, calidad y originales. |
| 16 | `ejecuciones` | Una corrida de una etapa del proceso. | Etapa, versión, configuración, tiempos, estado, conteos y errores. |
| 17 | `archivos_fuente` | Una versión de un archivo de entrada. | Nombre, ruta, tipo y hash del contenido. |
| 18 | `ejecucion_archivos` | El uso de un archivo por una ejecución. | Ejecución, archivo y función. |
| 19 | `trazabilidad_registros` | Una acción sobre un registro de origen. | Archivo, fila/referencia, ejecución, destino, acción y motivo. |
| 20 | `incidencias` | Un hallazgo o decisión sobre datos cargados. | Ejecución, empresa, entidad, campo, tipo, antes/después, decisión, estado y fecha. |

## 3. Diccionario de datos

### 3.1. Empresas, puntos de venta y asesores

**`empresas`**

- `empresa_id`: identificador de la fuente y clave primaria.
- `nombre`: nulo si la fuente no proporciona un nombre verificable.

**`puntos_venta`**

- `punto_venta_id`: identificador de sede y clave primaria.
- `empresa_id`: relación obligatoria con su empresa.
- `nombre`, `ubicacion`: opcionales; no se derivan de ciudades de clientes.

**`asesores`**

- `asesor_id`: clave primaria.
- `empresa_id`, `punto_venta_id`: empresa y sede, con coherencia entre ambas.
- `nombre`, `capacidad_diaria_leads`, `activo`.
- `fecha_ingreso`, `fecha_ingreso_precision`: conservar la precisión informada.
- Originales y diagnósticos disponibles en la fuente, mediante campos de auditoría o JSON.

No se inventa una asignación de clientes a asesores. El modelo actual contiene asesores y sus capacidades; la asignación de trabajo es una decisión posterior que deberá modelarse si se implementa.

### 3.2. Catálogo de motos

**`marcas`**

- `marca_id`: clave interna estable.
- `nombre`: nombre normalizado, único según la normalización acordada.

**`modelos_moto`**

- `sku`: clave primaria suministrada por el catálogo.
- `marca_id`: relación con `marcas`.
- `linea`: nombre de la referencia o línea, tal como está en catálogo.
- `cilindraje`, `segmento`, `precio_lista`, `unidades_disponibles`.

**`disponibilidad_modelo`**

- Clave compuesta: `sku`, `punto_venta_id`.
- Una fila indica que el catálogo ofrece ese modelo en esa sede.
- No incluye cantidad por sede: la fuente no la proporciona. `unidades_disponibles` se conserva al nivel del SKU, sin repartir ni repetir esa cantidad como inventario de cada sede.

No se crea un nivel adicional de familias o variantes que la fuente no distinga. El catálogo suministrado sirve como referencia común; los datos de clientes permanecen separados por empresa.

### 3.3. Leads y consultas

**`leads`**

- `lead_consolidado_id`: clave primaria estable producida por la consolidación.
- `empresa_id`: obligatoria; define el ámbito de la identidad.
- `nombre_presentacion`.
- `primera_fecha_registro`, `ultima_fecha_registro` y su precisión cuando pueda determinarse sin inventarla.
- `reglas_identidad`: reglas aplicadas para consolidar consultas, en JSON.

**`consultas`**

- `lead_id_origen`: clave de la entrada original conservada.
- `lead_consolidado_id`, `empresa_id`: vínculo al cliente dentro de la misma empresa.
- `punto_venta_id`: opcional si no se dispone de vínculo válido.
- `canal`, `campania`.
- `nombre_declarado`, `telefono`, `email`, `ciudad`.
- `modelo_declarado`: texto de interés conservado; `modelo_sku`: vínculo opcional al catálogo.
- `estado_gestion`.
- `fecha_registro`, `fecha_primer_contacto`, precisión de cada una y criterios de resolución.
- Diagnósticos de calidad: teléfono utilizable, modelo ambiguo, fechas pendientes y demás estados existentes.
- `datos_originales`: JSON con los valores recibidos antes de normalizar.

Ejemplo: un cliente escribe por formulario y WhatsApp a la misma empresa. Se representa con un lead y dos consultas. Los teléfonos, correos y ciudades consolidados se pueden obtener de esas consultas mediante una vista. No se fuerza un único contacto si la persona declaró varios.

### 3.4. Conversaciones y mensajes

**`conversaciones`**

- `conversacion_id`: clave primaria de origen.
- `lead_id_origen`: consulta vinculada, obligatoria para admitir la conversación a la base.
- `empresa_id`: coincide con la consulta y con el lead.
- `canal`, `fecha_inicio`, precisión y criterio de interpretación.
- Referencia de lead recibida originalmente y anotación del vínculo.
- `descartada`: booleano obligatorio.
- `motivos_descarte`: lista JSON; obligatoria y no vacía si se descarta.
- `fecha_descarte`: momento real conocido de la decisión. Si no está disponible, permanece nulo; la hora de carga no se presenta como hora histórica de descarte.
- Versión de la política de descarte para relacionar la decisión con el proceso que la produjo.

**`mensajes`**

- `mensaje_id`: clave interna.
- `conversacion_id`: relación obligatoria.
- `posicion`: orden dentro de la conversación, conservando la numeración utilizada por las evidencias.
- `emisor`, `hora_original`, `texto`.
- Unicidad de `(conversacion_id, posicion)`.

El flag de descarte se centraliza en la conversación. No se repite en todos los mensajes o extracciones: se filtran por relación con su conversación. La posición determina el orden cuando la hora sola no permite reconstruir una fecha completa.

**Precedencia de decisiones:** primero verificar el vínculo; después aplicar el estado de descarte. Una conversación descartada pero sin vínculo tampoco entra en la base. Permanece en revisión externa junto con su contenido y motivos.

### 3.5. Extracciones e intereses

**`extracciones_ia`**

- `extraccion_id`: clave interna.
- `conversacion_id`, `ejecucion_id`.
- Proveedor y `modelo_ia`; `version_prompt`, `version_normalizador` y versión del esquema cuando exista.
- `resultado`: JSON del contrato fijo. Incluye modelos de interés, presupuesto, inicial, cuota mensual, moneda conocida, crédito ofrecido/solicitado/aceptado/rechazado, pago, intención, objeción, cita, cotización y evidencias.
- `estado_validacion`, alcance de la revisión semántica y huellas del contenido/configuración de entrada.
- No se sobrescribe una extracción de otra versión; se conserva como resultado histórico.

**`intereses_modelo`**

- `interes_id`, `extraccion_id`.
- `texto_mencionado`, `modelo_sku` opcional, `estado_identificacion`, `evidencias` JSON.
- Una extracción puede tener varios intereses. Cada interés apunta como máximo a un SKU identificado; si es ambiguo se conserva el texto y la incertidumbre.

Esta tabla es una proyección consultable del JSON de extracción. Se genera a partir de él en la misma transacción y no se edita por separado, para impedir divergencias. Las referencias de evidencias conservan emisor, posición y texto; el cargador verifica su correspondencia con los mensajes.

### 3.6. Priorizaciones y modelos entrenados

**`priorizaciones`**

- `priorizacion_id`: clave interna.
- `empresa_id`, `lead_consolidado_id`, `ejecucion_id`.
- `lead_id_contexto`, `conversacion_id_contexto`: opcionales; si existen pertenecen al mismo lead y empresa.
- `score_prioridad`: puntos de reglas, entre 0 y 100.
- `temperatura`, `cola`, `explicacion`, `accion_sugerida`, `version_reglas`.
- `score_modelo_experimental`: salida del modelo en la escala documentada, separada de los puntos de reglas.
- `modelo_ml_id`: obligatorio si se guarda score de ese modelo.
- Estado/cobertura del contexto y referencias a conversaciones utilizables cuando estén disponibles.
- Unicidad propuesta: `(empresa_id, lead_consolidado_id, ejecucion_id)`.

La posición actual se calcula en una vista dentro de cada empresa y tipo de cola, por score, antigüedad y desempate estable. No se trata `posicion_en_cola_empresa` del CSV como una posición vigente permanente. Puede conservarse como parte de la evidencia de la exportación de origen.

**`modelos_ml`**

- `modelo_ml_id`, `ejecucion_id`, `algoritmo`, `version`.
- `configuracion`, columnas de entrada y contrato de transformación.
- Periodo de entrenamiento, criterio de selección, métricas de evaluación, versiones de dependencias y limitaciones.
- `ruta_artefacto`, `hash_artefacto`, `estado`.

El pipeline entrenado se guarda fuera de la base, en el archivo `.joblib`; la base registra su referencia verificable. La elección actual es la regresión logística comercial sin pesos. Seleccionarla para continuar no equivale a declararla apta para producción ni a activar su score como prioridad operativa.

### 3.7. Histórico de cierres

**`historico_cierres`**

- `historico_id`: corresponde al `lead_id` del archivo histórico; no identifica un lead actual.
- `empresa_id`, `punto_venta_id`, `fecha_registro` y precisión de fecha.
- `canal`, modelo cotizado en texto, `modelo_sku`, `precio_lista`.
- `horas_al_primer_contacto`, `numero_contactos`.
- `manifesto_cuota_inicial`, `forma_pago_declarada`, `pidio_cita`, `desenlace`.
- Originales y diagnósticos de normalización.

Los 2.200 registros históricos pueden persistirse, incluidos los 179 «Sin gestión». Estos últimos se excluyeron del entrenamiento, no de la fuente ni del almacenamiento. No se convierten en «Perdido». Tampoco se inventa fecha de cierre u horizonte de conversión.

### 3.8. Ejecuciones, archivos y auditoría

**`ejecuciones`**

- `ejecucion_id`, etapa, versión de código/configuración y huella reproducible de entradas y método.
- Inicio, fin, estado, conteos y resumen de errores.
- Las ejecuciones históricas importadas deben identificarse como importadas. No se atribuye un entrenamiento nuevo al simple acto de cargar su artefacto.

**`archivos_fuente`**

- `archivo_id`, nombre, ruta, tipo de fuente y hash del contenido.
- Registra versiones por contenido; cambiar el archivo genera otra referencia de versión.

**`ejecucion_archivos`**

- Relación entre ejecución y archivo con campo `funcion`.
- Clave compuesta `(ejecucion_id, archivo_id)`. En este diseño un archivo tiene una función descrita por ejecución.

**`trazabilidad_registros`**

- Archivo, fila o referencia de origen, ejecución, empresa cuando corresponda.
- ID original, entidad/identificador de destino, acción y motivo.
- Permite registrar consolidaciones, copias duplicadas y exclusiones sin crear clientes activos para registros eliminados.

**`incidencias`**

- ID, ejecución, empresa cuando corresponda, entidad e identificador afectados.
- Campo, tipo de problema, detalle, valores antes/después, decisión, estado y fecha conocida.
- Las referencias `entidad_afectada`/`identificador_afectado` son descriptivas y se verifican en el cargador; no son una clave foránea SQL que apunte a múltiples tablas.
- Las incidencias de conversaciones sin vínculo y sus detalles permanecen en el archivo externo de revisión. En la base puede registrarse el conteo agregado de elementos no cargados en la ejecución, sin importar esas conversaciones.

## 4. Relaciones e integridad por empresa

### Relaciones principales

- Empresa → puntos de venta, leads e histórico.
- Punto de venta → asesores; puede recibir consultas.
- Marca → modelos de moto → disponibilidad en puntos de venta.
- Lead → consultas → conversaciones → mensajes y extracciones.
- Extracción → intereses en modelos de moto.
- Lead → priorizaciones versionadas → referencia opcional a modelo ML.
- Ejecución → resultados, archivos e incidencias.

### Reglas de coherencia

Los identificadores mostrados como claves primarias en el diagrama son los identificadores actuales, únicos en los archivos entregados. Además se requieren claves únicas y relaciones compuestas que comprueben empresa:

- `leads`: unicidad adicional de `(empresa_id, lead_consolidado_id)`.
- `puntos_venta`: unicidad adicional de `(empresa_id, punto_venta_id)`.
- Una consulta referencia a su lead mediante `(empresa_id, lead_consolidado_id)` y a su sede mediante `(empresa_id, punto_venta_id)` cuando se conoce.
- Asesores deben referenciar una sede de su propia empresa.
- Conversaciones referencian `(empresa_id, lead_id_origen)` de una consulta.
- Prioridades referencian su lead y su contexto dentro de la misma empresa. El cargador también comprueba que la consulta de contexto pertenece a ese mismo lead; no basta con que sea de la misma empresa.
- Mensajes, extracciones e intereses heredan el ámbito de empresa a través de la conversación.

Si futuras fuentes reutilizan IDs entre empresas, habrá que adaptar las claves primarias a claves compuestas o internas; no se debe sobrescribir una entidad de otra empresa.

**Acceso:** estas restricciones impiden relaciones cruzadas, pero no implementan por sí solas autorización de lectura. La API debe aplicar el ámbito de empresa desde la identidad del usuario en cada consulta y en sus relaciones hijas. Las tablas de auditoría con valores originales también contienen información que requiere ese aislamiento. Incidencias globales, ejecuciones globales y archivos técnicos no se exponen automáticamente a todas las empresas.

## 5. Convenciones y restricciones

- Fechas visibles y exportadas en `YYYY-MM-DD`, con hora cuando la fuente realmente la aporta. Nunca usar mes–día–año como formato de salida.
- Guardar precisión (`fecha`, `fecha_hora`, desconocida) y valor original cuando corresponda. Una columna conceptual `datetime` no autoriza convertir una fecha sin hora en una medianoche real.
- Teléfonos e identificadores como texto; conservar prefijos y ceros cuando correspondan.
- Valores monetarios en tipo decimal de precisión fija y moneda conocida por separado. Moneda ausente permanece desconocida.
- Separar cero, `NULL`, «no informa» y negativas explícitas según el significado del campo.
- Scores limitados a 0–100; no confundir una escala numérica con una probabilidad calibrada.
- Capacidades, cantidades y precios no negativos cuando tengan valor; los errores se anotan antes de cargar.
- `descartada` no nula y con motivos cuando sea verdadera. Un estado de CRM «Descartado» en una consulta es distinto del descarte por calidad de una conversación.
- Preferir restricción de borrado en entidades con historia y auditoría. No eliminar en cascada datos históricos como forma habitual de actualizar cargas.

## 6. Índices y vistas previstos

### Índices

| Tabla | Índice / restricción | Objetivo |
|---|---|---|
| `conversaciones` | `(empresa_id, descartada)` | Filtrar conversaciones utilizables o descartadas por empresa. |
| `consultas` | `(empresa_id, lead_consolidado_id)` | Recuperar entradas de un cliente. |
| `consultas` | `(empresa_id, fecha_registro)` | Consultar ingresos por periodo. |
| `mensajes` | Único `(conversacion_id, posicion)` | Conservar orden y evitar duplicados. |
| `extracciones_ia` | `(conversacion_id, ejecucion_id)` | Consultar resultados versionados; unicidad según contrato de ejecución. |
| `intereses_modelo` | `(modelo_sku, extraccion_id)` | Buscar interés por modelo. |
| `priorizaciones` | Único `(empresa_id, lead_consolidado_id, ejecucion_id)` | Evitar repetir resultados de una misma ejecución. |
| `priorizaciones` | `(empresa_id, ejecucion_id, cola, score_prioridad)` | Consultar colas de una clasificación completada. |
| `historico_cierres` | `(empresa_id, fecha_registro)` | Filtrar histórico por empresa y periodo. |
| `incidencias` | `(empresa_id, estado, tipo)` | Revisar incidencias del ámbito autorizado. |

Los índices concretos se ajustarán al motor y a las consultas de la API; no reemplazan los controles de acceso.

### Vistas lógicas

- `v_leads_actuales`: identidad y contactos observados en sus consultas, sin mezclar empresas.
- `v_conversaciones_utilizables`: conversaciones con `descartada = false`; sus datos relacionados se recuperan respetando ese filtro.
- `v_prioridad_vigente`: última ejecución de clasificación completada correctamente por ámbito de carga. No mezcla silenciosamente filas de cargas parciales con versiones anteriores.
- `v_cola_priorizada`: orden de atención por empresa y cola; desempate reproducible por antigüedad y clave.

Estas vistas no añaden nuevas tablas al inventario de 20.

## 7. Fuentes de carga

Las rutas siguientes son relativas a la raíz del proyecto.

| Fuente | Destino / uso |
|---|---|
| `data/processed/asesores.csv` | Asesores; verificar correspondencia empresa–sede. |
| `data/processed/catalogo_motos.csv` | Marcas, modelos y disponibilidad por sede. |
| `data/processed/leads.csv` | Leads consolidados. |
| `data/processed/consultas_leads.csv` | Consultas y detalle declarado por canal. |
| `data/processed/conversaciones.json` | Conversaciones y mensajes; primero validar vínculo. |
| `data/processed/extracciones_conversaciones_ia.json` | Extracciones utilizables e intereses, solo con vínculo válido. |
| `data/processed/extracciones_conversaciones_descartadas.json` | Estado y motivos de descarte; extracción y conversación originales para auditoría, solo con vínculo válido. |
| `data/processed/conversaciones_utilizables_ia.json` | Comprobar pertenencia al conjunto aceptado del paso 03. |
| `data/processed/priorizacion_leads.json` o `.csv` | Prioridades; escoger una representación canónica y verificar equivalencia si se leen ambas. |
| `data/processed/contexto_priorizacion.json` | Contexto y referencias de las prioridades. |
| `data/processed/historico_cierres.csv` | Histórico completo, incluidos los no gestionados. |
| `data/processed/trazabilidad_leads.csv` | Trazabilidad de consolidación y exclusión. |
| `data/processed/incidencias_datos.json`, `incidencias_extraccion_ia.json`, `incidencias_modelado.json` | Incidencias y decisiones, aplicando la política de revisión externa para conversaciones sin vínculo. |
| Manifiestos de `data/processed` | Versiones, conteos y huellas de los procesos previos. |
| `outputs/clasificacion_04/desbalance_v2/modelo_sin_pesos.joblib` | Artefacto elegido como referencia experimental; conservar el archivo fuera de la base. |
| `outputs/clasificacion_04/desbalance_v2/manifest_desbalance.json` y `revision_resultados.json` | Configuración, resultados y decisión posterior a la ejecución. |
| `outputs/clasificacion_04/ficha_modelo.json` y `modelo_experimental.joblib` | Modelo y metadatos que generaron los scores actuales exportados. |

**Procedencia exacta de los scores:** aunque la referencia sin pesos de la segunda iteración tenga la misma configuración, no se cambia retroactivamente la referencia de los scores existentes. Se registra el artefacto que realmente los produjo. Aplicar otro artefacto debe generar una ejecución de scoring identificada.

Empresas y sedes pueden obtenerse de los IDs presentes en las fuentes verificadas. Si hay discrepancias de pertenencia, se registran y se bloquea el vínculo afectado; no se decide por intuición.

## 8. Comportamiento esperado del script 05

1. Validar existencia, esquema y huellas de las entradas; establecer versión del esquema y configuración de carga.
2. Preparar fuera de la carga las conversaciones sin vínculo y sus datos relacionados, con motivo y conteos para revisión.
3. Crear o migrar el esquema de forma versionada; no recrearlo destructivamente en cada ejecución.
4. Registrar la ejecución de importación y las referencias a ejecuciones/artefactos previos sin fabricar hechos históricos.
5. Cargar catálogos y entidades padre antes de sus hijos: empresas/sedes/marcas, catálogo/asesores, leads/consultas, conversaciones/mensajes, extracciones/intereses, modelos/prioridades e histórico/auditoría según dependencias.
6. Aplicar inserción/actualización por claves estables. Reconocer la misma entrada y versión para que un reintento no duplique entidades ni resultados.
7. Ejecutar la carga de datos en una transacción: si falla la integridad, revertir esa carga. Registrar el fallo después de la reversión o en un log externo para no perder el diagnóstico.
8. Validar conteos, claves, vínculos por empresa, exclusión de huérfanas y correspondencia entre extracciones, intereses y evidencias.
9. Marcar la carga como completada solo después de la validación; generar un resumen de cargados, actualizados, descartados conservados y pendientes fuera de la base.

Los archivos de revisión externos no deben contener credenciales ni reutilizarse como entradas activas sin resolver sus vínculos. Una nueva ejecución puede cargarlos cuando exista evidencia suficiente y quede registrada la resolución.

## 9. Validaciones de aceptación

- Cada lead cargado pertenece a una sola empresa y conserva sus consultas; no se fusionan clientes entre empresas.
- No hay consultas, conversaciones o contextos vinculados a otra empresa.
- No se cargan conversaciones sin vínculo válido ni sus mensajes, extracciones o intereses.
- Las conversaciones descartadas admitidas mantienen flag, motivos y contenido; una vista utilizable no las incluye.
- Todo mensaje conserva posición y contenido; las evidencias apuntan a mensajes reales.
- Los intereses desconocidos conservan texto y SKU nulo; no se pierden menciones.
- No se reparten unidades de inventario entre sedes sin datos para hacerlo.
- El histórico conserva los casos sin gestión, sin alterar sus etiquetas.
- Scores operativos y experimentales permanecen distintos y con su procedencia.
- Repetir la carga no aumenta injustificadamente los conteos.
- Los conteos se reconcilian con las fuentes y las exclusiones documentadas, sin fijar como inmutables los conteos de una sola ejecución.

## 10. Lectura del diagrama y próximos pasos

En Mermaid: `||` = exactamente uno; `o|` = cero o uno; `o{` = cero o muchos; `|{` = uno o muchos. `PK` indica clave primaria y `FK`, clave foránea.

El diagrama no representa todas las relaciones de auditoría ni todas las columnas. Las referencias descriptivas a entidades no son claves foráneas polimórficas. Las precisiones temporales y las restricciones compuestas se implementan según este documento.

El motor elegido es PostgreSQL de Supabase. El esquema SQL y el cargador ya están implementados; queda completar la conexión y verificar una carga real. La integración automática del script corresponde al punto 06; autenticación y autorización por empresa deben quedar implementadas al exponer la API o tablero. Hasta entonces, el esquema queda cerrado al acceso público.
