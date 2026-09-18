# Estado verificado de la plataforma

Actualizado el 2026-09-18. Los cambios se registran mediante Conventional
Commits locales; no se ha hecho push en esta intervención.

## Cierre del alcance 1–6

| Fase | Resultado |
|---|---|
| C1: PostgreSQL y permisos | Bootstrap aplicado en Supabase, SQL 001–007 y Django 0001–0004. Rol web LOGIN restringido, separado del administrador. |
| C2: lote y web | Identidades conciliadas por empresa y fuentes estables; consultas aceptadas inmutables; prioridades distintas pasan a revisión. Recarga completa verificada. |
| C3: IA individual | Contrato completo compartido con lote, validación de evidencias, caché durable, cuota global y publicación atómica por revisión. |
| C4: revisión y cartera | Resolución supervisada de identidad y prioridad; transferencias con capacidad, auditoría e idempotencia. |
| C5: producto y API | Tablero, cola, alta, gestión, filtros, paginación, SLA y respuestas OpenAPI. Revisión visual básica en escritorio y móvil. |
| C6: aceptación | Pruebas locales, PostgreSQL real, recarga mixta, concurrencia, recuperación, entorno limpio y revisión de secretos. Véase la matriz de aceptación. |

## PostgreSQL operativo

`06_inicializar_plataforma.py --aplicar` dejó 1451 estados operativos:
473, 497 y 481 por empresa. Creó tres usuarios supervisores, cada uno con una
sola empresa. Una repetición creó cero usuarios y conservó las contraseñas.
Los accesos se guardan únicamente en `local-private/usuarios.md`, ignorado por Git.
La aplicación utiliza `DJANGO_DATABASE_URL` de mínimo privilegio; la conexión
administrativa se utiliza para migraciones y carga.

**SQLite solo se utiliza en pruebas unitarias y en la maqueta visual aislada.**
No sustituye PostgreSQL ni acredita restricciones SQL, RLS o concurrencia.

## Evidencia ejecutada

- Pruebas locales de dominio, pipeline y Django: ver conteo final en
  [aceptación](ACEPTACION.md) y ejecutar `tests/ejecutar_pruebas_locales.py`.
- PostgreSQL aislado: migraciones SQL/Django, rol restringido, alta y reintento,
  publicación IA con historia y score, conflicto de lote, SLA y contextos
  A → B → A. Escrituras cruzadas y consultas sin ámbito rechazadas.
- Recarga completa de 1451 leads: lote → alta web y gestión → repetir lote →
  nueva fuente coincidente con alta web → repetir instantánea antigua aceptada.
  Se preservaron identidad canónica, prioridad web y gestión.
- Sesiones simultáneas PostgreSQL: alta de la misma identidad con claves
  distintas, dos reclamadores y dos asignadores. Mismo teléfono en tres
  empresas produce identidades distintas. HTTP rechaza ámbitos ajenos,
  operador, membresía revocada y objetos fuera de la cartera.
- Backup/restauración de esquema sintético con PostgreSQL 17: comparación de
  conteos y huellas de las 42 tablas. El esquema comercial no fue restaurado
  ni eliminado. Las concesiones de roles se reaplican por separado.
- Gemini: una petición sintética adicional validó el contrato completo
  compartido. Las dos peticiones anteriores correspondían al contrato inicial;
  no se presentan como evaluación del contrato nuevo. No se reextrajo el histórico.
- `run.py --sin-api --sin-db`: etapas 1–5 completadas usando caché válida.
  Este comando no demuestra por sí solo persistencia; la recarga PostgreSQL sí.
- Tres cuentas iniciales autenticadas: solo su empresa, listado y tablero.
  Página de 25 leads: 10 consultas y aproximadamente 0,66–0,67 segundos por
  empresa en esta ejecución. Es una medición puntual, no una prueba de carga.
- Entorno virtual nuevo: instalación de `requirements-web.txt`, `pip check`
  y `manage.py check` correctos.
- Navegador con fixtures: acceso, selección de empresa, tablero, formulario
  y cola vacía; vistas de 1280×800 y 390×844. Otros estados se cubren mediante
  pruebas HTTP; no se afirma una auditoría completa de accesibilidad.

## Decisiones que explican el comportamiento

1. Un teléfono nunca identifica globalmente a una persona entre empresas.
2. Un lote no gana vigencia por llegar más tarde. Una prioridad diferente se
   propone al supervisor, que conserva o adopta con motivo y auditoría.
3. Una consulta aceptada no se sobrescribe con otro contenido. Se detiene la
   carga y se genera `outputs/persistencia_05/revision_carga.json` con el motivo.
4. Un resultado IA tardío no reemplaza una captura nueva. La respuesta recibida
   se guarda antes de publicar para evitar otra llamada si falla la escritura.
5. Cuota global por modelo: 8 intentos/minuto y 240 en 24 horas móviles. La
   reserva SQL es compartida por lote y worker; si falla, no se llama al proveedor.
6. Modelos mencionados se conservan todos. Desconocido no significa cero ni no.
7. La prioridad operativa usa reglas explicables. El modelo entrenado continúa
   como experimento; estas verificaciones no demuestran una mejora predictiva.

## Pendiente fuera de este cierre

- **7: Render:** construir y arrancar la imagen en el proveedor, configurar
  secretos, worker/programación y almacenamiento durable de fuentes/caché,
  comprobar URL, HTTPS y recorrido alojado. No hay URL verificada aquí.
- **8: entrega:** presentación, demostración y acceso final del evaluador.

No se verificó Docker en un daemon local ni rendimiento bajo concurrencia de
muchos usuarios. La prueba Gemini sintética no equivale a una evaluación
semántica exhaustiva. Esos límites no se ocultan como resultados positivos.
