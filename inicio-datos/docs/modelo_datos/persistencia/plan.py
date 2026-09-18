"""Prepara filas relacionales conservando trazabilidad y separación."""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .config import VERSION, ErrorValidacion, huella, identidad
from .fuentes import (
    Fuentes,
    booleano,
    entero,
    indice,
    numero,
    opcional,
    temporal,
)

CLAVES = {
    "empresas": ("empresa_id",),
    "puntos_venta": ("punto_venta_id",),
    "asesores": ("asesor_id",),
    "marcas": ("marca_id",),
    "modelos_moto": ("sku",),
    "disponibilidad_modelo": ("sku", "punto_venta_id"),
    "leads": ("lead_consolidado_id",),
    "consultas": ("lead_id_origen",),
    "conversaciones": ("conversacion_id",),
    "mensajes": ("mensaje_id",),
    "ejecuciones": ("ejecucion_id",),
    "extracciones_ia": ("extraccion_id",),
    "intereses_modelo": ("interes_id",),
    "modelos_ml": ("modelo_ml_id",),
    "priorizaciones": ("priorizacion_id",),
    "historico_cierres": ("historico_id",),
    "archivos_fuente": ("archivo_id",),
    "ejecucion_archivos": ("ejecucion_id", "archivo_id"),
    "trazabilidad_registros": ("trazabilidad_id",),
    "incidencias": ("incidencia_id",),
}
ORDEN = (
    "empresas",
    "puntos_venta",
    "asesores",
    "marcas",
    "modelos_moto",
    "disponibilidad_modelo",
    "leads",
    "consultas",
    "conversaciones",
    "mensajes",
    "ejecuciones",
    "extracciones_ia",
    "intereses_modelo",
    "modelos_ml",
    "priorizaciones",
    "historico_cierres",
    "archivos_fuente",
    "ejecucion_archivos",
    "trazabilidad_registros",
    "incidencias",
)


@dataclass
class Lote:
    """Instantánea validada a cargar en una única transacción.

    Attributes:
        fuentes: Artefactos originales de entrada, ya verificados.
        filas: Filas por tabla de dominio.
        revision: Contenido excluido de la DB por vínculo desconocido.
        ejecucion_id: Identificador determinista de la carga.
        etapas: Identificadores de ejecuciones históricas importadas.
    """

    fuentes: Fuentes
    filas: dict[str, list[dict]] = field(
        default_factory=lambda: {nombre: [] for nombre in CLAVES}
    )
    revision: list[dict] = field(default_factory=list)
    ejecucion_id: str = ""
    etapas: dict[str, str] = field(default_factory=dict)

    def agregar(self, tabla: str, fila: dict) -> None:
        """Añade una fila a una tabla conocida."""
        self.filas[tabla].append(fila)

    def resumen(self) -> dict:
        """Resume conteos sin datos personales ni credenciales."""
        descartadas = sum(
            r["descartada"] for r in self.filas["conversaciones"]
        )
        return {
            "version": VERSION,
            "ejecucion_id": self.ejecucion_id,
            "conteos": {
                t: len(f) + (1 if t == "ejecuciones" else 0)
                for t, f in self.filas.items()
            },
            "conversaciones_descartadas_cargables": descartadas,
            "conversaciones_utilizables_cargables": (
                len(self.filas["conversaciones"]) - descartadas
            ),
            "conversaciones_revision_externa": sum(
                r["tipo"] == "conversacion_sin_vinculo" for r in self.revision
            ),
            "incidencias_revision_externa": sum(
                r["tipo"] == "incidencia_sin_vinculo" for r in self.revision
            ),
        }


def exigir(condicion: bool, mensaje: str) -> None:
    """Valida una condición del contrato incluso con Python optimizado."""
    if not condicion:
        raise ErrorValidacion(mensaje)


