# Aceptación: cierre C1–C6

Evidencia al 2026-09-18. Consultar [estado y límites](ESTADO_REAL.md).
Las pruebas automáticas usan fixtures sintéticas; las recargas usan los
artefactos privados de la prueba técnica en un esquema aislado.

## Matriz del contrato

| Caso | Evidencia reproducible | Resultado |
|---|---|---|
| AC01: teléfono igual, empresas diferentes | `tests/verificar_concurrencia_postgresql.py`: tres empresas | Identidades separadas |
| AC02: mismo cliente, nuevo canal | `plataforma/crm/test_alta_sql.py`; `tests/verificar_recarga_postgresql.py` | Consulta nueva, identidad preservada |
| AC03: altas simultáneas | `tests/verificar_concurrencia_postgresql.py`: dos sesiones y claves distintas | Un único lead |
| AC04: reintento y cuerpo cambiado | `plataforma/crm/test_alta_sql.py`, `test_recorrido.py` | Repetición estable; cambio devuelve 409 |
| AC05: teléfono compartido incompatible | `tests/test_identidades_lote.py`; pruebas de alta | Revisión, sin fusión automática |
| AC06: inicial cero, nula y positiva | Dominio y pruebas de reglas del pipeline | Estados distintos; solo positiva aporta |
| AC07: cita como única señal | `tests/test_dominio_prioridad.py`; integración PostgreSQL | 44,44 y caliente |
| AC08: oferta no es petición de crédito | Contrato compartido y pruebas de extracción individual | Se exige evidencia del cliente |
| AC09: error o cuota IA | `plataforma/crm/test_cierre.py`; cuota en concurrencia PostgreSQL | Alta preservada, error durable, novena reserva rechazada |
| AC10: respuesta IA tardía | `plataforma/crm/test_cierre.py` | No publica sobre revisión nueva |
| AC11: alta, gestión y recargas | `tests/verificar_recarga_postgresql.py` | Identidad, gestión y vigente conservadas |
| AC12: objetos y agregados ajenos | Integración PostgreSQL, concurrencia y `test_recorrido.py` | RLS, HTTP y cartera impiden acceso |
| AC13: asignadores simultáneos | `tests/verificar_concurrencia_postgresql.py` | Una asignación sin exceder cupo |
| AC14: backlog antiguo | Concurrencia PostgreSQL: fuente de 2020 y asignación actual | Original intacto y fecha operativa de hoy |
| AC15: fecha sin hora | `tests/test_sla.py` y métrica PostgreSQL | No medible; no se inventa hora |
| AC16: descartada vinculada o huérfana | Pruebas de preservación del pipeline; validación de carga completa | Vinculada conservada; huérfana fuera de DB comercial |
| AC17: caída/reclamación/caché | `plataforma/crm/tests.py`, `test_cierre.py`; sesiones PostgreSQL | Lease y reintentos acotados; respuesta reutilizada |
| AC18: alta sobre cartera ajena | Pruebas de dominio/alta y recorrido | Revisión sin revelar datos |
| AC19: cambio de contexto | Integración A → B → A y matriz HTTP de tres empresas | Se restaura contexto; nueva autorización |
| AC20: intento y contacto | `test_recorrido.py::test_intento_y_contacto_son_eventos_distintos` | Dos eventos; un lead gestionado, un intento y un contacto |

## Comprobaciones complementarias

- [x] 81 pruebas locales: 46 Django, 21 dominio y 14 pipeline.
- [x] Migraciones SQL 001–007 y Django 0001–0004 en PostgreSQL.
- [x] Bootstrap permanente y login de tres supervisores aislados por empresa.
- [x] Conflicto de prioridad: decisión supervisada, auditoría y repetición segura.
- [x] Transferencia y gestión simultáneas preservan actividad y cartera.
- [x] Backup/restauración: conteos y huellas iguales en 42 tablas sintéticas.
- [x] Contrato OpenAPI contrastado con respuestas reales de detalle, lista y tablero.
- [x] Pipeline completo con caché; recarga completa en PostgreSQL aislado.
- [x] Contrato completo validado con una llamada Gemini sintética adicional.
- [x] Entorno virtual nuevo: dependencias web, `pip check` y `manage.py check`.
- [x] Medición puntual: página de 25 leads, 10 consultas, 0,66–0,67 s.
- [x] Revisión visual básica de escritorio/móvil con fixtures y pruebas HTTP.
- [x] Ruff y revisión de secretos antes de los commits.
- [ ] Validación de URL, imagen y procesos alojados en Render (fase 7).
- [ ] Presentación y recorrido final con el evaluador (fase 8).

## Reproducibilidad y límites

Comandos en [README](../../README.md). `tests/ejecutar_pruebas_locales.py`
separa las pruebas unitarias de las conexiones comerciales. Los verificadores
PostgreSQL crean y eliminan sus propios esquemas o revierten su transacción;
no restauran sobre `crm`. Para backup ver [recuperación](RECUPERACION.md).

La medición puntual no acredita capacidad bajo carga masiva. Las pruebas de
concurrencia cubren carreras concretas, no todas las intercalaciones posibles.
Una llamada Gemini no acredita exactitud universal. La inspección visual básica
no constituye una auditoría de accesibilidad ni la validación del sitio alojado.
