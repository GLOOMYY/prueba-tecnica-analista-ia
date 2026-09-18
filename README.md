# Prueba técnica — Analista de IA

## Organización

```text
inicio-datos/          Notebooks y trabajo preservado de los puntos 1–5
auto-inicio-datos/     Flujo operativo en Python y funciones en utils/
run.py                Entrada única del flujo automático
.env                  Credenciales locales, excluidas de Git
requirements.txt      Dependencias del flujo automático
```

- [Desarrollo y notebooks](inicio-datos/README.md).
- [Automatización, decisiones y comandos](auto-inicio-datos/README.md).
- [Modelo de datos y diagrama](inicio-datos/docs/modelo_datos/README.md).
- [Verificación del flujo](auto-inicio-datos/VERIFICACION.md).
- [Plan de plataforma, API y trabajo entre agentes](docs/plan-plataforma/README.md).
- [Plataforma Django](plataforma/README.md).
- [Estado verificado y pendientes](docs/operacion/ESTADO_REAL.md).
- [Guía de uso](docs/operacion/GUIA_USO.md).

## Ejecutar

Python 3.11, desde la raíz del repositorio:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# Solo al configurar un clon nuevo; no sobrescribir un .env existente:
Copy-Item .env.example .env
# Completar las variables privadas antes de ejecutar:
.\.venv\Scripts\python.exe run.py
```

Configurar el `.env` según `.env.example`. El comando ingiere, normaliza,
extrae con IA, prioriza y persiste en Supabase. Las entradas operativas están
en `auto-inicio-datos/data/raw`; también acepta `--fuentes <carpeta>`.

**Fuentes privadas:** los datos, salidas, cachés y PDF del enunciado no se
versionan. Obtener por un canal autorizado `asesores.csv`, `catalogo_motos.csv`,
`conversaciones.json`, `historico_cierres.csv` y `leads.csv`; colocarlos en esa
carpeta o indicar `--fuentes`. No se necesita editar su contenido.
`--sin-api` requiere además una caché válida obtenida de una ejecución previa;
un clon sin caché necesita permitir la extracción y configurar Gemini.

```powershell
# Ejecución continua disparada por cambios en los archivos:
.\.venv\Scripts\python.exe run.py --watch --intervalo 60

# Validación local con caché, sin peticiones nuevas ni conexiones SQL:
.\.venv\Scripts\python.exe run.py --sin-api --sin-db
```

`--watch` requiere mantener el proceso activo. No se ha instalado un servicio ni
registrado un horario en el sistema. El mismo `run.py` puede ser invocado por un
programador de tareas o una plataforma de despliegue.

Los datos son sintéticos. La prioridad operativa sigue reglas explicables y el
modelo tabular sigue siendo experimental. La plataforma incluye autenticación,
autorización por empresa/cartera, tablero, cola diaria, API y alta con score.
La integración y el aislamiento se comprobaron en PostgreSQL real.
Render es el proveedor elegido; su despliegue aún debe validarse.

## Plataforma y comprobaciones locales

Desde la raíz, después de crear el entorno:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-web.txt -r requirements-dev.txt
.\.venv\Scripts\python.exe 06_inicializar_plataforma.py --aplicar
.\.venv\Scripts\python.exe plataforma/manage.py runserver
```

Completar `DJANGO_SECRET_KEY` con un secreto aleatorio privado y usar
`DJANGO_ENV=development` solo localmente. **La plataforma usa PostgreSQL de
Supabase.** Después de cargar el histórico con `run.py`, el inicializador aplica
SQL y Django, configura un rol web restringido, sincroniza el histórico y crea
los tres usuarios iniciales. No ejecutarlo con una base ajena al proyecto.
Las credenciales quedan en `local-private/usuarios.md`, excluido de Git;
ver [usuarios iniciales](docs/operacion/USUARIOS_INICIALES.md).
Repetir la inicialización no cambia contraseñas ni duplica cuentas.

En Linux/macOS, usar `.venv/bin/python` y `cp .env.example .env` en lugar de
las rutas y el comando equivalentes de PowerShell.

Pruebas con datos sintéticos, sin consumir Gemini ni cargar Supabase:

```powershell
.\.venv\Scripts\python.exe tests/ejecutar_pruebas_locales.py
.\.venv\Scripts\python.exe tests/verificar_secretos.py
.\.venv\Scripts\python.exe -m ruff check .
```

## Repositorio y evaluación

Los commits usan Conventional Commits y fechas reales. La primera serie
incorpora trabajo que ya existía, separado por componentes; no reconstruye
artificialmente fechas ni iteraciones pasadas. Los avances siguientes se
registrarán cuando ocurran.

El repositorio ya fue conectado a Render según el log de despliegue del usuario.
Los últimos commits siguen locales hasta hacer push; comprobar el acceso del
evaluador antes de entregar. Consultar la
[revisión de seguridad](docs/operacion/SEGURIDAD_REPOSITORIO.md).

## Validación PostgreSQL y recuperación

Las pruebas SQL usan esquemas aleatorios aislados en el destino configurado y
eliminan únicamente sus propias fixtures. Requieren la conexión administrativa.
No consumen Gemini. Revisar su alcance antes de ejecutarlas:

```powershell
.\.venv\Scripts\python.exe tests/verificar_integracion_postgresql.py
.\.venv\Scripts\python.exe tests/verificar_concurrencia_postgresql.py
.\.venv\Scripts\python.exe tests/verificar_recarga_postgresql.py --trabajo <carpeta-de-ejecucion-validada>
.\.venv\Scripts\python.exe tests/verificar_usuarios_iniciales.py
```

La recarga requiere las salidas completas privadas del pipeline. La prueba de
usuarios lee el documento privado y no imprime contraseñas. Las pruebas locales
usan SQLite temporal únicamente para reglas y HTTP; las pruebas anteriores
verifican PostgreSQL. Consultar [aceptación](docs/operacion/ACEPTACION.md),
[recuperación](docs/operacion/RECUPERACION.md) y
[despliegue](docs/operacion/DESPLIEGUE.md).
