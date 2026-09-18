# Recuperación y pruebas de respaldo

## Prueba ejecutada

El verificador de concurrencia crea un esquema `carrera_<uuid>` con datos
sintéticos, aplica SQL/Django y prueba sesiones independientes. Si se configura
`POSTGRES_BIN`, también ejecuta `pg_dump` y `pg_restore`:

1. Guarda un dump privado, sin propietarios ni concesiones de permisos.
2. Renombra únicamente el esquema sintético a `<nombre>_original`.
3. Restaura sobre el nombre ahora libre, en la misma base de prueba.
4. Compara cantidad y huella del contenido de cada tabla, incluidos JSON/nulos.
5. Elimina ambos esquemas temporales y su rol al terminar.

Resultado verificado: **42 tablas con contenido idéntico**. No se restauró el
esquema comercial. El dump queda en `local-private/`, excluido de Git.
El helper rechaza nombres que no correspondan al formato aleatorio de prueba.

## Repetir la comprobación

Instalar herramientas PostgreSQL compatibles con la versión del servidor.
En esta ejecución se usaron los binarios portables 17.11, sin instalar servicio.
La [página oficial de PostgreSQL para Windows](https://www.postgresql.org/download/windows/)
enlaza las distribuciones de binarios de EDB.

```powershell
$env:POSTGRES_BIN = 'C:\ruta\postgresql\bin'
.\.venv\Scripts\python.exe tests/verificar_concurrencia_postgresql.py
Remove-Item Env:POSTGRES_BIN
```

En Linux usar la carpeta que contiene `pg_dump` y `pg_restore` sin extensión.
Se requiere `SUPABASE_DB_URL` administrativa. Las credenciales se pasan por el
entorno del subproceso, nunca como argumentos ni como salida de consola.
Sin `POSTGRES_BIN` se prueban las carreras, pero se omite el respaldo.

## Procedimiento ante una recuperación real

1. Detener temporalmente lote, worker y escrituras web.
2. Crear un respaldo del estado actual antes de cualquier sustitución.
3. Restaurar primero en una base/esquema de recuperación separado.
4. Verificar migraciones, conteos, relaciones, trabajos y prioridad publicada.
5. Reaplicar `plataforma/crm/sql/roles_postgresql.sql` y verificar RLS con el rol
   web: el dump de prueba excluye ACL y no acredita su restauración automática.
6. Validar login, detalle y aislamiento; cambiar la conexión al destino aprobado.
7. Reanudar procesos y revisar trabajos pendientes/idempotencia.

Este procedimiento no autoriza a sobrescribir producción automáticamente.
La conservación, cifrado y periodicidad de los backups alojados se configuran
con el proveedor durante la fase de despliegue. La prueba local demuestra
recuperabilidad del esquema de aplicación, no una política de backups activa.
