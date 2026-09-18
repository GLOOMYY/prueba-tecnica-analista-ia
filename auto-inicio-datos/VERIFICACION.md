# Verificación de la reorganización y el punto 6

Fecha: 2026-09-17. Datos sintéticos entregados para la prueba técnica.

## Evidencia comprobada

- Los tres notebooks conservan exactamente sus bytes, incluidas sus salidas.
- Los CSV de leads, consultas, asesores, catálogo, histórico y trazabilidad
  coinciden byte a byte con los procesados conservados en `inicio-datos`.
- Los JSON de conversaciones, extracciones utilizables, descartadas y
  conversaciones utilizables conservan el mismo contenido.
- La empresa, identidad, score operativo, temperatura, cola, explicación y
  score experimental coinciden con los resultados revisados anteriormente.
- La migración inicial mantiene exactamente su contenido SQL original.
- La bitácora de Gemini no aumentó: **cero peticiones nuevas** durante las pruebas.
- Ruff y formato pasaron. Pasaron 13 pruebas del nuevo flujo y las 13 pruebas
  de persistencia conservadas en `inicio-datos/tests`.

## Ejecución real hasta Supabase

Se ejecutó `run.py --sin-api` y terminó en `completada`, incluyendo lectura,
normalización, extracción desde caché, priorización y carga SQL conciliada.

Huella de esa ejecución:
`97376d75ad32` (prefijo del directorio de ejecución).

El resumen de carga está en `outputs/persistencia_05/resumen.json` dentro de
esa ejecución, con estado `cargado_y_verificado`.

| Entidad del lote | Cantidad |
|---|---:|
| Leads | 1.451 |
| Consultas | 1.500 |
| Conversaciones | 665 |
| Conversaciones utilizables / descartadas | 446 / 219 |
| Mensajes | 4.231 |
| Prioridades | 1.451 |
| Históricos | 2.200 |
| Marcas / modelos de moto | 5 / 24 |
| Conversaciones en revisión externa | 12 |

Los resultados versionados del nuevo lote se añaden a la historia existente;
estos conteos no representan el total histórico acumulado de todas las tablas.
Se registra un modelo del flujo automático, manteniendo los anteriores.

## Repetición y fallos

La repetición real reutilizó correctamente los checkpoints 01–04. El paso 05
falló por conexión (`OperationalError`) después de sus reintentos; se registró
como fallido y no publicó una confirmación nueva de éxito.

El intento siguiente no llegó a ejecutarse: la revisión automática de permisos
informó falta de créditos del espacio de trabajo. **Queda pendiente completar
la segunda verificación remota del nuevo runner.** La idempotencia del cargador
original ya se había verificado en el punto 5, pero no se presenta eso como una
segunda ejecución remota exitosa de este runner.

Después de esta prueba se añadió conservación de manifiestos por intento para
que una repetición no sobrescriba la evidencia del intento anterior. Este ajuste
de orquestación se valida localmente; las reglas y el cargador SQL no cambiaron.
La versión final (`53eabf51358e`, prefijo) completó la validación local y se
repitió reutilizando 01–04 y validando 05. También funcionó al invocarla desde
otro directorio. Sus manifiestos por intento permanecen separados.

## Activación permanente

El modo `--watch` y su disparo ante cambios estables están implementados y
probados localmente. El comando único también puede invocarse desde un
programador de tareas. No se dejó un proceso indefinido ejecutándose ni se
instaló un servicio/horario en el equipo.

Por tanto: **flujo automático implementado y recorrido hasta la base real**;
la operación permanente requiere activar `--watch` o registrar el comando en
la plataforma/horario que se elija.
