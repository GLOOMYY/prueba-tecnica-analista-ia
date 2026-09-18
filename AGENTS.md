# Guía de trabajo del proyecto

## 1. Alcance y prioridad de estas instrucciones

Este archivo aplica a todo el repositorio. Su objetivo es producir una solución
correcta, sencilla, reproducible y explicable para la prueba técnica de Analista
de IA. También sirve como referencia de estudio y revisión para el usuario.

- Las instrucciones explícitas del usuario prevalecen sobre las convenciones
  locales de este archivo. No introducir solicitudes de permiso innecesarias.
- Leer las instrucciones adicionales de un subdirectorio antes de modificarlo,
  si existen. Resolver contradicciones considerando el alcance y el pedido actual.
- Revisar el estado real de los archivos antes de editar: el usuario modifica y
  ejecuta los notebooks. No regenerarlos desde constructores temporales antiguos.
- Preservar cambios ajenos y limitar cada intervención al trabajo solicitado.
- Si el usuario pide preparar código para ejecutarlo personalmente, no ejecutar
  ese código, ni entrenamientos, llamadas de IA o cargas que contenga. Sí se puede
  inspeccionar texto y validar sintaxis/estructura sin ejecutarlo.
- Separar siempre lo propuesto, lo implementado, lo ejecutado y lo verificado.
  No reportar una carga, prueba, despliegue o métrica sin evidencia.
- No publicar, hacer commits, desplegar ni enviar información a terceros solo
  porque esta guía los mencione como entregables. Seguir la autorización del
  usuario y completar el trabajo que sí está dentro del alcance.

## 2. Problema de negocio y fuentes de verdad

Tres comercializadoras comparten un CRM. La solución debe convertir fuentes
heterogéneas en una cola diaria de leads priorizados, enriquecida con información
explícita de conversaciones y aislada por empresa.

Consultar:

- `inicio-datos/Assessment-Analista-IA-Enunciado.pdf`: enunciado de la prueba.
- `inicio-datos/analisis.md`: resumen de requisitos y rúbrica; algunas decisiones allí pueden
  ser anteriores a las instrucciones más recientes del usuario.
- `inicio-datos/docs/modelo_datos/README.md`: diccionario y decisiones de persistencia.
- `inicio-datos/docs/modelo_datos/modelo_datos.mmd`: relaciones y campos principales.
- Notebooks y manifiestos de cada etapa: evidencia de transformaciones y resultados.

Ante una discrepancia, distinguir el requisito del evaluador, una hipótesis
documentada y una decisión posterior del usuario. No atribuir al enunciado
decisiones que tomó el proyecto.

## 3. Requisitos y criterios de evaluación

### Alcance funcional obligatorio

1. Ingerir las fuentes sin edición manual de los datos.
2. Normalizar formatos y consolidar duplicados entre canales de una misma empresa.
3. Extraer con IA información comercial explícita y conservar evidencias.
4. Priorizar con lógica explicable y contrastada con el histórico.
5. Persistir en una base de datos real con esquema propio y versionado.
6. Ejecutar el flujo completo con un único disparo reproducible.
7. Publicar una URL funcional para demostrar el resultado.
8. Impedir que una empresa vea clientes de otra.

Un notebook y archivos planos no sustituyen los requisitos de persistencia,
automatización ni publicación.

### Rúbrica y evidencia esperada

| Bloque | Peso | Evidencia que debe poder mostrarse |
|---|---:|---|
| Entendimiento del negocio | 10 | Objetivo, población, señales y decisiones justificadas. |
| Datos y base de datos | 15 | Normalización, incidencias, esquema, claves, carga y conciliación. |
| Automatización y orquestación | 15 | Un comando/evento, configuración, reintentos seguros y logs. |
| Componente de IA | 20 | Extracción con evidencia, validación y evaluación honesta del scoring. |
| Ingeniería y repositorio | 12 | Código mantenible, pruebas pertinentes, dependencias e historial real. |
| Despliegue y publicación | 10 | URL operativa y configuración reproducible del servicio. |
| Producto y usabilidad | 6 | Cola clara, explicación y acciones útiles para el asesor. |
| Documentación | 5 | README ejecutable, decisiones, supuestos y limitaciones. |
| Sustentación y comunicación | 7 | Capacidad de explicar y demostrar el código y sus resultados. |

