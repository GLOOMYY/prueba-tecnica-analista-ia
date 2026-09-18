# Despliegue y operación

## Procesos

| Proceso | Comando | Propósito |
|---|---|---|
| Web | `sh deploy/start-web.sh` | Comprueba configuración, recolecta estáticos e inicia Gunicorn. |
| Lote | `python run.py` | Ingesta completa programada. |
| Worker | `python plataforma/manage.py procesar_trabajos --tipo extraer_ia` | Deshabilitado: termina con error sin reclamar trabajos hasta integrar Gemini individual. |

## Variables

Copiar `.env.example` al gestor de secretos del proveedor. Configurar
`DJANGO_ENV=production`, `DJANGO_DEBUG=False`, `DJANGO_SECRET_KEY` (al menos
50 caracteres aleatorios), `DJANGO_ALLOWED_HOSTS`, `DJANGO_DATABASE_URL` con rol web
mínimo y `DJANGO_SECURE_SSL_REDIRECT=True`. No utilizar la URL administrativa
del cargador como credencial web.

## Release seguro

1. Construir la imagen con `docker build -t prueba-ia .`.
2. Ejecutar `python plataforma/manage.py check --deploy` con las variables de
   producción.
   El arranque se detiene ante errores. Las advertencias siguen visibles:
   W005/W021 quedan pendientes hasta decidir HSTS para subdominios y precarga
   del dominio definitivo; no activar esas políticas sin revisar su alcance.
3. Aplicar las migraciones Django y `002_vigencia_por_lead.sql` usando el rol
   administrativo, en una ventana controlada.
4. Configurar `/healthz/` como liveness y `/readyz/` como readiness.
5. Verificar autenticación, aislamiento de empresas y una carga idempotente en
   un entorno aislado antes de apuntar al entorno de evaluación.

## Render: publicación diferida

Render es el proveedor elegido. El usuario pospuso conectar el repositorio y
publicar; no hay URL ni servicio creado. `render.yaml` prepara el servicio web
Docker y los secretos se configuran fuera del repositorio. La imagen contiene
web y dominio; todavía no empaqueta el lote ni un worker operativo.

No se construyó la imagen: Docker no tenía un daemon disponible. Tampoco se
verificó PostgreSQL remoto: el DNS del host configurado no resolvió. Antes de
publicar deben cerrarse los pendientes de [ESTADO_REAL.md](ESTADO_REAL.md).

El lote alojado necesitará fuentes y caché durables. No usar el filesystem del
contenedor web como almacenamiento final. El horario alojado se configurará
cuando se retome el despliegue, después de verificar la integración.
