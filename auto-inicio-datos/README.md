# Flujo automático: puntos 1 a 5

`../run.py` es la entrada del punto 6. Ejecuta los scripts en orden, sin Jupyter,
sin ejecutar notebooks y sin depender de `inicio-datos` durante la ejecución.
Los notebooks originales permanecen como evidencia y material de estudio.

## Uso

Desde la raíz del repositorio, con Python 3.11:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py
```

La instalación es preparación del entorno, no un paso manual de cada carga.
Las credenciales se leen del `.env` de la raíz o del entorno del proceso;
el entorno prevalece. `.env.example` contiene las variables sin secretos.

### Opciones de ejecución

```powershell
# Recorrer todo el flujo, con lectura/escritura SQL y solo caché de Gemini:
.\.venv\Scripts\python.exe run.py --sin-api

# Recorrer todo el flujo y validar el lote sin conectar a servicios:
.\.venv\Scripts\python.exe run.py --sin-api --sin-db

# Datos externos: proporcionar los cinco archivos del conjunto completo:
.\.venv\Scripts\python.exe run.py --fuentes C:\datos\entrada

# Mantener un proceso que dispare el flujo al detectar cambios:
.\.venv\Scripts\python.exe run.py --watch --intervalo 60
```

También funciona con ruta absoluta desde otro directorio. `--sin-api` falla
si una conversación necesita una respuesta nueva; no inventa resultados.
`--sin-db` nunca publica el estado de persistencia completada.

## Estructura y responsabilidades

| Archivo/carpeta | Responsabilidad |
|---|---|
| `01_ingerir.py` | Leer los cinco archivos y registrar cantidades. |
| `02_normalizar.py` | Teléfonos, fechas, categorías, relaciones, duplicados por empresa, exclusiones e incidencias. |
| `03_extraer_ia.py` | Extracción con Gemini, validación, evidencias y separación de conversaciones descartadas. |
| `04_priorizar.py` | Reglas operativas y regresión logística experimental de configuración fija. |
| `05_persistir.py` | Validar el lote, aplicar migraciones y cargar/reconciliar Supabase. |
| `utils/` | Orquestación, reglas, contratos y persistencia reutilizables. |
| `utils/migrations/` | SQL versionado; la migración inicial es idéntica a la aplicada en el punto 5. |
| `data/raw/` | Entrada operativa inicial, copiada de las fuentes preservadas. |
| `outputs/extraccion_ia_v2/` | Caché inicial de Gemini y bitácora compartida. |
| `ejecuciones/<huella>/` | Instantánea de entrada, procesados, modelos, controles y resúmenes de cada versión. |
| `ultima_exitosa.json` | Referencia a la última ejecución que confirmó la carga SQL. |
| `tests/` | Pruebas locales; no consumen API ni conectan a Supabase. |

Cada script acepta `--trabajo <directorio>` para diagnóstico. El uso habitual es
`run.py`, que prepara ese directorio y ejecuta todas las etapas automáticamente.

## Disparo por evento y programación

El modo `--watch` observa contenido, no solo fechas de modificación. Espera dos
lecturas iguales antes de ejecutar, copia las fuentes a una instantánea y vuelve
a verificar sus hashes. Así evita procesar una copia todavía en curso.

Al iniciar procesa el conjunto estable; después solo vuelve a ejecutar cuando
cambian las fuentes o el código. Si falla, reintenta en el siguiente intervalo
y conserva el avance. El bloqueo impide dos orquestadores simultáneos en esta
instalación, y PostgreSQL añade un bloqueo transaccional del esquema.

Para dejarlo funcionando debe mantenerse ese proceso activo, preferiblemente
supervisado por el servicio o plataforma donde se despliegue. **La reorganización
no instala ni deja activo un servicio permanente en el equipo.**

Para ejecución programada, un programador de tareas puede invocar directamente
el Python del entorno con la ruta absoluta de `run.py`. No necesita activar un
entorno interactivo ni ejecutar los cinco scripts individualmente. El horario y
la plataforma de despliegue quedan por definir; no se ha registrado una tarea
del sistema ni una automatización de la aplicación Codex.

## Reanudación, integridad y estados

1. La huella de ejecución incluye fuentes, código, migraciones y versiones de
   dependencias. Las fuentes originales no se modifican.
2. Cada etapa registra sus productos y hashes. Un checkpoint se reutiliza solo
   si todos sus archivos siguen presentes e intactos.
3. Un cambio o una salida incompleta invalida esa etapa y las posteriores.
4. Un fallo detiene la secuencia y devuelve código distinto de cero. Los errores
   registran tipo y ubicación, sin credenciales, valores privados ni mensajes
   completos del driver/API.
5. El paso SQL siempre vuelve a comprobar la carga, incluso si los anteriores
   se reutilizan. La migración y la carga son repetibles sin duplicar el mismo
   lote. Se reintentan hasta tres veces los errores de conexión SQL.
6. `ultima_exitosa.json` se actualiza solo después de la confirmación SQL. Los
   archivos parciales quedan en su carpeta de ejecución y no se anuncian como
   última versión completada.

Estados: `en_curso`, `fallida`, `validada_sin_db` y `completada`.
Cada intento conserva su manifiesto en `intentos/`; `ejecucion.json` sirve como
índice del último intento para reanudar. Una repetición fallida no sobrescribe
el manifiesto del intento exitoso anterior.
Los manifiestos se publican mediante reemplazo atómico. Un fallo durante una
exportación deja el checkpoint incompleto y fuerza su reconstrucción.

Se reciben **instantáneas completas**, no archivos parciales de novedades.
La carga rechaza la desaparición silenciosa de entidades ya persistidas.
Una futura política de bajas necesita definición explícita.

## Decisiones conservadas

- Misma persona en empresas diferentes: identidades separadas.
- Fechas ISO, sin inventar horas ni invertir globalmente fechas de otros leads.
- Modelos de moto declarados se conservan aunque no coincidan con el catálogo.
- El registro de prueba se excluye con motivo y trazabilidad.
- Conversaciones inconsistentes vinculadas se almacenan con `descartada`.
- Las conversaciones sin pertenencia verificable y sus incidencias relacionadas
  quedan en `outputs/persistencia_05/revision_fuera_db.json` de la ejecución.
- No se completan declaraciones por intuición: se conservan citas y desconocidos.

## IA y cuota

Se conserva el modelo, prompt y contrato aprobados en el notebook. La huella de
caché incluye mensajes, modelo, prompt, esquema y normalizador. Los vínculos al
CRM y la correspondencia con el catálogo se actualizan usando las fuentes de
la ejecución, aunque se reutilice la extracción.

Las peticiones nuevas se agrupan por empresa, con un máximo de cinco
conversaciones. Se conserva el ritmo de 6,1 segundos entre inicios y un límite
local de 240 intentos por fecha UTC. La bitácora sobrevive a los reinicios.
Estos topes son defensas locales, no una garantía de cuota concedida por Google.
Al agotar cuota se detiene sin cargar un lote incompleto; `--watch` permite
reintentar automáticamente. La caché evita repetir peticiones completadas.

El piloto y las revisiones humanas quedan en `inicio-datos`; no se presentan
como revisiones humanas nuevas durante cada ejecución automática.

## Modelo tabular: por qué no repetir toda la experimentación

La selección ya se realizó: regresión logística comercial, `C=1`,
`class_weight=None`, semilla 42. El script reajusta **esa configuración** con
marzo–junio de 2026, excluyendo los históricos sin desenlace observado. Conserva
los 2.200 históricos en la base aunque algunos no sirvan para entrenar.

No vuelve a comparar candidatos ni afirma una evaluación independiente sobre
julio. Las comparaciones con balanceo, métricas y gráficos originales permanecen
en `inicio-datos`. La ficha nueva registra fuentes, configuración y versiones.

Se registra un artefacto experimental por ejecución, sin copiar como nuevas las
tres versiones históricas del notebook. Las versiones anteriores permanecen en
Supabase. La cola operativa usa las mismas reglas explicables y mantiene el score
del modelo separado. El período fijo pertenece a esta prueba técnica; para una
operación futura con nuevos meses debe definirse un protocolo de reentrenamiento.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m ruff check auto-inicio-datos run.py
.\.venv\Scripts\python.exe -m ruff format --check auto-inicio-datos run.py
.\.venv\Scripts\python.exe -m unittest discover -s auto-inicio-datos/tests -v
```

Las pruebas cubren detención, reanudación, productos alterados, entrada cambiante,
bloqueo concurrente y eventos estables. El resultado de las verificaciones reales
se documenta en [VERIFICACION.md](VERIFICACION.md).
