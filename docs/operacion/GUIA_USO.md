# Recorrido comercial local

Requiere migraciones y usuarios/membresías aprovisionados. Para alta y catálogo
también requiere las tablas históricas SQL; SQLite de desarrollo vacío no las
crea. Las pruebas aíslan sus propios datos sintéticos.

1. Entrar a `/accounts/login/` y seleccionar una empresa autorizada.
2. En «Añadir lead», declarar nombre, contacto, sede y únicamente señales
   conocidas. Identificar SKU solo cuando exista correspondencia verificable.
3. Guardar: se muestran score, razón y acción sugerida en el detalle. Si la
   identidad es ambigua, la captura permanece en revisión.
4. Registrar gestión. Pérdida/descarte necesitan motivo; cierre requiere
   confirmación; seguimiento necesita fecha futura en Bogotá.
5. Consultar «Mis leads de hoy». Crear un lead no equivale a asignarlo:
   la asignación exige capacidad y asesor elegible de su sede.

## API

Autenticación: sesión con CSRF o `Authorization: Token <token>` emitido mediante
un procedimiento administrativo privado. Nunca guardar tokens en ejemplos reales.
Las rutas comerciales requieren `X-Empresa-ID` con membresía activa.
Alta y gestión requieren `Idempotency-Key`, conservada en cada reintento.

Ejemplo sintético de cuerpo para `POST /api/v1/leads/`:

```json
{
  "nombre_cliente": "Ana Perez",
  "telefono": "3001234567",
  "sede_id": "SEDE-DE-LA-EMPRESA",
  "cuota_inicial": "1000000.00",
  "moneda": "COP",
  "cliente_pidio_cita": true
}
```

Consultar `/api/schema/` autenticado para el contrato básico y `/api/docs/`
para leerlo mediante la interfaz navegable DRF. El score prioriza atención;
no representa probabilidad de compra.
