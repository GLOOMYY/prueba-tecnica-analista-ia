# Guion de ocho diapositivas — borrador para sustentación

1. **Problema**: tres comercializadoras y una cola útil por empresa; mismo
   cliente en empresas distintas mantiene identidades separadas.
2. **Fuentes y limpieza**: ingesta reproducible, formatos conservadores,
   trazabilidad, desconocidos e incidencias. Mostrar ejemplo sintético.
3. **IA con evidencia**: extracción fija de conversaciones, distinción cliente/
   asesor y descarte por inconsistencias. Mostrar salidas reales del notebook.
4. **Priorización**: reglas explicables; separar score operativo del modelo
   experimental. Explicar desbalance y por qué no se afirma superioridad del ML.
5. **Persistencia**: modelo propio en PostgreSQL, consultas frente a identidades,
   historia, claves de empresa y controles de acceso.
6. **Producto**: demostrar alta → score → gestión → tablero/API; capacidad real
   de asesor. Presentar como pendiente cualquier integración no comprobada.
7. **Automatización y despliegue**: runner y caché; mostrar ejecuciones reales.
   Render diferido; no afirmar que exista un horario alojado o URL pública.
8. **Pruebas y límites**: evidencia de idempotencia, rollback e identidad por
   empresa; distinguir SQLite de PostgreSQL y enumerar pendientes vigentes.

Este archivo es un guion, no una presentación final renderizada. Antes de la
entrega, reemplazar pendientes por evidencia únicamente cuando se verifiquen.
