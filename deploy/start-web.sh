#!/bin/sh
set -eu
# HSTS de subdominios y preload requieren decidir el dominio definitivo.
# Las advertencias siguen visibles; los errores impiden iniciar el servicio.
python plataforma/manage.py check --deploy --fail-level ERROR
python plataforma/manage.py collectstatic --noinput --verbosity 0
exec gunicorn --chdir plataforma --bind "0.0.0.0:${PORT:-8000}" --workers 2 --timeout 120 plataforma.wsgi:application
