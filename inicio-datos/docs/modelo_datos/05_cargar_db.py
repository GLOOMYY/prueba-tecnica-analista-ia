"""Valida y carga los procesados en una transacción PostgreSQL.

Ejecutar desde la raíz: python docs/modelo_datos/05_cargar_db.py
Usar --validar para preparar y revisar el lote sin conectar.
"""

from persistencia.cli import cargar_main

if __name__ == "__main__":
    raise SystemExit(cargar_main())