Entregables: repositorio accesible, URL pública funcional, README, diagrama de
arquitectura y presentación de máximo ocho diapositivas. El historial de commits
debe reflejar trabajo real; no fabricar commits retrospectivos ni evidencia.

Evitar los motivos de descalificación descritos en el enunciado: faltar al
repositorio o URL, exponer credenciales o datos personales reales, no poder
explicar el código, entregar una solución sin adaptación y tener una URL que no
funcione en la sustentación.

## 4. Estado y decisiones técnicas actuales

- Lenguaje: Python; usar el entorno virtual del proyecto y comprobar su versión.
- Base de datos elegida por el usuario: PostgreSQL de Supabase, mediante SQL.
- Plataforma y API elegidas: Django + Django REST Framework en `plataforma/`.
  El paquete de configuración también se llama `plataforma`.
- IA de conversaciones: Gemini; conservar las versiones reales en los artefactos.
- Modelo tabular elegido para continuar: regresión logística comercial sin pesos,
  como referencia experimental. No hay mejora concluyente demostrada para despliegue.
- Prioridad operativa actual: reglas explícitas; score ML separado.
- La automatización vive en `auto-inicio-datos` con `run.py` en la raíz.
  Los notebooks de `inicio-datos` son evidencia histórica y estudio.

### Ubicaciones actuales

| Ruta | Propósito |
|---|---|
| `inicio-datos/notebooks/01_02_importacion_datos.ipynb` | Ingestión, limpieza y consolidación. |
| `inicio-datos/notebooks/03_extraccion_ia_piloto.ipynb` | Extracción, revisión y descarte por inconsistencias. |
| `inicio-datos/notebooks/04_clasificacion_priorizacion.ipynb` | Entrenamiento, evaluación, balanceo y conclusiones. |
| `inicio-datos/data/processed/` | Resultados intermedios y manifiestos. |
| `inicio-datos/outputs/clasificacion_04/` | Artefactos y métricas de la primera iteración. |
| `inicio-datos/outputs/clasificacion_04/desbalance_v2/` | Comparación con/sin pesos y revisión posterior. |
| `inicio-datos/docs/modelo_datos/` | Diseño relacional de 20 tablas y diagrama. |
| `tmp/` | Herramientas temporales; no depender de ellas en producción. |

Punto 05: scripts `inicio-datos/docs/modelo_datos/05_crear_db.py` y `05_cargar_db.py`, con
migraciones SQL, configuración de entorno y modo `--validar`. Consultar
`inicio-datos/docs/modelo_datos/EJECUCION_05.md`. No asumir que ya se ejecutaron remotamente:
verificar la evidencia de carga. Crear tablas en Supabase no implica crear otro
proyecto de Supabase ni una nueva base administrada.

No cambiar nombres o mover archivos silenciosamente: actualizar también rutas,
documentación y referencias afectadas.

## 5. Principios de diseño: Clean Code, KISS y pragmatismo

- **KISS:** resolver el caso actual con el menor número razonable de componentes.
- **YAGNI:** no agregar abstracciones, motores, colas, frameworks o infraestructura
  para necesidades hipotéticas.
- **Responsabilidad única:** separar lectura, transformación, validación,
  persistencia y presentación. Una función debe tener un propósito reconocible.
- **DRY con criterio:** extraer reglas de negocio repetidas y propensas a divergir;
  no crear un framework por dos fragmentos parecidos.
- **SOLID cuando aporte valor:** contratos pequeños, composición y dependencias
  explícitas; no exigir clases, interfaces o herencia para funciones sencillas.
- Mantener transformaciones puras cuando sea práctico. Encapsular efectos de E/S
  en límites claros para facilitar pruebas y reuso.
- No hacer conexiones, entrenar, cargar datos o leer secretos al importar módulos.
- Preferir nombres descriptivos, retornos tempranos y estructuras simples a
  anidamientos profundos y expresiones compactas difíciles de estudiar.
