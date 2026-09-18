# Plataforma Django y API

## Estructura

```text
plataforma/
├── manage.py
├── plataforma/       Configuración, URLs y entradas WSGI/ASGI
├── cuentas/          Usuarios y pertenencia a empresas
└── crm/              Páginas, API y servicios del CRM
```

El paquete de configuración se llama `plataforma`; se conserva el nombre
elegido al crear el proyecto. Cada aplicación tiene su carpeta `migrations/`.

## Configuración aplicada

- Django REST Framework y las aplicaciones `cuentas` y `crm` registradas.
- Idioma español, zona `America/Bogota` y soporte de zonas horarias habilitado.
- API con autenticación por sesión y token, permiso `IsAuthenticated` y ámbito explícito
  validado por membresía para rutas comerciales.
- Clave de Django, modo debug y hosts permitidos leídos desde el `.env` de la
  raíz. Las variables del proceso prevalecen sobre ese archivo.
- Dependencias fijadas en `requirements-web.txt` en la raíz del repositorio.

## Comprobación

Desde la raíz del repositorio:

```powershell
.\.venv\Scripts\python.exe plataforma/manage.py check
```

SQLite permanece disponible para desarrollo y pruebas. PostgreSQL web se activa
solo con `DJANGO_DATABASE_URL`, separada de la credencial administrativa de carga.
Las migraciones locales y RLS están preparadas; su aplicación remota aún debe
verificarse con roles reales.

Hay API, tablero básico, cola propia y gestión comercial sobre tablas operativas.
El alta transaccional, su score y los reintentos se probaron localmente con tablas
SQL de contrato mínimo. Falta validar su integración con PostgreSQL y los roles
reales; SQLite no demuestra RLS ni concurrencia.
Consultar [estado y pendientes](../docs/operacion/ESTADO_REAL.md) y
[guía de uso](../docs/operacion/GUIA_USO.md).
Consultar [`docs/operacion/DESPLIEGUE.md`](../docs/operacion/DESPLIEGUE.md) para
la imagen Docker, procesos y checklist de release.
