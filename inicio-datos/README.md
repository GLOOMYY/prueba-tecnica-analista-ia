# Desarrollo y evidencia de los puntos 1 a 5

Esta carpeta conserva el código y las explicaciones de los notebooks y los
scripts del punto 5. Para preparar Git se retiraron las salidas guardadas y los
contadores de ejecución: podían incluir filas, contactos y conversaciones.
Los originales con resultados están en `../local-private/notebooks-originales/`,
excluidos de Git. No se reejecutaron notebooks durante esta preparación.

- `notebooks/`: estudio, exploración y decisiones documentadas.
- `data/`: fuentes originales y resultados revisados.
- `outputs/`: evidencias, extracciones, métricas y modelos anteriores.
- `docs/modelo_datos/`: diagrama, diccionario y scripts SQL del punto 5.
- `tests/`: pruebas de la persistencia original.
- `requirements-*.txt`: dependencias de los trabajos anteriores.

`data/`, `outputs/` y el PDF original del enunciado son archivos locales
excluidos de Git. Un clon requiere recibir las fuentes por un canal privado
autorizado; no se publican como parte del código.

Las rutas `data/`, `outputs/`, `docs/` y `notebooks/` dentro de los documentos y
salidas históricas se interpretan respecto a **esta carpeta**. Para ejecutar un
notebook histórico, usar `inicio-datos` o `inicio-datos/notebooks` como directorio
de trabajo del kernel. Los notebooks no se han reejecutado durante la migración.

El `.env` permanece exclusivamente en la raíz del repositorio. Los scripts SQL
históricos se adaptaron para leerlo allí. Si se vuelve a ejecutar el notebook de
Gemini, su proceso debe recibir `API_KEY_GEMINI` en el entorno; la copia histórica
del notebook conserva su resolución original de `.env` para no cambiarlo.

Para ejecución operativa usar [el nuevo flujo](../auto-inicio-datos/README.md),
que no depende de esta carpeta. Las reglas futuras deben mantenerse en ese
flujo; esta carpeta conserva la evidencia de cómo se llegó a ellas.
