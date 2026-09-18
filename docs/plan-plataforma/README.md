# Plan de trabajo: plataforma, API y operación automática

**Estado:** ejecución iniciada. T00 y T01 están cerradas con evidencia local; se
implementó la primera base de identidad de T03/T04. No se han desplegado cambios
ni modificado datos remotos. Fecha de elaboración: 2026-09-17.

## Orden de lectura

1. [Plan maestro](PLAN_MAESTRO.md): alcance, arquitectura, decisiones, fases,
   criterios de aceptación, riesgos y entrega.
2. [Contratos funcionales y técnicos](CONTRATOS.md): permisos, alta de leads,
   scoring, asignación diaria, API y convivencia con el pipeline.
3. [Trabajo entre agentes](AGENTES.md): roles, propiedad de archivos, acuerdos,
   revisiones, dependencias y mensajes para delegar tareas.
4. [Tablero de ejecución](TABLERO.md): tareas identificadas, dependencias,
   responsables y evidencias necesarias para cerrarlas.
5. [Decisiones de implementación](DECISIONES.md): decisiones aceptadas, pendientes
   y baseline al iniciar la ejecución.

## Resultado que se busca

Una aplicación Django con tablero, **mis leads de hoy**, detalle de clientes,
alta de leads con prioridad persistida y una API REST consumible. La solución
debe estar publicada, aislar cada empresa y ejecutar su procesamiento sin
depender de que alguien abra notebooks o mantenga su computador encendido.

Los cuatro documentos forman un único plan. Los contratos son propuestas
operativas para ejecutar el alcance; el coordinador y los revisores deben
ratificarlos en G0 antes de implementar. No se afirma que los agentes ya hayan
discutido o aprobado estas decisiones.

## Fuentes de verdad

- [Enunciado original](../../inicio-datos/Assessment-Analista-IA-Enunciado.pdf).
- [Guía del repositorio](../../AGENTS.md).
- [Modelo y persistencia existentes](../../inicio-datos/docs/modelo_datos/README.md).
- [Estado del flujo automático](../../auto-inicio-datos/VERIFICACION.md).
- [Configuración inicial de Django](../../plataforma/README.md).

Las instrucciones posteriores del usuario prevalecen sobre este plan. Cada
ajuste debe actualizar los contratos y las tareas afectadas; no mantener dos
decisiones contradictorias en documentos distintos.