- No imponer límites artificiales de líneas por función; dividir cuando cambien
  responsabilidad o nivel de abstracción.
- Evitar estado global mutable, dependencias ocultas y argumentos de tipo `dict`
  sin contrato cuando un tipo pequeño y explícito sería más claro.
- Usar clases solo para representar estado o comportamiento que lo justifique.
- No introducir patrones de repositorio, fábrica o inyección sofisticada sin una
  necesidad concreta. Pasar una conexión o configuración como argumento suele bastar.
- Los scripts numerados son entradas CLI; la lógica reutilizable debe vivir en
  módulos importables con nombres válidos, no importando `05_...` como paquete.

## 6. Estilo Python: PEP 8 y Google Python Style Guide

### Convenciones del proyecto

- Cuatro espacios, UTF-8 y nombres sin caracteres ambiguos. Funciones/variables
  en `snake_case`, clases en `PascalCase`, constantes en `UPPER_SNAKE_CASE`.
- Código nuevo: máximo 79 caracteres por línea; texto de comentarios y docstrings
  alrededor de 72. URLs y contenido indivisible pueden exceptuarse justificadamente.
  Esta decisión resuelve la diferencia entre los anchos sugeridos por las guías.
- Usar paréntesis para continuaciones y evitar instrucciones múltiples por línea.
- Imports al inicio: biblioteca estándar, terceros y proyecto; sin `import *`.
- Usar `is None`, context managers y argumentos mutables con valor inicial `None`.
- Comparaciones y comprensiones deben ser fáciles de leer; usar un bucle si hay
  múltiples efectos o condiciones complejas.
- Type hints en funciones públicas, límites de módulos y estructuras compartidas.
  No usar `Any`, `cast` o `# type: ignore` para ocultar incompatibilidades reales.
- Mantener los nombres de dominio existentes en español, como `empresa_id`,
  `lead_consolidado_id` y `descartada`. No renombrarlos para traducirlos a inglés.
  En código nuevo, mantener coherencia de idioma dentro de cada módulo.
- Comentarios y explicación del proyecto en español claro. Comentar decisiones,
  restricciones y razones, no repetir literalmente lo que hace una línea.
- Preferir `pathlib.Path`; no incrustar rutas absolutas del equipo en código.
- Comparar flotantes con tolerancia adecuada; dinero con `Decimal`/`NUMERIC`.
- No usar `assert` para validar entradas externas o permisos en código operativo:
  lanzar excepciones explícitas. Los asserts sí son apropiados en pruebas.

### Docstrings de estilo Google

Documentar módulos, funciones públicas, clases y lógica privada no trivial.
Usar comillas triples dobles y resumen breve. Incluir, cuando aplique:
`Args`, `Returns`, `Yields`, `Raises` y `Attributes`. No crear secciones vacías
ni duplicar innecesariamente los tipos ya presentes en la firma.

Explicar precondiciones, significado de los valores, unidades, efectos laterales
y manejo de desconocidos. Las excepciones documentadas deben coincidir con el
comportamiento real. Evitar comentarios ornamentales o ejemplos que se desactualicen.

Ejemplo de convención, no código pendiente de implementación:

```python
def validar_empresa(empresa_id: str, empresa_lead: str) -> None:
    """Comprueba que un registro pertenece a la empresa del lead.

    Args:
        empresa_id: Empresa declarada por el registro relacionado.
        empresa_lead: Empresa de la identidad consolidada.

    Raises:
        ValueError: Si falta una empresa o los identificadores difieren.
    """
    if not empresa_id or not empresa_lead:
        raise ValueError("La empresa es obligatoria para este vínculo.")
    if empresa_id != empresa_lead:
        raise ValueError("El registro y el lead pertenecen a empresas distintas.")
```

Las guías orientan el estilo; no justifican reescribir todo el código histórico
en una tarea pequeña. Mejorar el área intervenida sin alterar resultados previos.

## 7. Reglas de datos que no se deben perder