def preparar_ejecuciones(lote: Lote) -> None:
    """Identifica procesos previos sin inventar sus fechas reales."""
    archivos_codigo = sorted(Path(__file__).parent.glob("*.py"))
    archivos_codigo += sorted(
        (Path(__file__).parents[1] / "migrations").glob("*.sql")
    )
    fingerprint = {p.name: huella(p) for p in archivos_codigo}
    lote.ejecucion_id = identidad(VERSION, lote.fuentes.hashes, fingerprint)
    for etapa, name in {
        "normalizacion": "manifest.json",
        "extraccion": "manifest_extraccion_ia.json",
        "clasificacion": "manifest_clasificacion.json",
        "desbalance": "manifest_desbalance.json",
    }.items():
        manifest = lote.fuentes.objeto(name)
        eid = identidad(etapa, manifest)
        lote.etapas[etapa] = eid
        lote.agregar(
            "ejecuciones",
            {
                "ejecucion_id": eid,
                "etapa": etapa + "_importada",
                "version_codigo": str(manifest.get("version", "importada")),
                "huella_entrada": identidad(manifest),
                "importada": True,
                "inicio": None,
                "fin": None,
                "estado": "completada",
                "configuracion": manifest,
                "conteos": {},
                "errores": [],
            },
        )


def preparar_maestros(lote: Lote) -> None:
    """Obtiene empresas y sedes de relaciones explícitas y carga catálogo."""
    fuentes = lote.fuentes
    empresas, sedes = set(), {}
    for name in [
        "asesores.csv",
        "consultas_leads.csv",
        "historico_cierres.csv",
    ]:
        for fila in fuentes.lista(name):
            empresa, sede = fila["empresa_id"], fila["punto_venta_id"]
            exigir(bool(empresa), "Registro operativo sin empresa.")
            empresas.add(empresa)
            if sede:
                exigir(
                    sede not in sedes or sedes[sede] == empresa,
                    "Una sede aparece asociada a empresas distintas.",
                )
                sedes[sede] = empresa
    for empresa in sorted(empresas):
        lote.agregar("empresas", {"empresa_id": empresa, "nombre": None})
    for sede, empresa in sorted(sedes.items()):
        lote.agregar(
            "puntos_venta",
            {
                "punto_venta_id": sede,
                "empresa_id": empresa,
                "nombre": None,
                "ubicacion": None,
            },
        )
    for r in fuentes.lista("asesores.csv"):
        lote.agregar(
            "asesores",
            {
                "asesor_id": r["asesor_id"],
                "empresa_id": r["empresa_id"],
                "punto_venta_id": r["punto_venta_id"],
                "nombre": r["nombre"],
                "capacidad_diaria_leads": entero(r["capacidad_diaria_leads"]),
                "activo": booleano(r["activo"]),
                **temporal(
                    "fecha_ingreso",
                    r["fecha_ingreso"],
                    r["fecha_ingreso_precision"],
                ),
                "datos_originales": r,
            },
        )
    catalogo = fuentes.lista("catalogo_motos.csv")
    for marca in sorted({r["marca"] for r in catalogo}):
        lote.agregar("marcas", {"marca_id": identidad(marca), "nombre": marca})
    for r in catalogo:
        lote.agregar(
            "modelos_moto",
            {
                "sku": r["sku"],
                "marca_id": identidad(r["marca"]),
                "linea": r["linea"],
                "cilindraje": entero(r["cilindraje"]),
                "segmento": opcional(r["segmento"]),
                "precio_lista": numero(r["precio_lista"]),
                "unidades_disponibles": entero(r["unidades_disponibles"]),
                "datos_originales": r,
            },
        )
        for sede in sorted(set(r["puntos_venta_disponibles"].split("|"))):
            exigir(sede in sedes, "Sede del catálogo sin empresa verificable.")
            lote.agregar(
                "disponibilidad_modelo",
                {
                    "sku": r["sku"],
                    "punto_venta_id": sede,
                },
            )


