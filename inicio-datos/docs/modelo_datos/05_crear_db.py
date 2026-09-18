"""Crea o migra el esquema propio en PostgreSQL, sin borrar datos.

Ejecutar desde la raíz: python docs/modelo_datos/05_crear_db.py
Usar --validar para revisar archivos/configuración sin conectar.
"""

from persistencia.cli import crear_main

if __name__ == "__main__":
    raise SystemExit(crear_main())