- Conservar las fuentes originales. La limpieza genera derivados reproducibles.
- Nunca fusionar identidades entre empresas, aunque coincidan nombre y teléfono.
- Mantener consulta original y cliente consolidado como niveles distintos.
- No completar hechos por intuición. Conservar desconocidos, ambigüedades y evidencia.
- Fechas de salida en año–mes–día; día–mes–año puede interpretarse cuando la fuente
  lo sustente. No usar mes–día–año como presentación de salida.
- Si la evidencia obliga a invertir día/mes, revisar coherencia entre registro y
  contacto del mismo lead; no aplicar la inversión globalmente a otras personas.
- Conservar precisión temporal. Una fecha sin hora no es evidencia de medianoche.
- Teléfonos como texto. Distinguir inválido, desconocido y utilizable. No usar un
  teléfono compartido entre empresas como identidad global.
- Cada eliminación debe dejar motivo y trazabilidad. El registro «prueba prueba»
  previamente excluido no debe reaparecer como cliente activo.
- Conservar todos los modelos de moto mencionados, aunque no estén en catálogo.
- Una consulta descartada en CRM no equivale a una conversación descartada por calidad.
- Conversaciones descartadas con vínculo válido: guardar flag `descartada`,
  motivos y contenido; excluir de la vista utilizable y del scoring activo.
- Conversaciones sin vínculo verificable: revisión externa, sin importar su
  conversación, mensajes, extracciones o intereses a la base. No crear entidades
  ficticias para satisfacer claves foráneas.
- No repartir unidades del catálogo entre sedes: no se conocen esas cantidades.
- Los 179 históricos sin gestión no son negativos de entrenamiento; conservarlos
  en almacenamiento con su etiqueta real. Los conteos son referencias de la versión
  actual, no valores que deban imponerse a futuras fuentes.

## 8. SQL, Supabase y persistencia

- Implementar el esquema acordado de `inicio-datos/docs/modelo_datos/`; mantener sincronizados
  diccionario, diagrama y migraciones si se modifica una relación.
- Separar creación/migración y carga en los dos scripts `05` solicitados.
- Usar migraciones versionadas y detectar incompatibilidades. `CREATE TABLE IF
  NOT EXISTS` por sí solo no actualiza una tabla con estructura antigua.
- No usar `DROP`, `TRUNCATE`, recreación destructiva o borrado masivo como mecanismo
  normal de recarga. Una operación destructiva debe estar explícitamente solicitada.
- Claves primarias, foráneas, restricciones únicas y `CHECK` deben representar el
  contrato; no depender solamente de validaciones Python.
- Asegurar empresa mediante relaciones compuestas, no solo columnas independientes.
  Comprobar también que el contexto de una prioridad pertenezca al mismo lead.
- SQL parametrizado para valores; identificadores dinámicos mediante mecanismos
  seguros del driver y listas permitidas, nunca interpolación de texto recibido.
- Transacciones para cambios que deban ser atómicos. Si falla la carga, revertirla
  y registrar el diagnóstico después de la reversión o fuera de esa transacción.
- Carga idempotente: reintentar mismo contenido/configuración no duplica filas.
  Usar claves naturales/huellas estables y políticas explícitas de actualización.
- Versionar extracciones, modelos y prioridades; no sobrescribir historia de un
  método distinto. Conservar el artefacto que realmente generó cada score.
- Usar columnas relacionales para claves, filtros y reglas de integridad. JSONB
  para contratos estructurados, evidencia y auditoría; no meter todo en un blob.
- Las tablas derivadas de un JSON deben generarse de forma atómica y verificarse
  contra él. No permitir ediciones independientes que creen divergencias.
- Crear índices para consultas reales, incluido `(empresa_id, descartada)`.
- La vista vigente solo debe exponer ejecuciones completadas y coherentes; no
  mezclar una carga fallida con resultados anteriores sin una política documentada.
- Configurar límites de tiempo de conexión/consulta y tamaño razonable de lotes.
  Reintentar solo errores transitorios, con límite y operaciones idempotentes.