def preparar_clientes(lote: Lote) -> None:
    """Conserva consultas y consolidados dentro de cada empresa."""
    leads = indice(lote.fuentes.lista("leads.csv"), "lead_consolidado_id")
    consultas = lote.fuentes.lista("consultas_leads.csv")
    indice(consultas, "lead_id")
    catalogo = {r["sku"] for r in lote.filas["modelos_moto"]}
    por_lead = {}
    for consulta in consultas:
        por_lead.setdefault(consulta["lead_consolidado_id"], []).append(
            consulta
        )

    def precision_agregada(valor: str, lid: str) -> str | None:
        """No atribuye hora exacta a un extremo con fechas de precisión día."""
        if any(
            q["fecha_registro"][:10] == valor[:10]
            and q["fecha_registro_precision"] == "fecha"
            for q in por_lead.get(lid, [])
        ):
            return "fecha"
        return None

    for r in leads.values():
        lote.agregar(
            "leads",
            {
                "lead_consolidado_id": r["lead_consolidado_id"],
                "empresa_id": r["empresa_id"],
                "nombre_presentacion": opcional(r["nombre_presentacion"]),
                **temporal(
                    "primera_fecha_registro",
                    r["primera_fecha_registro_resuelta"],
                    precision_agregada(
                        r["primera_fecha_registro_resuelta"],
                        r["lead_consolidado_id"],
                    ),
                ),
                **temporal(
                    "ultima_fecha_registro",
                    r["ultima_fecha_registro_resuelta"],
                    precision_agregada(
                        r["ultima_fecha_registro_resuelta"],
                        r["lead_consolidado_id"],
                    ),
                ),
                "reglas_identidad": json.loads(r["reglas_identidad"]),
                "datos_originales": r,
            },
        )
    for r in consultas:
        lead = leads.get(r["lead_consolidado_id"])
        exigir(
            lead is not None and lead["empresa_id"] == r["empresa_id"],
            "Consulta con vínculo inexistente o cruzado entre empresas.",
        )
        exigir(
            not r["modelo_sku"] or r["modelo_sku"] in catalogo,
            "SKU de consulta no existe en catálogo.",
        )
        lote.agregar(
            "consultas",
            {
                "lead_id_origen": r["lead_id"],
                "lead_consolidado_id": r["lead_consolidado_id"],
                "empresa_id": r["empresa_id"],
                "punto_venta_id": opcional(r["punto_venta_id"]),
                "canal": opcional(r["canal"]),
                "campania": opcional(r["campania"]),
                "nombre_declarado": opcional(r["nombre_cliente"]),
                "telefono": opcional(r["telefono"]),
                "email": opcional(r["email"]),
                "ciudad": opcional(r["ciudad"]),
                "modelo_declarado": opcional(r["modelo_interes_texto"]),
                "modelo_sku": opcional(r["modelo_sku"]),
                "estado_gestion": opcional(r["estado_gestion"]),
                **temporal(
                    "fecha_registro",
                    r["fecha_registro"],
                    r["fecha_registro_precision"],
                ),
                **temporal(
                    "fecha_primer_contacto",
                    r["fecha_primer_contacto"],
                    r["fecha_primer_contacto_precision"],
                ),
                "calidad": {
                    k: v
                    for k, v in r.items()
                    if k.endswith(("_estado", "_criterio", "_comentario"))
                },
                "datos_originales": r,
            },
        )


def verificar_evidencias(valor: object, mensajes: list[dict]) -> None:
    """Comprueba citas del resultado contra mensaje y emisor originales."""
    if isinstance(valor, dict):
        if {"mensaje", "emisor", "texto"} <= valor.keys():
            posicion = valor["mensaje"]
            exigir(
                isinstance(posicion, int) and 1 <= posicion <= len(mensajes),
                "Evidencia con posición de mensaje inexistente.",
            )
            mensaje = mensajes[posicion - 1]
            exigir(
                valor["emisor"] == mensaje["emisor"]
                and bool(valor["texto"])
                and valor["texto"] in mensaje["texto"],
                "Evidencia no coincide con texto/emisor de la fuente.",
            )
        for item in valor.values():
            verificar_evidencias(item, mensajes)
    elif isinstance(valor, list):
        for item in valor:
            verificar_evidencias(item, mensajes)


