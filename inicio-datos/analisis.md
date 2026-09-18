# Prueba Tecnica

## Contexto

- Empresa de venta de motos con 15 puntos de venta en Antioquia, Bogota, la Costa Atlantica
- El grupo lo conforma con otras dos comercializadoras
- Las 3 comparten el mismo CRM
- **Cada empresa solo puede ver sus propios clientes**
- Leads llegan por 3 canales:
  1. Call Center
  2. Formularios campaña Meta
  3. Formulario sitio web
- Leads caen todos a una sola bandeja y los asesores los contactan por orden de llegada
- `“Estamos recibiendo más de 3.000 leads al mes y de cada diez que gestionamos cerramos menos de uno. Los asesores llaman al que llegó primero, no al que más probabilidad tiene de comprar. Cuatro de cada diez leads no se tocan en las primeras 24 horas, y ahí es donde se pierden. Además, la conversación de WhatsApp tiene toda la información —qué moto quiere, cuánto tiene de inicial, si va por crédito— pero nadie la pasa al CRM, así que el asesor arranca de cero en cada llamada.”` Gerente General.

## Reto

Construir una solución automatizada, versionada, con bd y publicada, que convierta leads crudos en una lista priorizada de gestion diaria por asesor (Una pila o cola?), enriquecida por la informacion hoy enterrada en las conversaciones

## Alcance mínimo

1. Ingerir los archivos fuente entregados sin intervención manual.
2. Normalizar y consolidar: unificar formatos de teléfono, fecha, ciudad y modelo;
   detectar y resolver leads duplicados, considerando que una misma persona pudo
   haber escrito por dos canales distintos.
3. Extraer con IA la información estructurada que está en las conversaciones: modelo
   de interés, presupuesto o cuota inicial mencionada, forma de pago, intención
   declarada, objeción principal y si pidió cita o cotización.
4. Clasificar y priorizar: asignar a cada lead una temperatura o score de prioridad con
   una lógica explicable y sustentada. No se exige un modelo entrenado desde cero; se
   exige criterio y justificación de la aproximación elegida.
5. Persistir todo en una base de datos con un modelo de datos propio. Los archivos
   planos y las hojas de cálculo no cuentan como almacenamiento final.
6. Automatizar la ejecución de punta a punta: el flujo debe poder correr solo, de forma
   programada o disparada por evento, sin que nadie ejecute pasos a mano.
7. Publicar el resultado en una URL pública y funcional: un tablero, una vista de “mis
   leads de hoy” o una API consumible. Debe estar operando el día de la sustentación.
8. Respetar la separación por empresa: la información de una comercializadora no
   puede quedar visible para otra.

## Insumos

Datos sinteticos, poner atencion a las inconsistencias, detectar y resolver hace parte del ejercicio

`Descripcion en el pdf`

`Sugerencia: El histórico es la única fuente que le permite validar con datos si su lógica de priorización realmente separa a los que cierran de los que no. Úselo.`

`Podria servir el historico para entrenar un modelo de calificacion de usuarios`

## Condiciones

1. **Automatización:**
   El proceso completo se ejecuta con un solo disparo: comando, cron, webhook, workflow o agente. Un notebook que se corre celda por celda no cumple.
2. **Repositorio:**
   Código en GitHub o GitLab, público o con acceso para el evaluador, con historial de commits real (no un único commit final), README y instrucciones de ejecución.
3. **Base de datos:**
   Motor relacional o vectorial a elección (PostgreSQL, Supabase, SQL Server, SQLite y similares), con el esquema versionado o el script de creación dentro del repositorio.
4. **Publicación:**
   URL accesible desde internet: Vercel, Streamlit Cloud, Render, Hugging Face Spaces, Railway, VPS propio u otro.
5. **Sustentación:**
   Demostración en vivo sobre la URL publicada, no sobre capturas de pantalla.

## Lo que decido yo

1. Lenguaje: Python
2. Framework: FastAPI o Django, aun no lo decido
3. Proveedor de IA: Veremos cual nos sale gratuito
4. Arquitectura: Un unico servicio por ahora
5. Alcance del tablero son decisión suya: decidimos al analizar bien toda la data y tener lista la api

## Entregables

1. Enlace al repo
2. URL publica a la solucion
3. README con: qué hace, cómo se ejecuta, decisiones tomadas, supuestos asumidos y qué haría con más tiempo.
4. Diagrama de arquitectura
5. PPTX con maximo 8 diapositivas para la sustentacion.

## Calificacion

| Bloque                                            | Peso |
| ------------------------------------------------- | ---: |
| Entendimiento del negocio y encuadre del problema |   10 |
| Datos y base de datos                             |   15 |
| Automatización y orquestación                     |   15 |
| Componente de IA                                  |   20 |
| Ingeniería de software y repositorio              |   12 |
| Despliegue y publicación                          |   10 |
| Producto entregado y usabilidad                   |    6 |
| Documentación                                     |    5 |
| Sustentación y comunicación                       |    7 |

## Descalificables

Condiciones que descalifican la entrega

- No entregar repositorio o no entregar URL pública.
- Exponer credenciales, llaves de API o datos personales reales en el repositorio.
- No poder explicar el funcionamiento del propio código durante la sustentación.
- Entregar una solución copiada sin adaptación ni comprensión.
- Que la URL publicada no funcione el día de la sustentación, sin explicación razonable.