- No llamar «persistencia verificada» a generar un SQL o abrir una conexión:
  comprobar escritura, lectura, conteos e integridad en la instancia objetivo.
- Si no hay conexión o credenciales, completar código y verificaciones locales
  autorizadas, y declarar la validación remota pendiente.

## 9. Seguridad, secretos y separación por empresa

- Secretos exclusivamente en entorno o gestor de secretos. `.env` permanece
  excluido de Git; `.env.example` contiene nombres y valores vacíos o ficticios.
- Al editar `.env`, preservar valores existentes y añadir solo variables que el
  código utilice. No imprimir el archivo, DSN, contraseñas, tokens o API keys.
- Configuración tipada y centralizada; fallar con nombres de variables faltantes,
  nunca con sus valores. Evitar exigir claves HTTP de Supabase si solo se usa SQL.
- Mantener cifrado/verificación de la conexión según la configuración soportada;
  no resolver un error de conexión desactivando seguridad silenciosamente.
- Credenciales privilegiadas de carga solo en el backend o proceso administrativo.
  Nunca incluir service keys o credenciales SQL en navegador, notebooks guardados,
  respuestas HTTP, trazas públicas, ejemplos o capturas.
- El rol de carga y el rol de la aplicación no deben asumirse equivalentes.
  Usar el mínimo privilegio necesario para cada uno.
- Para datos expuestos mediante Supabase, definir permisos y políticas de acceso
  por fila cuando corresponda. Comprobar el comportamiento con los roles reales,
  incluidas las tablas hijas, vistas y rutas indirectas.
- No afirmar aislamiento porque las tablas tengan `empresa_id` o porque una
  consulta administrativa filtre correctamente. Probar acceso denegado entre empresas.
- Resolver el ámbito de empresa desde la identidad autenticada y autorizada, no
  confiar en un `empresa_id` enviado por el cliente como prueba de permiso.
- Los logs, incidencias y originales también pueden revelar datos de otras
  empresas. No exponerlos sin controles de acceso.
- Registrar conteos, IDs técnicos y códigos de error; evitar cuerpos completos
  de mensajes, teléfonos, correos y respuestas sensibles en logs rutinarios.
- Si aparece una credencial en un archivo, no repetirla en el reporte. Corregir
  la exposición dentro del alcance y comunicar si requiere rotación al usuario.

## 10. Extracción de IA y evaluación de modelos

- Contrato JSON fijo y validado. Registrar proveedor/modelo y versiones de prompt,
  esquema y normalizador junto con hashes de fuente/configuración.
- Cada afirmación comercial debe tener evidencia del emisor correcto. Oferta del
  asesor no es solicitud del cliente; silencio no es rechazo; empleo no es crédito
  aprobado; ausencia de importe no equivale a cero.
- Validar estructura y semántica: mensajes citados existentes, autor, importes,
  rangos, signos, modelos y contradicciones. No confiar solo en JSON bien formado.
- Usar caché y reanudación por huella para no consumir cuota duplicada. Limitar
  concurrencia y reintentos; respetar presupuesto gratuito/configurado.
- No llamar a una API al importar módulos ni reextraer todo cuando basta validar
  resultados existentes. Consultar disponibilidad vigente antes de cambiar de modelo.
- Separar entrenamiento, selección y evaluación. Preprocesamiento y pesos de clase
  se ajustan solo con entrenamiento; no contaminar con validación o prueba.
- No usar resultados futuros, contactos acumulados u otras señales posteriores
  como si existieran al momento de priorizar.
- Métricas principales según propósito: AP y concentración de cierres a capacidad
  fija; exactitud sola es engañosa con clases desbalanceadas.
- Comparar con referencias sencillas, documentar empates, tamaño de muestra y
  desempeño por empresa. Ponderar clases no garantiza un mejor ranking.
- Julio ya fue explorado: no presentarlo otra vez como conjunto independiente nuevo.
- No cambiar criterio de selección después de ver resultados para forzar una mejora.
- Registrar semilla, periodos, features, configuración, métricas y versiones.
- Cargar únicamente artefactos de modelo de confianza. Verificar su hash y contrato.
- No equiparar score, probabilidad calibrada y efecto causal de contactar a alguien.
- Resultados negativos también son entregables válidos: explicar límites y decisión.

