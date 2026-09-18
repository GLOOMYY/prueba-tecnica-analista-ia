# Recorrido comercial local

Requiere PostgreSQL y el bootstrap `06_inicializar_plataforma.py --aplicar`
posterior a la carga histórica. Los tres accesos de evaluación están en
`local-private/usuarios.md`, excluido de Git. Cada cuenta es supervisora de
una sola empresa. Las pruebas aíslan sus propios datos sintéticos.

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

## Revisión supervisada

Desde el tablero, abrir las capturas pendientes para vincular una identidad,
crear una distinta o rechazar con motivo. Una coincidencia en otra empresa nunca
permite fusionar leads. Los conflictos de prioridad del lote tienen su propia
pantalla: comparar vigente y propuesta y conservar o adoptar con una nota.
Repetir la misma decisión no duplica la auditoría.

La transferencia exige asesor activo, sede compatible y cupo disponible.
Una tarea ya atendida conserva a quien la atendió aunque cambie la cartera.
Los supervisores iniciales no son asesores: para poblar «Mis leads de hoy» se
necesitan usuarios con membresía de asesor vinculada al catálogo de asesores.

## Indicadores

- Activos: leads abiertos de la cartera visible.
- Asignados hoy: asignaciones de esa cartera en la fecha de Bogotá.
- Gestionados hoy: leads distintos con alguna gestión hoy.
- Intentos/contactos: eventos sin respuesta/contactado de hoy, respectivamente.
- SLA 24 h: desde registro hasta primer contacto efectivo documentado.
  Fechas sin hora quedan no medibles; plazos todavía abiertos no entran en el
  denominador. No se imputa un contacto a un intento sin respuesta.
