# Punto 05: crear y cargar el esquema en Supabase

## Qué está implementado

Los dos scripts solicitados están en esta carpeta:

1. **`05_crear_db.py`**: crea el esquema privado `crm`, aplica las migraciones
   versionadas y verifica que existan las tablas previstas.
2. **`05_cargar_db.py`**: valida las fuentes y carga los datos en una transacción,
   comprobando sus valores antes de confirmar la escritura.

Son entradas pequeñas: la lógica reutilizable vive en `persistencia/` y el SQL
versionado en `migrations/001_inicial.sql`. No requieren Gemini, entrenamiento,
un ORM ni el cliente HTTP de Supabase.

**Estado al 2026-09-17:** punto 05 completado y verificado en Supabase.
Se ejecutaron ambos scripts mediante Session pooler con conexión cifrada.
La carga comparó los valores escritos con sus fuentes antes de confirmar la
transacción. Repetir la migración no aplicó cambios y repetir la carga devolvió
`ya_cargado_y_verificado`, sin duplicar registros.

Supabase ya proporciona una base PostgreSQL. El primer script crea nuestro
**esquema y tablas dentro de esa base**; no crea otro proyecto ni ejecuta
`CREATE DATABASE`.

## 1. Dependencias

Desde la raíz del repositorio, en PowerShell. Las rutas de datos y salidas
que se describen en esta guía son relativas a `inicio-datos/`:

```powershell
.\.venv\Scripts\python.exe -m pip install -r inicio-datos/requirements-db.txt
```

Usar Python 3.11 y el entorno del proyecto. Las dependencias de base de datos
están separadas de las de entrenamiento. Los scripts requieren PostgreSQL 15
o posterior para las vistas que respetan los permisos de quien las consulta.

## 2. Configurar `.env`

Las variables ya se añadieron sin sobrescribir las anteriores. Existe un
`.env.example` sin secretos para documentarlas.

| Variable | Uso | Valor inicial |
|---|---|---|
| `SUPABASE_DB_URL` | URI de conexión PostgreSQL del proyecto. | Vacío: completar. |
| `SUPABASE_DB_SCHEMA` | Esquema propio donde se crean las tablas. | `crm` |
| `SUPABASE_DB_SSLMODE` | Exigir conexión cifrada. | `require` |
| `SUPABASE_DB_CONNECT_TIMEOUT` | Tiempo máximo para conectar, en segundos. | `15` |
| `SUPABASE_DB_STATEMENT_TIMEOUT_MS` | Tiempo máximo por operación SQL, en milisegundos. | `120000` |