## 11. Automatización, CLI y errores

- Entradas CLI con `main()` y guardia `if __name__ == "__main__":`.
- Configuración explícita desde entorno/argumentos; ninguna edición manual de
  fuentes o celdas debe ser necesaria en el flujo final.
- Prever un comando de punta a punta que invoque etapas reutilizables, sin copiar
  reglas entre notebooks y scripts. Implementarlo cuando corresponda al punto 06.
- Ejecutar desde raíz o resolver rutas de manera estable respecto al proyecto;
  no depender accidentalmente del directorio de trabajo del usuario.
- Logs con etapa, ejecución, cantidades, duración y estado. `print` puede servir
  para un resumen CLI; usar `logging` para diagnóstico operativo.
- Salida de proceso no cero ante fallo. No capturar `Exception` para continuar
  silenciosamente, devolver éxito falso o dejar resultados parcialmente válidos.
- Capturar excepciones específicas cerca de donde pueden resolverse. En el límite
  CLI, convertir fallos en un mensaje útil y sanitizado conservando causa interna.
- Usar escrituras atómicas para manifiestos finales; no marcarlos como completados
  antes de confirmar las operaciones correspondientes.
- Proteger contra cargas simultáneas incompatibles cuando exista ese riesgo;
  evitar añadir coordinación distribuida si basta una ejecución única.

## 12. Pruebas y herramientas de calidad

Preferir pocas pruebas que detecten fallos reales a muchas pruebas que reproduzcan
la implementación. No imponer un porcentaje de cobertura sin relación con riesgos.

### Casos que sí merecen pruebas

- Misma persona en empresas diferentes permanece separada.
- Consulta/conversación/prioridad con empresa o lead cruzado es rechazada.
- Descartada válida se conserva y filtra; huérfana permanece fuera de la base.
- Diferencia entre dato ausente, cero y negativa explícita.
- Interpretación de fechas sin inventar precisión o invertir otros leads.
- Referencias de evidencia y normalización de importes.
- Repetición de carga, actualización permitida, versiones y rollback ante fallo.
- Estado fallido no se publica como resultado vigente.
- Ejecución en entorno nuevo con las dependencias y configuración documentadas.
- API/vistas no permiten lectura de clientes ni hijos de otra empresa.

### Tipos de comprobación

- Unitarias para transformaciones y reglas puras con datos sintéticos pequeños.
- Integración contra PostgreSQL de prueba para restricciones, transacciones e
  idempotencia; no dar por equivalente SQLite para validar comportamiento SQL.
- Prueba de humo de CLI y lectura posterior cuando esté autorizada la ejecución.
- End-to-end del flujo y del aislamiento antes de declarar lista la entrega.

No ejecutar pruebas destructivas sobre el proyecto remoto real. Usar un destino
de pruebas aislado y verificar su configuración. No llamar servicios facturables
o consumir cuota como parte de pruebas unitarias.

### Herramientas recomendadas para introducir gradualmente

- `ruff` para lint, imports y formato, configurado con el ancho acordado.
- `pytest` para pruebas; `mypy` o equivalente para contratos relevantes cuando
  aporte valor y esté configurado.
- `pyproject.toml` como configuración central de estas herramientas cuando se
  incorporen. Convención de docstrings Google; evitar reglas incompatibles entre sí.
- Dependencias declaradas y versionadas de forma reproducible. No instalar paquetes
  globales ni añadir herramientas por apariencia sin usarlas.

No asumir que estas herramientas ya están instaladas/configuradas. Informar qué
comprobaciones se hicieron realmente. Una validación de sintaxis no demuestra que
el código funcione ni que conecte a Supabase.

## 13. Notebooks, documentación y experiencia de estudio

- Explicar antes del código el objetivo, la razón de la decisión y sus supuestos.
- Después de resultados, explicar qué se observa y qué no puede concluirse.
- Celdas en orden ejecutable; sin depender de variables ocultas de otra sesión.
- Conservar salidas del usuario. Celdas nuevas no ejecutadas deben quedar sin
  contador/salidas y con estado pendiente, no con resultados anteriores simulados.
