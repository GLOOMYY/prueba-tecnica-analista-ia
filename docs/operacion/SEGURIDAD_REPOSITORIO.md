# Revisión previa al primer historial Git

## Alcance

Se revisaron archivos candidatos a Git antes de crear el primer commit. La rama
no tenía commits previos: no existía historial que limpiar. No se publicó ni
envió el repositorio a un servicio remoto durante esta revisión.

## Medidas aplicadas

- `.env` y sus variantes están excluidos; `.env.example` conserva variables
  vacías y configuración no secreta.
- Se excluyen fuentes, procesados, respuestas de IA, cachés, modelos generados,
  informes de ejecución, PDF original, bases SQLite, logs y respaldos privados.
- Los notebooks versionados conservan código y explicaciones, sin salidas ni
  contadores de ejecución. Sus originales se guardan en
  `local-private/notebooks-originales/`, fuera de Git.
- Se comparó el contenido candidato con los secretos configurados localmente
  y se buscaron patrones de claves, tokens, claves privadas y URI con contraseña.
  El informe de búsqueda muestra solo rutas y categorías, nunca secretos.
- La URI detectada en `plataforma/crm/tests.py` es una fixture sintética sobre
  `db.example.com`; no contiene credenciales operativas.
- Se revisaron referencias a correos y teléfonos en fuentes y notebooks.
  Las pruebas usan ejemplos sintéticos; las salidas de datos se excluyeron.

Esta revisión reduce riesgos, pero no garantiza que cualquier modificación
futura esté libre de secretos. `.gitignore` no protege archivos ya rastreados
ni evita que alguien use `git add -f`.

## Antes de cada publicación

1. Revisar `git status --short` y `git diff --cached --stat`.
2. Revisar el diff preparado sin copiar credenciales a comentarios o informes.
3. Confirmar que no se agregaron salidas ejecutadas de notebooks ni fuentes.
4. Mantener secretos en entorno o gestor del proveedor y roles mínimos de DB.
5. Si una credencial se expuso en Git o en un canal compartido, rotarla;
   borrar un archivo no invalida la credencial ni elimina el historial previo.

Los datos del ejercicio se entregan por un canal autorizado separado. El README
explica cómo restaurarlos localmente y qué puede probarse sin ellos.

## Historial honesto

La serie inicial registra la incorporación actual del proyecto por componentes,
con Conventional Commits y la identidad Git ya configurada. No se alteran fechas,
autores ni resultados para fingir un desarrollo pasado. El requisito de acceso
en GitHub/GitLab seguirá pendiente hasta publicar y habilitar al evaluador.