def preparar_extraccion(lote: Lote, c: dict, e: dict) -> None:
    """Preserva resultado íntegro y proyecta todas sus menciones de modelos."""
    cid = c["conversacion_id"]
    exigir(
        all(
            e[k] == c[k]
            for k in ("empresa_id", "lead_id", "lead_consolidado_id")
        ),
        "Extracción y conversación tienen vínculos distintos.",
    )
    verificar_evidencias(e["extraccion"], c["mensajes"])
    eid = identidad(lote.etapas["extraccion"], cid)
    lote.agregar(
        "extracciones_ia",
        {
            "extraccion_id": eid,
            "conversacion_id": cid,
            "ejecucion_id": lote.etapas["extraccion"],
            "proveedor": "Google",
            "modelo_ia": e["modelo"],
            "version_prompt": e["version_prompt"],
            "version_normalizador": e["version_normalizador"],
            "estado_validacion": e.get("estado_extraccion"),
            "revision_semantica": e.get("revision_semantica"),
            "huella_conversacion": e.get("huella_conversacion"),
            "huella_configuracion": e.get("huella"),
            "resultado": e["extraccion"],
            "datos_originales": e,
        },
    )
    catalogo = {r["sku"] for r in lote.filas["modelos_moto"]}
    for i, interes in enumerate(e["extraccion"]["modelos_interes"]):
        matches = {
            m.get("sku")
            for m in e["catalogo"]
            if m["mencion"] == interes["valor"] and m.get("sku")
        }
        sku = next(iter(matches)) if len(matches) == 1 else None
        exigir(
            sku is None or sku in catalogo, "SKU extraído fuera del catálogo."
        )
        lote.agregar(
            "intereses_modelo",
            {
                "interes_id": identidad(eid, i),
                "extraccion_id": eid,
                "texto_mencionado": interes["valor"],
                "modelo_sku": sku,
                "estado_identificacion": "identificado"
                if sku
                else "sin_resolver",
                "evidencias": interes["evidencias"],
            },
        )


def preparar_conversaciones(lote: Lote) -> set[str]:
    """Excluye huérfanas antes de aplicar el flag de descartada.

    Returns:
        Identificadores que permanecerán exclusivamente en revisión externa.
    """
    fuentes = lote.fuentes
    consultas = indice(fuentes.lista("consultas_leads.csv"), "lead_id")
    todas = indice(fuentes.lista("conversaciones.json"), "conversacion_id")
    descartadas = indice(
        fuentes.lista("extracciones_conversaciones_descartadas.json"),
        "conversacion_id",
    )
    extracciones = {}
    for e in fuentes.lista("extracciones_conversaciones_ia.json"):
        cid = e["extraccion"]["conversacion_id"]
        exigir(cid not in extracciones, "Extracción utilizable duplicada.")
        extracciones[cid] = e
    exigir(
        not set(extracciones) & set(descartadas),
        "Una conversación figura como utilizable y descartada.",
    )
    exigir(
        set(todas) == set(extracciones) | set(descartadas),
        "El conjunto aceptado/descartado no cubre las conversaciones.",
    )
    aceptadas = indice(
        fuentes.lista("conversaciones_utilizables_ia.json"), "conversacion_id"
    )
    exigir(
        set(aceptadas) == set(extracciones),
        "Conversaciones aceptadas y extracciones no coinciden.",
    )
    externas = set()
    for cid, c in todas.items():
        d = descartadas.get(cid)
        if d:
            exigir(
                d["conversacion_original"] == c,
                "La copia descartada no coincide con su conversación.",
            )
            e = d["extraccion_original"]
        else:
            exigir(aceptadas[cid] == c, "La copia utilizable fue alterada.")
            e = extracciones[cid]
        q = consultas.get(c["lead_id"])
        valido = q is not None and all(
            c[k] == q[k] for k in ("empresa_id", "lead_consolidado_id")
        )
        if not valido:
            externas.add(cid)
            lote.revision.append(
                {
                    "tipo": "conversacion_sin_vinculo",
                    "motivo": "Sin vínculo verificable: fuera de la base.",
                    "conversacion": c,
                    "extraccion": e,
                    "descarte": d,
                }
            )
            continue
        lote.agregar(
            "conversaciones",
            {
                "conversacion_id": cid,
                "lead_id_origen": c["lead_id"],
                "lead_consolidado_id": c["lead_consolidado_id"],
                "empresa_id": c["empresa_id"],
                "canal": c["canal"],
                **temporal("fecha_inicio", c["fecha_inicio"]),
                "lead_id_recibido": c.get("lead_id_recibido"),
                "descartada": d is not None,
                "motivos_descarte": d["motivos"] if d else [],
                "fecha_descarte": None,
                "politica_descarte": d["politica"] if d else None,
                "datos_originales": {
                    k: v for k, v in c.items() if k != "mensajes"
                },
            },
        )
        for posicion, mensaje in enumerate(c["mensajes"], start=1):
            lote.agregar(
                "mensajes",
                {
                    "mensaje_id": identidad(cid, posicion),
                    "conversacion_id": cid,
                    "posicion": posicion,
                    "emisor": mensaje["emisor"],
                    "hora_original": mensaje.get("hora"),
                    "texto": mensaje["texto"],
                },
            )
        preparar_extraccion(lote, c, e)
    return externas