- Separar evidencia histórica de conclusiones nuevas. No alterar métricas guardadas
  para que coincidan con una hipótesis o una explicación.
- Mover lógica operativa estable a módulos reutilizables cuando corresponda;
  mantener notebooks como demostración y estudio de esa lógica.
- README con instalación, variables sin secretos, comandos reales, esquema,
  ejecución, pruebas, despliegue, decisiones, supuestos y pendientes.
- Distinguir archivos generados de código fuente. Documentar cómo regenerarlos
  y su versión; no editar CSV procesados a mano para resolver casos puntuales.
- Mantener el diagrama de arquitectura separado del diagrama de datos: responden
  a preguntas diferentes aunque ambos sean entregables de documentación.
- El producto debe mostrar prioridad, motivo y siguiente acción de forma clara;
  no exponer detalles de implementación que no ayuden al asesor.

## 14. Flujo de trabajo y definición de terminado

### Antes de cambiar

1. Entender el alcance y respetar las restricciones de ejecución del usuario.
2. Leer archivos relevantes y comprobar cambios existentes; no asumir rutas de
   memoria ni leer `.env` completo en una salida visible.
3. Identificar contratos, fuentes, riesgos de integridad y resultados esperados.
4. Elegir una solución pequeña y verificable. Preguntar solo si falta una decisión
   indispensable; no repetir decisiones ya autorizadas.

### Durante el trabajo

1. Comunicar hallazgos y decisiones en español claro.
2. Mantener cambios cohesionados y explicar motivos cuando afecten resultados.
3. Actualizar documentación y pruebas pertinentes al mismo tiempo que el código.
4. No ampliar el alcance a entrenamientos, limpiezas, despliegues o reestructuras
   no solicitadas por conveniencia del agente.

### Antes de dar por terminado

- Código cumple el contrato y conserva las decisiones de negocio.
- No hay secretos nuevos en archivos versionables ni en salidas.
- Se completaron las verificaciones apropiadas que estaban autorizadas.
- Se reportan por separado verificaciones pendientes y límites conocidos.
- Documentación refleja comportamiento real, rutas y comandos vigentes.
- Para el punto 05: esquema aplicado, datos cargados, lectura e integridad verificadas
  en Supabase; si solo se generaron scripts, declarar implementación pendiente de ejecución.
- Para la entrega completa: ejecución automática, DB real, URL operativa,
  aislamiento comprobado y materiales de sustentación disponibles.

La respuesta final debe decir qué cambió, dónde está, cómo se verificó y qué falta.
No declarar finalizado un requisito solo porque se escribió el código.

## 15. Referencias de estilo

- [PEP 8: convenciones de código Python](https://peps.python.org/pep-0008/).
- [PEP 257: convenciones de docstrings](https://peps.python.org/pep-0257/).
- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html).

Las convenciones específicas de este repositorio resuelven diferencias entre
estas guías. Aplicarlas con criterio para mejorar legibilidad y corrección, no
como excusa para introducir complejidad o cambios ajenos a la tarea.

## 16. Organización después del punto 06

- `inicio-datos/` conserva el desarrollo de 1–5; no reejecutar ni reescribir
  notebooks por cambios del flujo operativo.
- `auto-inicio-datos/` contiene las etapas Python numeradas, `utils/`,
  fuentes operativas, caché y pruebas. No depende de notebooks ni de `tmp/`.
- `run.py` ejecuta las cinco etapas y acepta `--watch` por cambios de archivos.
- Las credenciales permanecen en el `.env` de la raíz.
- Ejecutar Ruff y unittest según `auto-inicio-datos/README.md`.
- Un modo `--sin-db` válido no demuestra persistencia remota. El servicio
  permanente o su horario no quedan activos por generar el código.
- Mantener la migración inicial inmutable; nuevas modificaciones SQL deben
  ir en otra migración. Las copias históricas documentan el estado del paso 5.
