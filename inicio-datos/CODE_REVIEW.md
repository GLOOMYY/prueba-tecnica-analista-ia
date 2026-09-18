# CODE REVIEW — `prueba-tecnica-analista-ia`

Revisión como Senior SWE (QA + Code Review). Alcance: todo el código existente
(`notebooks/01_importacion_datos.ipynb`, `tmp/revision_pendientes/build.mjs`,
`data/processed`, `.env`, `api`, config de git). Fecha de revisión: 17-sep-2026.
No se modificó ningún archivo del repo en la revisión.

---

## 1. SEGURIDAD

**S1 — CRÍTICO: API key real expuesta en el workspace**
- Archivo: `.env:1` y `api:3`
- Ubicación: clave `API_KEY_GEMINI=[CREDENCIAL OMITIDA]`;
  en `api` hardcodeada en `X-goog-api-key` para `gemini-flash-latest` que llama a
  `https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent`.
- Explicación: es una llave real de Gemini sin revocar, en claro, en dos archivos.
  Hoy no se indexaría en git gracias a `.gitignore`, pero la prueba descalifica
  explícitamente "Exponer credenciales, llaves de API... en el repositorio", y basta
  un `git add -f`, una copia del directorio o un ticket para filtrarla. El
  `.gitignore` es la única protección; la llave no está revocada.
- Solución: rotar/revocar la llave de inmediato, eliminarla de `.env` y `api`,
  cargarla solo desde variables de entorno del runtime (o secret manager), añadir
  `.env.example` y leerla con `os.environ`/`python-dotenv`. Nunca versionarla.

**S2 — MEDIO: `api` sin extensión y con URL fija de Google**
- Archivo: `api`
- Explicación: script de prueba suelto con credenciales incrustadas; su nombre sin
  extensión es ruido en el repo.
- Solución: borrarlo o convertirlo en un script que lea la key de variables de entorno.

---

## 2. ARQUITECTURA

**A1 — CRÍTICO: toda la ETL vive en un solo notebook (no cumple automatización)**
- Archivo: `notebooks/01_importacion_datos.ipynb` (38 celdas, ~1.500 líneas de lógica real)
- Explicación: `analisis.md` es taxativo: "El proceso completo se ejecuta con un solo
  disparo... Un notebook que se corre celda por celda no cumple". Toda la ingesta,
  normalización, deduplicación y exportación están en celdas con `display()` y
  dependencia de estado entre celdas. No hay `requirements.txt`, no hay runner, no hay
  script de orquestación.
- Solución: extraer la lógica a un paquete `src/` (módulos: `normalizacion.py`,
  `fechas.py`, `identidad.py`, `exportar.py`) con un `pipeline.py`/`main.py`
  ejecutable con un comando, más `requirements.txt` fijado. Puente inmediato:
  `papermill` o `nbconvert --execute` en un `.py`/CI.

**A2 — ALTO: `tmp/revision_pendientes/datos.json` es curado a mano**
- Archivo: `tmp/revision_pendientes/datos.json`; generador: `build.mjs`
- Explicación: contiene decisiones ya tomadas por una persona ("Dejar pendiente",
  "Mantener original", "Valor corregido") que ningún paso del notebook produce; luego
  `build.mjs` lo convierte a `outputs/revision_pendientes/pendientes_revision.xlsx`.
  Esto rompe la automatización punta a punta (requisito #6 y condición #1: "sin que
  nadie ejecute pasos a mano") y crea una segunda verdad sobre pendientes (duplicada
  con `incidencias_datos.json`).
- Solución: que el notebook exporte los pendientes a `outputs/` y genere `datos.json`
  como parte del pipeline; el XLSX debe ser un derivado reproducible.

**A3 — ALTO: `build.mjs` con ruta absoluta a Windows y dependencias sin declarar**
- Archivo: `build.mjs:6` — `const out = 'D:/Proyectos/prueba-tecnica-analista-ia/outputs/revision_pendientes';`
- Explicación: dependencia de `@oai/artifact-tool` en `tmp/node_modules/`, ruta
  hardcodeada e imperativa (no ejecutable en otro OS/CI).
- Solución: parametrizar la ruta (argv/`process.env`), añadir `package.json` con los
  deps y un script `npm run build`, o eliminar `build.mjs` en favor de `openpyxl`
  dentro del pipeline Python.