def preparar_modelos(lote: Lote) -> str:
    """Registra artefactos sin deserializarlos ni cambiar su procedencia."""
    fuentes = lote.fuentes
    ficha = fuentes.objeto("ficha_modelo.json")
    nombres = [
        (
            "modelo_experimental.joblib",
            "clasificacion",
            ficha,
            "experimental_generador_scores_actuales",
        ),
        (
            "desbalance_v2/modelo_sin_pesos.joblib",
            "desbalance",
            fuentes.objeto("manifest_desbalance.json"),
            "experimental_elegido",
        ),
        (
            "desbalance_v2/modelo_balanced.joblib",
            "desbalance",
            fuentes.objeto("manifest_desbalance.json"),
            "experimental_comparacion",
        ),
    ]
    ids = []
    for name, etapa, metadata, estado in nombres:
        path = fuentes.out / name
        digest = huella(path)
        mid = identidad(name, digest)
        ids.append(mid)
        lote.agregar(
            "modelos_ml",
            {
                "modelo_ml_id": mid,
                "ejecucion_id": lote.etapas[etapa],
                "algoritmo": "regresion_logistica",
                "version": str(metadata["version"]),
                "ruta_artefacto": path.relative_to(fuentes.root).as_posix(),
                "hash_artefacto": digest,
                "estado": estado,
                "configuracion": metadata,
                "metricas": metadata.get(
                    "metricas_prueba", metadata.get("metricas_julio", [])
                ),
                "limitaciones": metadata.get("limitaciones", []),
            },
        )
    return ids[0]