Obtener la URI en **Supabase → Connect**. Preferir conexión directa para
migraciones; si la red local no puede acceder por IPv6, usar **Session pooler**.
Copiar host, usuario y puerto de esa pantalla, sin construirlos por intuición.
Reemplazar la contraseña del ejemplo y codificar sus caracteres reservados para
URI. No confundir la URI PostgreSQL con la URL HTTP del proyecto ni con una API
key. [Documentación de conexión de Supabase](https://supabase.com/docs/guides/database/connecting-to-postgres).

La variable del entorno del proceso prevalece sobre `.env`. Revisar esa
precedencia si se está apuntando a un proyecto inesperado. La URI se mantiene
privada y no se imprime, ni siquiera al fallar una conexión.

`require` exige cifrado, pero no equivale a verificar completamente la identidad
del servidor. Se admite `verify-ca` o `verify-full` con la configuración de
certificado de libpq apropiada; una opción más estricta en la URI se respeta.
El código no acepta `disable`, `allow` o `prefer` ni baja SSL para sortear errores.

El usuario SQL necesita crear el esquema y sus objetos. Usar esta credencial
solo como credencial administrativa de backend/carga, nunca en un navegador.

## 3. Validar localmente antes de conectar

```powershell
.\.venv\Scripts\python.exe inicio-datos/docs/modelo_datos/05_crear_db.py --validar
.\.venv\Scripts\python.exe inicio-datos/docs/modelo_datos/05_cargar_db.py --validar
```

- El primero revisa configuración y archivos de migración. No simula ejecución
  SQL ni afirma que el servidor sea compatible.
- El segundo prepara las filas de todas las tablas, revisa manifiestos y
  relaciones y genera el archivo de revisión externa. No necesita una URI
  completa y **no abre conexiones SQL**.
- La validación escribe un resumen y la revisión en
  `outputs/persistencia_05/<id_de_carga>/`. No modifica los procesados ni los
  notebooks.

Conteos de referencia obtenidos con los archivos actuales:

| Entidad | Filas cargables |
|---|---:|
| Empresas / puntos de venta / asesores | 3 / 15 / 42 |
| Marcas / modelos / disponibilidades por sede | 5 / 24 / 179 |
| Leads / consultas | 1.451 / 1.500 |
| Conversaciones | 665 |
| Conversaciones utilizables / descartadas | 446 / 219 |
| Mensajes / extracciones / intereses de modelos | 4.231 / 665 / 752 |
| Prioridades / registros históricos | 1.451 / 2.200 |
| Modelos ML registrados | 3 |
| Trazas de filas de leads | 1.503 |
| Incidencias cargables | 13.142 |

Hay **12 conversaciones y 58 incidencias relacionadas fuera de la base**.
Esas 12 incluyen 9 utilizables en la extracción y 3 descartadas: la falta de
vínculo prevalece sobre el estado de calidad. La reconciliación es
`665 cargables + 12 externas = 677 originales`.

Las cuatro ejecuciones históricas importadas se registran sin inventar sus
horas de ejecución. Se añade una quinta ejecución para la carga SQL efectiva.
Los conteos no se usan como constantes para forzar futuras entradas.

## 4. Crear el esquema

Después de completar `SUPABASE_DB_URL`:

```powershell
.\.venv\Scripts\python.exe inicio-datos/docs/modelo_datos/05_crear_db.py
```

Resultado esperado: `estado: esquema_verificado`.

- Aplica `001_inicial.sql` en una transacción.
- Crea **20 tablas de dominio**, cuatro vistas y una tabla técnica
  `schema_migrations` con versión, hash y fecha de aplicación.
- Conserva datos; no usa `DROP` ni `TRUNCATE`.
- Si se vuelve a ejecutar, verifica la misma migración y no duplica tablas.
- Si una migración aplicada cambió, se detiene. Las evoluciones deben ir en una
  nueva migración, no editando una ya desplegada.
- Rechaza reutilizar un esquema con tablas preexistentes sin registro de
  migraciones. Evita trabajar en `public`, `auth`, `storage` o esquemas reservados.

Una migración y la carga comparten un bloqueo transaccional por esquema para
evitar que dos instancias de estos scripts hagan cambios incompatibles a la vez.

## 5. Cargar los datos

```powershell
.\.venv\Scripts\python.exe inicio-datos/docs/modelo_datos/05_cargar_db.py
```

Resultado esperado: `estado: cargado_y_verificado`.

La carga:

1. Comprueba hashes de normalización, extracción, clasificación y comparación
   de desbalance. Rechaza artefactos que ya no correspondan a sus manifiestos.
2. Separa las conversaciones sin vínculo y sus incidencias en
   `revision_fuera_db.json`. No crea clientes o empresas ficticios.
3. Crea maestros desde relaciones explícitas. No inventa nombres de empresas,
   ubicaciones o cantidades de inventario por sede.
4. Conserva la conversación descartada con su flag, motivos y contenido. La
   fecha de descarte queda nula porque no está documentada en las fuentes.
5. Guarda todos los intereses y los JSON de evidencia, y verifica las citas de
   los resultados contra mensaje, posición y emisor.
6. Mantiene los históricos sin gestión sin convertirlos en perdidos.
7. Registra el modelo original como generador de los scores actuales, y los dos
   modelos de la segunda iteración como elegido experimental/comparación.
   No reentrena, recalcula ni sustituye la procedencia de scores.
8. Inserta o actualiza por claves estables, sin cambiar la empresa propietaria.
9. Lee y compara todas las columnas de las filas cargadas y valida la vista de
   clasificación antes de confirmar el `COMMIT`.

Si falla una operación SQL, la transacción se revierte. El error se registra
fuera de esa transacción en un archivo local sanitizado, sin datos de filas ni
credenciales. El comando devuelve código distinto de cero; no continuar con
otros pasos del flujo como si hubiera terminado correctamente.

### Repetición y nuevas fuentes

Ejecutar otra vez la misma carga produce `ya_cargado_y_verificado`: comprueba
los registros y no duplica resultados. La identidad del lote incluye huellas de
fuentes, versión y código del cargador.

Las entidades operativas se actualizan por clave, y los resultados de métodos
distintos permanecen versionados. Si la nueva foto omite entidades operativas
que ya existen, el script se detiene: no las borra ni deja desaparecer clientes
silenciosamente. Una política de bajas futuras debe decidirse explícitamente.

No es un cargador de archivos parciales. La clasificación recibida debe cubrir
los leads del conjunto completo. La vista vigente escoge una sola clasificación
importada completada, en lugar de mezclar resultados de cargas parciales.

## 6. Esquema físico y diferencias respecto al diagrama conceptual

- Las claves internas son textos deterministas derivados de hashes, no enteros
  autoincrementales. Eso permite repetir archivos sin duplicar intereses,
  mensajes, extracciones, incidencias o versiones.
- Cada fecha de negocio tiene columnas `date`, `time` opcional y precisión. Una
  fecha sin hora tiene la columna de hora nula. No se inventan zonas horarias.
- Fechas de ejecución de este cargador usan `timestamptz` y UTC. Las ejecuciones
  históricas importadas tienen inicio/fin desconocidos, y un momento de registro
  técnico independiente.
- Las conversaciones incluyen el ID consolidado para comprobar en SQL la
  coherencia del contexto de prioridades mediante claves compuestas.
- Se conserva el registro de origen completo en JSONB, además de columnas
  consultables. Las menciones de motos se proyectan de la extracción en la misma
  transacción.
- `schema_migrations` es infraestructura técnica; no cambia las 20 tablas de
  dominio acordadas.

El SQL en `migrations/` es la definición física exacta; el Mermaid es la vista
conceptual y el diccionario explica la semántica de los campos.

## 7. Acceso y aislamiento

El esquema queda **privado**: se revocan permisos de `PUBLIC`, `anon` y
`authenticated` cuando esos roles existen; se activa RLS en las tablas sin crear
políticas permisivas. Las vistas son `security_invoker`.

El propietario/rol administrativo conserva capacidad para cargar y revisar los
datos. RLS sin políticas no concede acceso a usuarios normales, pero los roles
privilegiados pueden omitirla. No usar la credencial administrativa en el cliente.
[RLS en Supabase](https://supabase.com/docs/guides/database/postgres/row-level-security).

Este paso impide exponer accidentalmente los datos por defecto. **Todavía no
implementa usuarios, membresías o políticas que permitan a cada asesor leer su
empresa.** Esa autorización y sus pruebas se completarán con la API/tablero.
La integridad entre empresas sí se refuerza mediante claves foráneas compuestas.

## 8. Revisar en el SQL Editor de Supabase

Estas consultas suponen que se mantuvo el esquema `crm`. Ejecutarlas como
administrador después de ambos scripts:

```sql
SELECT 'leads' AS tabla, count(*) FROM crm.leads
UNION ALL SELECT 'consultas', count(*) FROM crm.consultas
UNION ALL SELECT 'conversaciones', count(*) FROM crm.conversaciones
UNION ALL SELECT 'mensajes', count(*) FROM crm.mensajes
UNION ALL SELECT 'historico_cierres', count(*) FROM crm.historico_cierres;

SELECT empresa_id, descartada, count(*)
FROM crm.conversaciones
GROUP BY empresa_id, descartada
ORDER BY empresa_id, descartada;

SELECT empresa_id, cola, count(*)
FROM crm.v_cola_priorizada
GROUP BY empresa_id, cola
ORDER BY empresa_id, cola;

SELECT etapa, estado, importada, inicio, fin
FROM crm.ejecuciones
ORDER BY registrada_en;
```

La lectura administrativa demuestra persistencia, no acceso autorizado por
empresa. Verificar ese aislamiento requiere los roles reales de la aplicación.

## 9. Pruebas locales

```powershell
.\.venv\Scripts\python.exe -m pip install -r inicio-datos/requirements-dev.txt
.\.venv\Scripts\python.exe -m ruff check inicio-datos/docs/modelo_datos inicio-datos/tests
.\.venv\Scripts\python.exe -m ruff format --check inicio-datos/docs/modelo_datos inicio-datos/tests
.\.venv\Scripts\python.exe -m unittest discover -s inicio-datos/tests -v
```

Las pruebas verifican sintaxis PostgreSQL con `pglast`, claves y contratos de
datos, desconocido frente a cero, precisión temporal, evidencia del emisor,
rechazo de cruces de empresa, revisión externa, flags y preparación repetible.

Las 13 pruebas locales pasaron, junto con las comprobaciones de estilo y formato.
Además, el 2026-09-17 se realizaron pruebas de integración en Supabase:

- Migración inicial aplicada y segunda ejecución sin migraciones pendientes.
- Carga completa conciliada por valores; repetición sin duplicados.
- Conteos remotos coincidentes con la tabla de referencia: 1.451 leads,
  1.500 consultas, 665 conversaciones y 1.451 prioridades vigentes.
- Claves foráneas rechazaron una consulta con empresa ajena y una prioridad
  cuyo contexto correspondía a otro lead de la misma empresa.
- Las 21 tablas tienen RLS habilitado; los roles reales `anon` y
  `authenticated` recibieron acceso denegado al intentar leer `crm.leads`.
- Una escritura de prueba se revirtió y los conteos finales no cambiaron.

Esta última prueba usa una transacción forzada a rollback; no deja registros de
prueba. El resultado detallado está en
`outputs/persistencia_05/verificacion_remota.json`. Los permisos actuales
deniegan el acceso general; aún no se ha implementado ni probado la autorización
de usuarios por empresa para la futura aplicación.

Se observaron fallos intermitentes de conexión durante las verificaciones;
las reconexiones posteriores funcionaron con la misma configuración.

## 10. Archivos de salida

- `outputs/persistencia_05/esquema.json`: resultado remoto del script de esquema.
- `outputs/persistencia_05/verificacion_remota.json`: conteos, integridad,
  permisos y rollback verificados en la instancia, con fecha UTC.
- `outputs/persistencia_05/<id>/resumen.json`: estado local o remoto de la carga,
  explícitamente diferenciado.
- `outputs/persistencia_05/<id>/revision_fuera_db.json`: conversaciones y eventos
  pendientes fuera de la base; contiene contenido de revisión y no se publica.
- `outputs/persistencia_05/ultimo_error.json`: último diagnóstico SQL sanitizado,
  si hubo un error. Es histórico; su existencia no demuestra que la última carga
  también haya fallado.

La carpeta de salidas de persistencia está excluida de Git. Los scripts, el
esquema, sus pruebas y la documentación sí son versionables.
