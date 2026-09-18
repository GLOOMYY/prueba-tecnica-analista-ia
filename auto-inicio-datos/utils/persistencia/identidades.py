"""Concilia IDs de fuentes con identidades existentes sin fusionar empresas."""

from collections import defaultdict

from psycopg import sql
from psycopg.rows import dict_row

from .config import ErrorValidacion


def conciliar_identidades(conn, lote) -> None:
    """Reutiliza referencias estables o un contacto inequívoco de la empresa.

    La consulta de origen permanece como alias estable del lead canónico.
    Ante teléfonos compartidos, cambios de dueño o consolidaciones que agrupan
    varias identidades existentes, se rechaza el lote completo para revisión.
    Las declaraciones nuevas se conservan en consultas; no reescriben la ficha
    canónica ni las capturas, gestiones o responsables de la plataforma.
    """
    from dominio.identidad import nombres_compatibles

    with conn.cursor(row_factory=dict_row) as cursor:
        cursor.execute("SELECT * FROM leads")
        existentes = {r["lead_consolidado_id"]: r for r in cursor}
        cursor.execute(
            "SELECT lead_id_origen,lead_consolidado_id,empresa_id,telefono "
            "FROM consultas"
        )
        referencias, contactos = {}, defaultdict(set)
        for fila in cursor:
            referencias[fila["lead_id_origen"]] = fila
            if fila["telefono"]:
                contactos[(fila["empresa_id"], fila["telefono"])].add(
                    fila["lead_consolidado_id"]
                )
    consultas = defaultdict(list)
    for consulta in lote.filas["consultas"]:
        consultas[consulta["lead_consolidado_id"]].append(consulta)
    mapa, usados = {}, set()
    for lead in lote.filas["leads"]:
        origen, empresa = lead["lead_consolidado_id"], lead["empresa_id"]
        candidatos = {origen} if origen in existentes else set()
        for consulta in consultas[origen]:
            previa = referencias.get(consulta["lead_id_origen"])
            if previa:
                if previa["empresa_id"] != empresa:
                    raise ErrorValidacion(
                        "Referencia de fuente de otra empresa."
                    )
                candidatos.add(previa["lead_consolidado_id"])
            elif consulta.get("telefono"):
                encontrados = contactos[(empresa, consulta["telefono"])]
                if encontrados and (
                    len(encontrados) != 1
                    or not nombres_compatibles(
                        lead["nombre_presentacion"],
                        existentes[next(iter(encontrados))][
                            "nombre_presentacion"
                        ],
                    )
                ):
                    raise ErrorValidacion(
                        "Identidad ambigua entre lote y base: revisar fuentes."
                    )
                candidatos.update(encontrados)
        if len(candidatos) > 1:
            raise ErrorValidacion(
                "El lote intenta fusionar identidades existentes."
            )
        destino = next(iter(candidatos), origen)
        if destino in usados:
            raise ErrorValidacion(
                "Varias identidades del lote apuntan al mismo lead."
            )
        usados.add(destino)
        mapa[origen] = destino
        if destino in existentes:
            canonico = existentes[destino]
            if canonico["empresa_id"] != empresa:
                raise ErrorValidacion("Identidad canónica de otra empresa.")
            lead.update({clave: canonico[clave] for clave in lead})
    for filas in lote.filas.values():
        for fila in filas:
            if "lead_consolidado_id" in fila:
                fila["lead_consolidado_id"] = mapa.get(
                    fila["lead_consolidado_id"], fila["lead_consolidado_id"]
                )
            if fila.get("entidad_destino") == "leads":
                fila["identificador_destino"] = mapa.get(
                    fila["identificador_destino"],
                    fila["identificador_destino"],
                )


def validar_fuentes_inmutables(conn, lote, claves) -> None:
    """Impide que una foto vieja reescriba consultas o mensajes ya aceptados.

    Una corrección de una fuente ya cargada requiere resolución explícita.
    Se admite añadir nuevas consultas; se rechaza reemplazar evidencia previa.
    """
    for tabla in ("consultas", "conversaciones", "mensajes"):
        filas = lote.filas[tabla]
        if not filas:
            continue
        columnas = list(filas[0])
        with conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                sql.SQL("SELECT {} FROM {}").format(
                    sql.SQL(",").join(map(sql.Identifier, columnas)),
                    sql.Identifier(tabla),
                )
            )
            existentes = {
                tuple(r[c] for c in claves[tabla]): r for r in cursor
            }
        for fila in filas:
            anterior = existentes.get(tuple(fila[c] for c in claves[tabla]))
            if anterior is not None and anterior != fila:
                raise ErrorValidacion(
                    f"La fuente modifica evidencia aceptada en {tabla}; "
                    "requiere revisión antes de reemplazarla."
                )