def preparar_prioridades(lote: Lote, modelo_id: str) -> None:
    """Carga scores y su contexto; rechaza usar conversaciones descartadas."""
    fuentes = lote.fuentes
    leads = indice(lote.filas["leads"], "lead_consolidado_id")
    consultas = indice(lote.filas["consultas"], "lead_id_origen")
    conversaciones = indice(lote.filas["conversaciones"], "conversacion_id")
    contextos = indice(
        fuentes.lista("contexto_priorizacion.json"), "lead_consolidado_id"
    )
    prioridades = fuentes.lista("priorizacion_leads.json")
    exigir(
        set(indice(prioridades, "lead_consolidado_id")) == set(leads),
        "La clasificación no cubre exactamente los leads actuales.",
    )
    for r in prioridades:
        lid, empresa = r["lead_consolidado_id"], r["empresa_id"]
        exigir(
            leads[lid]["empresa_id"] == empresa,
            "Prioridad con empresa distinta a la del lead.",
        )
        qid, cid = r["lead_id_contexto"], r["conversacion_id_contexto"]
        for key, mapa in [(qid, consultas), (cid, conversaciones)]:
            if key:
                referencia = mapa.get(key)
                exigir(
                    referencia is not None
                    and referencia["empresa_id"] == empresa
                    and referencia["lead_consolidado_id"] == lid,
                    "Contexto de prioridad inexistente o cruzado.",
                )
        if cid:
            exigir(
                not conversaciones[cid]["descartada"]
                and conversaciones[cid]["lead_id_origen"] == qid,
                "La prioridad usa una conversación descartada o ajena.",
            )
        contexto = contextos[lid]
        exigir(
            contexto["empresa_id"] == empresa
            and contexto["conversacion_id_contexto"] == cid,
            "El archivo de contexto no corresponde a la prioridad.",
        )
        for referencia in contexto["conversaciones_utilizables"]:
            c = conversaciones.get(referencia)
            exigir(
                c is not None
                and not c["descartada"]
                and (c["empresa_id"], c["lead_consolidado_id"])
                == (empresa, lid),
                "Contexto con referencias no utilizables.",
            )
        lote.agregar(
            "priorizaciones",
            {
                "priorizacion_id": identidad(
                    lote.etapas["clasificacion"], lid
                ),
                "lead_consolidado_id": lid,
                "empresa_id": empresa,
                "ejecucion_id": lote.etapas["clasificacion"],
                "lead_id_contexto": qid,
                "conversacion_id_contexto": cid,
                "modelo_ml_id": modelo_id,
                "score_prioridad": numero(r["score_prioridad"]),
                "score_modelo_experimental": numero(
                    r["score_modelo_experimental"]
                ),
                "temperatura": r["temperatura"],
                "cola": r["cola"],
                "explicacion": r["explicacion_prioridad"],
                "accion_sugerida": r["accion_sugerida"],
                "version_reglas": r["metodo_prioridad"],
                "contexto": contexto,
                "datos_originales": r,
            },
        )


def preparar_historico(lote: Lote) -> None:
    """Mantiene todos los desenlaces, incluidos los históricos sin gestión."""
    for r in lote.fuentes.lista("historico_cierres.csv"):
        lote.agregar(
            "historico_cierres",
            {
                "historico_id": r["lead_id"],
                "empresa_id": r["empresa_id"],
                "punto_venta_id": opcional(r["punto_venta_id"]),
                "modelo_sku": opcional(r["modelo_sku"]),
                "modelo_cotizado": r["modelo_cotizado"],
                **temporal(
                    "fecha_registro",
                    r["fecha_registro"],
                    r["fecha_registro_precision"],
                ),
                "canal": r["canal"],
                "precio_lista": numero(r["precio_lista"]),
                "horas_al_primer_contacto": numero(
                    r["horas_al_primer_contacto"]
                ),
                "numero_contactos": entero(r["numero_contactos"]),
                "manifesto_cuota_inicial": r["manifesto_cuota_inicial"],
                "forma_pago_declarada": r["forma_pago_declarada"],
                "pidio_cita": r["pidio_cita"],
                "desenlace": r["desenlace"],
                "datos_originales": r,
            },
        )