**A4 — ALTO: repositorio sin commits ("No commits yet")**
- Archivo: raíz del repo; `git log` — "your current branch 'main' does not have any
  commits yet"
- Explicación: la prueba exige "historial de commits real (no un único commit final)".
  Hoy no hay ni un commit.
- Solución: iniciar control de versiones ahora, con commits atómicos por etapa
  (ingesta, normalización, fechas, modelos, identidad, export), `.github/workflows`
  para ejecutar, y nunca `git add -f` secretos.

**A5 — MEDIO: sin declaración de dependencias ni versión de entorno**
- Explicación: el notebook corre con un `.venv` local; no existe
  `requirements.txt`/`pyproject.toml`. La reproducibilidad (condición #2 del
  assessment) depende de la máquina del autor.
- Solución: generar `requirements.txt` fijado (o `uv.lock`/`poetry.lock`) y documentar
  el comando de ejecución en el README.

---

## 3. ERRORES FUNCIONALES Y CASOS BORDE

**C1 — MEDIO: `telefono_utilizable` usa `.all()` y castiga identidades con un solo teléfono válido**
- Archivo: notebook, sección 15, celda exec 33 — `'telefono_utilizable': bool(grupo['telefono_estado'].eq('valido').all())`
- Explicación: si una identidad agrupada tiene un teléfono válido y otro
  faltante/inválido, `all()` devuelve `False` y el cliente se marca como no
  contactable aunque exista un número real. Para el scoring/priorización posterior
  (requisito #4) esto puede bajar la prioridad de leads vendibles. Borde realista:
  consulta con teléfono válido + otra con teléfono vacío.
- Solución: usar `any(...)` como `tiene_telefono_utilizable` más un contador
  `telefonos_invalidos`, o agregar el mejor teléfono válido a nivel de identidad.

**C2 — MEDIO: `nombres_compatibles` acepta coincidencia por inicial como "compatible"**
- Archivo: sección 15, `def nombres_compatibles` (~líneas 2247-2273)
- Explicación: `Y. Castaño` + `Yuliana Castaño` → grupo. Dos personas distintas que
  comparten teléfono y coinciden en inicial + apellidos se fusionarían como un único
  cliente. El propio texto lo reconoce como supuesto/limitación, pero la regla ya se
  aplica automáticamente en `consultas_resueltas`. Riesgo comercial de mezclar
  consultas.
- Solución: marcar los grupos resueltos solo o principalmente por inicial para
  revisión humana (capa de "identidad incierta") en lugar de fusionarlos de pleno; el
  XLSX de pendientes es el canal natural para esa revisión.

**C3 — MEDIO: ids efímeros `DUP-###` y `CLI-PROP-###` dependen del orden de ejecución**
- Archivo: secciones 12/14 (`ngroup()+1`, `DUP-001`, `CLI-PROP-001`)
- Explicación: los códigos cambian si llegan nuevos leads o cambia el orden; el
  markdown los usa como referencias estables y quedan serializados en
  `incidencias_datos.json`. Frágil para un pipeline programado (requisito #6).
- Solución: derivar los códigos de un hash estable de `(empresa, teléfono)` (ya existe
  `id_consolidado`); mantener los códigos presentables solo como alias.

**C4 — MEDIO: `incidencias_datos.json` sin idempotencia entre corridas**
- Explicación: cada corrida regenera el archivo completo; con `incidencia_id`
  recomenzando en `INC-000001` no hay trazabilidad temporal ni diff entre corridas.
  Aceptable para la prueba; planificar versionado de incidencias para producción.

**C5 — BAJO: `modelo_interes_texto_normalizado` mezcla "nombre canónico" con "texto limpio"**
- Archivo: sección 9, `emparejar_modelo` (~línea 1267)
- Explicación: la columna `_normalizado` se llena con el nombre del catálogo
  (p. ej. `Honda CB 125F Twister`), no con el texto corregido del lead. Tampoco se
  persiste el `_criterio` para `coincidencia_exacta` (la sección 16 usa default).
- Solución: separar `modelo_normalizado` (texto limpio) de `modelo_canonico`/
  `modelo_sku`.

**C6 — BAJO: aserciones como guardas de integridad**
- Explicación: `assert` se elimina con `python -O`; para un pipeline que "debe poder
  correr solo" convienen excepciones dedicadas (`raise ValueError` con contexto) o
  validación con `pandera`/`great_expectations`. Además, los `raise ValueError` en
  mitad del notebook (sección 13, asesores con ID duplicado) dejan el notebook sin
  estado intermedio legible y sin `try/finally`.

**C7 — BAJO: `fecha_exportable(valor, precision=None)` emite hora 00:00:00 por defecto**
- Archivo: sección 19, `escribir_csv` (`salida[campo].map(fecha_exportable)`)
- Explicación: en columnas datetime que llegan a `escribir_csv` sin su `_precision`
  (p. ej. vía `tabla_exportable` con series faltantes), se escribe `YYYY-mm-dd
  00:00:00` para fechas de solo día, contradiciendo la convención documentada ("Las
  fechas agregadas no deben tratarse como horas exactas"). Las rutas principales lo
  manejan bien con `_precision`; el riesgo es la ruta genérica.
- Solución: derivar la precisión de la columna o pasar `precision` explícito por campo.

---

## 4. BUENAS PRÁCTICAS / DUPLICACIÓN / COMPLEJIDAD

**D1 — MEDIO: lógica de agrupación por `(empresa, teléfono)` duplicada 3 veces**
- Archivos: secciones 12 (`base_duplicados`, `candidatos_duplicados`), 13
  (`referencia_leads` + merge) y 14 (`base_propuestas` → `consultas_candidatas`)
- Explicación: mismas reglas de filtrado (teléfono `valido`, empresa informada),
  mismo `groupby` y mismo orden. Cualquier cambio de regla hay que replicarlo en tres
  sitios.
- Solución: función única `agrupar_por_empresa_telefono(tabla, minimo_duplicados=True)`
  y derivar candidatos/propuestas/referencia de esa única fuente.

**D2 — MEDIO: `revision_telefonos_invalidos` y `marcadores_prueba` duplican el criterio de "utilidad"**
- Explicación: los campos considerados señales útiles están hardcodeados en dos
  bucles (sección 17 y la generación de excepciones). Extraer un
  `es_lead_recuperable(fila)` reutilizable.

**D3 — BAJO: semántica de estados mezclada (`valido`/`valida`)**
- Explicación: `estados_resueltos` mezcla `valido` y `valida`. Funciona, pero obliga
  a comparaciones por string; definir constantes con `Enum`/`Literal` y un esquema único.

**D4 — BAJO: exportación CSV como JSON-in-CSV (listas en columnas)**
- Explicación: `leads.csv` guarda correos/intereses/canales como JSON dentro de celdas
  CSV (sección 19). No es un modelo relacional y complica consultas SQL posteriores.
  El propio README lo reconoce como etapa transitoria; planificar normalización 1NF o
  columnas puente hacia la futura base de datos.

---

## 5. LO QUE ESTÁ BIEN (mantener)

- Trazabilidad: `mapa_origen_consolidado`, `trazabilidad_filas`,
  `trazabilidad_salida_limpia` y `manifest.json` con SHA-256 (con verificación en la
  celda final) dan auditoría sólida.
- Conservador en decisiones de negocio: separación estricta por empresa, no imputa
  faltantes, no "corrige" catálogo, conserva originales en columnas `_original`.
- Reglas de fecha (sección 8) bien documentadas, con `_criterio`/`_precision` por campo.
- Uso de copias (`datos_normalizados`) sin tocar `data/raw`.
- Verificación con asserts al final y validación de SHA de fuentes.

---

## 6. Priorización sugerida

| # | Ítem | Severidad | Acción |
|---|------|-----------|--------|
| S1 | API key sin revocar | CRÍTICO | Rotar ahora |
| A1 | Notebook = única automatización | CRÍTICO | Paquete + runner + CI |
| A2 | `datos.json` curado a mano | ALTO | Generar en pipeline |
| A3 | Ruta absoluta en `build.mjs` | ALTO | Parametrizar |
| A4 | Sin commits | ALTO | Commit incremental + CI |
| C1 | `telefono_utilizable=.all()` | MEDIO | `any` + contador |
| C2 | Inicial = identidad compatible | MEDIO | Capa de revisión humana |
| D1/D2 | Lógica duplicada | MEDIO | Extraer funciones |