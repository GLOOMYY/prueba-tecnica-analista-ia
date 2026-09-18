# Despliegue y operación

## Diagnóstico: Render no encuentra Dockerfile

El log compartido corresponde al commit `076dbb7`. Se verificó en Git que ese
commit contiene `Dockerfile` en la raíz. El fallo ocurre antes de instalar
dependencias o iniciar Django. La causa probable es la ruta configurada en el
servicio; todavía no se inspeccionaron sus ajustes en Render.

En Settings → Build & Deploy comprobar:

- Root Directory: vacío, para utilizar la raíz del repositorio.
- Dockerfile Path: `./Dockerfile`.
- Docker Build Context Directory: `.` si aparece ese campo.
- Branch: `main`; Runtime/Language: Docker.
- Docker Command: vacío para usar el `CMD` del archivo.

La raíz no debe ser `plataforma`: el Dockerfile también copia `dominio`,
`deploy` y los requirements desde la raíz. Guardar y repetir el despliegue.
Un servicio creado manualmente no debe asumirse sincronizado con `render.yaml`.

Referencia: [rutas relativas a Root Directory en Render](https://render.com/docs/monorepo-support).
Este diagnóstico no demuestra que la compilación o la aplicación ya funcionen;
primero debe superarse la localización del Dockerfile.

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

## Render: despliegue iniciado por el usuario

Render es el proveedor elegido. El usuario conectó el repositorio e inició una
compilación, que falló al localizar el Dockerfile según el log compartido.
No se ha verificado una URL funcional. `render.yaml` prepara el servicio web
Docker y los secretos se configuran fuera del repositorio. La imagen contiene
web y dominio; todavía no empaqueta el lote ni un worker operativo.

No se construyó la imagen: Docker no tenía un daemon disponible. Tampoco se
verificó PostgreSQL remoto: el DNS del host configurado no resolvió. Antes de
publicar deben cerrarse los pendientes de [ESTADO_REAL.md](ESTADO_REAL.md).

El lote alojado necesitará fuentes y caché durables. No usar el filesystem del
contenedor web como almacenamiento final. El horario alojado se configurará
cuando se retome el despliegue, después de verificar la integración.