def preparar_auditoria(lote: Lote, externas: set[str]) -> None:
    """Conserva incidencias, pero no importa contenido de huérfanas."""
    fuentes = lote.fuentes
    empresas = {r["empresa_id"] for r in lote.filas["empresas"]}
    duenos = {}
    for tabla, clave in [
        ("consultas", "lead_id_origen"),
        ("leads", "lead_consolidado_id"),
        ("conversaciones", "conversacion_id"),
        ("asesores", "asesor_id"),
        ("historico_cierres", "historico_id"),
    ]:
        duenos.update({r[clave]: r["empresa_id"] for r in lote.filas[tabla]})
    for ruta, digest in fuentes.hashes.items():
        aid = identidad(ruta, digest)
        lote.agregar(
            "archivos_fuente",
            {
                "archivo_id": aid,
                "nombre": Path(ruta).name,
                "ruta": ruta,
                "hash_contenido": digest,
            },
        )
        lote.agregar(
            "ejecucion_archivos",
            {
                "ejecucion_id": lote.ejecucion_id,
                "archivo_id": aid,
                "funcion": "entrada_validada",
            },
        )
    for i, r in enumerate(fuentes.lista("trazabilidad_leads.csv")):
        destino = opcional(r["lead_consolidado_id"])
        lote.agregar(
            "trazabilidad_registros",
            {
                "trazabilidad_id": identidad(lote.etapas["normalizacion"], i),
                "archivo_id": fuentes.id_archivo("trazabilidad_leads.csv"),
                "ejecucion_id": lote.etapas["normalizacion"],
                "empresa_id": r["empresa_origen"]
                if r["empresa_origen"] in empresas
                else None,
                "referencia_origen": r["fila_origen"],
                "entidad_destino": "leads" if destino else None,
                "identificador_destino": destino,
                "accion": r["accion"],
                "motivo": opcional(r["motivo_exclusion"]),
                "detalle": r,
            },
        )
    for name, etapa in [
        ("incidencias_datos.json", "normalizacion"),
        ("incidencias_extraccion_ia.json", "extraccion"),
        ("incidencias_modelado.json", "clasificacion"),
    ]:
        contenido = fuentes.valores[name]
        eventos = (
            contenido["incidencias"]
            if isinstance(contenido, dict)
            else contenido
        )
        for i, evento in enumerate(eventos):
            cids = set(re.findall(r"CONV-\d+", json.dumps(evento)))
            if cids & externas:
                lote.revision.append(
                    {
                        "tipo": "incidencia_sin_vinculo",
                        "archivo": name,
                        "incidencia": evento,
                    }
                )
                continue
            referencia = next(
                (
                    evento.get(k)
                    for k in (
                        "conversacion_id",
                        "lead_consolidado_id",
                        "lead_id",
                        "id_origen",
                    )
                    if evento.get(k)
                ),
                None,
            )
            referencias = (
                referencia if isinstance(referencia, list) else [referencia]
            )
            propietarios = {
                duenos.get(ref) for ref in referencias if isinstance(ref, str)
            }
            inferida = (
                next(iter(propietarios)) if len(propietarios) == 1 else None
            )
            empresa = evento.get("empresa_id") or inferida
            lote.agregar(
                "incidencias",
                {
                    "incidencia_id": identidad(lote.etapas[etapa], name, i),
                    "ejecucion_id": lote.etapas[etapa],
                    "empresa_id": empresa if empresa in empresas else None,
                    "entidad_afectada": evento.get("tabla"),
                    "identificador_afectado": str(referencia)
                    if referencia
                    else None,
                    "campo": evento.get("campo"),
                    "tipo": evento.get("tipo", "sin_tipo"),
                    "decision": evento.get("accion", evento.get("decision")),
                    "estado": evento.get("estado"),
                    "fecha": None,
                    "antes": evento.get("antes", evento.get("valor_original")),
                    "despues": evento.get(
                        "despues", evento.get("valor_resultante")
                    ),
                    "detalle": evento,
                },
            )


def preparar_lote(root: Path) -> Lote:
    """Valida las fuentes y prepara la carga sin conectar a PostgreSQL."""
    lote = Lote(Fuentes(root))
    preparar_ejecuciones(lote)
    preparar_maestros(lote)
    preparar_clientes(lote)
    externas = preparar_conversaciones(lote)
    modelo_id = preparar_modelos(lote)
    preparar_prioridades(lote, modelo_id)
    preparar_historico(lote)
    preparar_auditoria(lote, externas)
    for tabla, filas in lote.filas.items():
        claves = [tuple(r[k] for k in CLAVES[tabla]) for r in filas]
        exigir(
            len(claves) == len(set(claves)),
            f"Claves duplicadas al preparar {tabla}.",
        )
    return lote
