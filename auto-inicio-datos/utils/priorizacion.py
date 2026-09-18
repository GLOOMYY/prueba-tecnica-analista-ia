"""Aplica reglas y reajusta la regresión ya elegida sin reabrir selección."""

from pathlib import Path

from .reglas_priorizacion import (
    elegir_ultima,
    explicar_reglas,
    inicial_de_extraccion,
    preparar_historico,
    registros,
    score_reglas,
    sha,
)


def ejecutar(root: Path) -> dict:
    """Aplica reglas y reajusta la regresión ya elegida sin reabrir selección.

    Args:
        root: Directorio de trabajo con data y outputs.

    Returns:
        Resumen verificable de la etapa.
    """
    import importlib.metadata as metadata
    import json

    import joblib
    import numpy as np
    import pandas as pd
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder

    ROOT = root
    DATA = ROOT / "data/processed"
    OUT = ROOT / "outputs/clasificacion_04"
    OUT.mkdir(parents=True, exist_ok=True)
    SEED = 42
    VERSION = "04-auto-v1"
    ENTRADAS = [
        "historico_cierres.csv",
        "leads.csv",
        "consultas_leads.csv",
        "extracciones_conversaciones_ia.json",
        "conversaciones_utilizables_ia.json",
    ]

    hashes_entrada = {p: sha(DATA / p) for p in ENTRADAS}
    hist = pd.read_csv(DATA / "historico_cierres.csv")
    leads = pd.read_csv(DATA / "leads.csv")
    consultas = pd.read_csv(DATA / "consultas_leads.csv")
    extracciones = json.loads(
        (DATA / "extracciones_conversaciones_ia.json").read_text(
            encoding="utf-8"
        )
    )
    conversaciones = json.loads(
        (DATA / "conversaciones_utilizables_ia.json").read_text(
            encoding="utf-8"
        )
    )
    incidencias = []
    pd.set_option("display.max_colwidth", 100)
    if not not hist.duplicated(["empresa_id", "lead_id"]).any():
        raise ValueError(
            "Clave histórica repetida: revisar antes de entrenar."
        )
    if not not leads.duplicated(["empresa_id", "lead_consolidado_id"]).any():
        raise ValueError(
            "Contrato incumplido: not leads.duplicated(['empr"
            "esa_id', 'lead_consolidado_id']).any()"
        )
    if not set(hist.desenlace.dropna()) <= {
        "Cerrado",
        "Perdido",
        "Sin gestión",
    }:
        raise ValueError(
            "Contrato incumplido: set(hist.desenlace.dropna()"
            ") <= {'Cerrado', 'Perdido', 'Sin gestión'}"
        )
    hist["fecha"] = pd.to_datetime(
        hist.fecha_registro, format="%Y-%m-%d", errors="coerce"
    )
    sin_etiqueta = ~hist.desenlace.isin(["Cerrado", "Perdido"])
    sin_fecha = hist.fecha.isna()
    for _, r in hist[sin_etiqueta | sin_fecha].iterrows():
        incidencias.append(
            {
                "tipo": "fuera_del_entrenamiento",
                "empresa_id": r.empresa_id,
                "lead_id": r.lead_id,
                "motivo": "Resultado no observado: no se convierte en perdido."
                if sin_etiqueta.loc[r.name]
                else "Fecha de registro inválida: no permite partición temporal.",
                "accion": "Conservar en la fuente; excluir solo de este experimento.",
            }
        )
    historico = hist[~sin_etiqueta & ~sin_fecha].copy()
    historico["y"] = historico.desenlace.eq("Cerrado").astype(int)
    PERFILES = {
        "ingreso": ["canal"],
        "comercial": [
            "canal",
            "modelo_sku",
            "manifesto_cuota_inicial",
            "forma_pago_declarada",
            "cita_observada",
        ],
    }

    X = preparar_historico(historico)
    if not not set(
        [
            "numero_contactos",
            "desenlace",
            "empresa_id",
            "horas_al_primer_contacto",
        ]
    ) & set(X.columns):
        raise ValueError(
            "Contrato incumplido: not set(['numero_contactos'"
            ", 'desenlace', 'empresa_id', 'horas_al_primer_co"
            "ntacto']) & set(X.columns)"
        )

    columnas_elegidas = PERFILES["comercial"]
    elegido = "comercial_logistica_1.0_sin_pesos"
    desarrollo = historico[historico.fecha.between("2026-03-01", "2026-06-30")]
    if desarrollo.y.nunique() != 2:
        raise ValueError("El histórico de desarrollo requiere ambas clases.")
    modelo_final = Pipeline(
        [
            (
                "categorias",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
            ),
            (
                "modelo",
                LogisticRegression(
                    C=1.0, class_weight=None, max_iter=2000, random_state=SEED
                ),
            ),
        ]
    ).fit(X.loc[desarrollo.index, columnas_elegidas], desarrollo.y)
    conv_por_id = {c["conversacion_id"]: c for c in conversaciones}
    if not len(conv_por_id) == len(conversaciones):
        raise ValueError(
            "Contrato incumplido: len(conv_por_id) == len(conversaciones)"
        )
    if not {e["extraccion"]["conversacion_id"] for e in extracciones} == set(
        conv_por_id
    ):
        raise ValueError(
            "Contrato incumplido: {e['extraccion']['conversac"
            "ion_id'] for e in extracciones} == set(conv_por_"
            "id)"
        )
    consultas_por_id = consultas.set_index("lead_id", drop=False)
    if not consultas_por_id.index.is_unique:
        raise ValueError(
            "Contrato incumplido: consultas_por_id.index.is_unique"
        )
    claves_lead = set(
        zip(leads.empresa_id, leads.lead_consolidado_id, strict=False)
    )
    por_lead, huerfanas = ({}, [])
    for e in extracciones:
        clave = (e["empresa_id"], e["lead_consolidado_id"])
        cid = e["extraccion"]["conversacion_id"]
        if clave not in claves_lead:
            huerfanas.append(
                {
                    "conversacion_id": cid,
                    "empresa_id": e["empresa_id"],
                    "lead_id": e["lead_id"],
                    "motivo": (
                        "Sin vínculo verificable a un lead y empresa; con"
                        "servar fuera de la cola."
                    ),
                }
            )
            continue
        if e["lead_id"] not in consultas_por_id.index:
            raise ValueError(
                "Contrato incumplido: e['lead_id'] in consultas_por_id.index"
            )
        q = consultas_por_id.loc[e["lead_id"]]
        if not (q.empresa_id, q.lead_consolidado_id) == clave:
            raise ValueError(
                "Contrato incumplido: (q.empresa_id, q.lead_conso"
                "lidado_id) == clave"
            )
        c = conv_por_id[cid]
        if not (c["empresa_id"], c["lead_consolidado_id"], c["lead_id"]) == (
            *clave,
            e["lead_id"],
        ):
            raise ValueError(
                "Contrato incumplido: (c['empresa_id'], c['lead_c"
                "onsolidado_id'], c['lead_id']) == (*clave, e['le"
                "ad_id'])"
            )
        por_lead.setdefault(clave, []).append(e)
    incidencias.extend(
        {"tipo": "conversacion_sin_vinculo", **r} for r in huerfanas
    )

    filas, contextos = ([], [])
    for _, lead in leads.iterrows():
        clave = (lead.empresa_id, lead.lead_consolidado_id)
        qs = consultas[
            (consultas.empresa_id == clave[0])
            & (consultas.lead_consolidado_id == clave[1])
        ]
        if not len(qs) > 0:
            raise ValueError("Contrato incumplido: len(qs) > 0")
        es = por_lead.get(clave, [])
        e, problema = (None, None)
        if es:
            posicion, problema = elegir_ultima(
                [
                    conv_por_id[x["extraccion"]["conversacion_id"]][
                        "fecha_inicio"
                    ]
                    for x in es
                ]
            )
            if posicion is not None:
                e = es[posicion]
            else:
                incidencias.append(
                    {
                        "tipo": "orden_conversaciones_ambiguo",
                        "empresa_id": clave[0],
                        "lead_consolidado_id": clave[1],
                        "motivo": problema,
                        "accion": "No usar señales conversacionales; conservar fuentes.",
                    }
                )
        qpos, qproblema = elegir_ultima(qs.fecha_registro.tolist())
        q = (
            consultas_por_id.loc[e["lead_id"]]
            if e
            else qs.iloc[qpos]
            if qpos is not None
            else None
        )
        if qproblema and e is None:
            incidencias.append(
                {
                    "tipo": "orden_consultas_ambiguo",
                    "empresa_id": clave[0],
                    "lead_consolidado_id": clave[1],
                    "motivo": qproblema,
                    "accion": "Solo conservar canal/modelo comunes; no inventar orden.",
                }
            )

        def valor_consulta(c, q=q, qs=qs):
            """Valor consulta."""
            if q is not None:
                return str(q[c]) if pd.notna(q[c]) else "DESCONOCIDO"
            valores = qs[c].fillna("DESCONOCIDO").unique()
            return str(valores[0]) if len(valores) == 1 else "DESCONOCIDO"

        ex = e["extraccion"] if e else None
        sku = valor_consulta("modelo_sku")
        if e and ex["modelos_interes"]:
            skus = {m.get("sku") for m in e["catalogo"] if m.get("sku")}
            sku = (
                next(iter(skus))
                if len(skus) == 1 and all(m.get("sku") for m in e["catalogo"])
                else "AMBIGUO"
            )
        pago = ex["forma_pago"]["valor"] if ex else "desconocida"
        pago = pago if pago in ["credito", "contado"] else "no_informa"
        fila = {
            "empresa_id": clave[0],
            "lead_consolidado_id": clave[1],
            "lead_id_contexto": str(q.lead_id) if q is not None else None,
            "conversacion_id_contexto": ex["conversacion_id"] if ex else None,
            "numero_conversaciones_utilizables": len(es),
            "canal": valor_consulta("canal"),
            "modelo_sku": sku,
            "manifesto_cuota_inicial": inicial_de_extraccion(ex)
            if ex
            else "NO_INFORMA",
            "forma_pago_declarada": pago,
            "cita_observada": "SI"
            if ex and ex["cita"]["cliente_solicito"]["estado"] == "si"
            else "NO_OBSERVADA",
            "fecha_antiguedad": lead.primera_fecha_registro_resuelta,
            "todas_consultas_descartadas": bool(
                qs.estado_gestion.eq("Descartado").all()
            ),
            "estado_contexto": "conversacion_utilizable"
            if e
            else "revision_orden"
            if problema
            else "sin_conversacion_utilizable",
        }
        filas.append(fila)
        contextos.append(
            {
                "empresa_id": clave[0],
                "lead_consolidado_id": clave[1],
                "conversaciones_utilizables": [
                    x["extraccion"]["conversacion_id"] for x in es
                ],
                "conversacion_id_contexto": fila["conversacion_id_contexto"],
                "extraccion_contexto": ex,
                "criterio": (
                    "Foto más reciente verificable; no acumular decla"
                    "raciones de otras fechas."
                ),
            }
        )
    actuales = pd.DataFrame(filas)
    X_actual = (
        actuales[PERFILES["comercial"]].fillna("DESCONOCIDO").astype(str)
    )
    actuales["score_prioridad"] = np.round(100 * score_reglas(X_actual), 2)
    actuales["score_modelo_experimental"] = np.round(
        100 * modelo_final.predict_proba(X_actual[columnas_elegidas])[:, 1], 4
    )
    actuales["temperatura"] = np.select(
        [
            actuales.cita_observada.eq("SI"),
            actuales.manifesto_cuota_inicial.eq("SI")
            | actuales.forma_pago_declarada.isin(["credito", "contado"]),
        ],
        ["caliente", "tibio"],
        default="sin_informacion_suficiente",
    )
    actuales["cola"] = np.select(
        [
            actuales.todas_consultas_descartadas,
            actuales.estado_contexto.eq("revision_orden"),
            actuales.temperatura.eq("sin_informacion_suficiente"),
        ],
        [
            "revision_descartado_crm",
            "revision_datos",
            "primer_contacto_o_ampliar_informacion",
        ],
        default="seguimiento_comercial",
    )

    actuales["explicacion_prioridad"] = actuales.apply(explicar_reglas, axis=1)
    actuales["accion_sugerida"] = actuales.cola.map(
        {
            "revision_descartado_crm": "Revisar motivo del descarte en CRM antes de reactivar.",
            "revision_datos": "Revisar orden temporal antes de usar declaraciones.",
            "primer_contacto_o_ampliar_informacion": (
                "Confirmar interés y completar información; no as"
                "umir desinterés."
            ),
            "seguimiento_comercial": (
                "Retomar la conversación y responder a lo solicit"
                "ado por el cliente."
            ),
        }
    )
    actuales.loc[
        actuales.cita_observada.eq("SI")
        & actuales.cola.eq("seguimiento_comercial"),
        "accion_sugerida",
    ] = (
        "Confirmar disponibilidad y estado de la cita sol"
        "icitada; no asumir que sigue pendiente."
    )
    actuales["metodo_prioridad"] = "reglas_evidencia_v1"
    actuales["modelo_experimental"] = elegido
    actuales["modelo_apto_produccion"] = False
    actuales["_fecha_orden"] = pd.to_datetime(
        actuales.fecha_antiguedad, format="mixed", errors="coerce"
    )
    actuales = actuales.sort_values(
        [
            "empresa_id",
            "cola",
            "score_prioridad",
            "_fecha_orden",
            "lead_consolidado_id",
        ],
        ascending=[True, True, False, True, True],
        na_position="last",
    )
    actuales["posicion_en_cola_empresa"] = (
        actuales.groupby(["empresa_id", "cola"]).cumcount() + 1
    )
    actuales = actuales.drop(columns="_fecha_orden")
    if not len(actuales) == len(leads):
        raise ValueError("Contrato incumplido: len(actuales) == len(leads)")
    if (
        not set(
            zip(
                actuales.empresa_id, actuales.lead_consolidado_id, strict=False
            )
        )
        == claves_lead
    ):
        raise ValueError(
            "Contrato incumplido: set(zip(actuales.empresa_id"
            ", actuales.lead_consolidado_id)) == claves_lead"
        )
    if not not actuales.duplicated(
        ["empresa_id", "lead_consolidado_id"]
    ).any():
        raise ValueError(
            "Contrato incumplido: not actuales.duplicated(['e"
            "mpresa_id', 'lead_consolidado_id']).any()"
        )
    if not actuales.score_prioridad.between(0, 100).all():
        raise ValueError(
            "Contrato incumplido: actuales.score_prioridad.be"
            "tween(0, 100).all()"
        )
    if not actuales.score_modelo_experimental.between(0, 100).all():
        raise ValueError(
            "Contrato incumplido: actuales.score_modelo_exper"
            "imental.between(0, 100).all()"
        )
    if not set(actuales.conversacion_id_contexto.dropna()) <= set(conv_por_id):
        raise ValueError(
            "Contrato incumplido: set(actuales.conversacion_i"
            "d_contexto.dropna()) <= set(conv_por_id)"
        )
    if not all(
        (sha(DATA / p) == huella for p, huella in hashes_entrada.items())
    ):
        raise ValueError(
            "Contrato incumplido: all((sha(DATA / p) == huell"
            "a for p, huella in hashes_entrada.items()))"
        )
    for _, g in actuales.groupby(["empresa_id", "cola"]):
        if not g.score_prioridad.is_monotonic_decreasing:
            raise ValueError(
                "Contrato incumplido: g.score_prioridad.is_monoto"
                "nic_decreasing"
            )
        if not g.posicion_en_cola_empresa.tolist() == list(
            range(1, len(g) + 1)
        ):
            raise ValueError(
                "Contrato incumplido: g.posicion_en_cola_empresa."
                "tolist() == list(range(1, len(g) + 1))"
            )
    caso_sin_datos = pd.DataFrame(
        [
            {
                "modelo_sku": "DESCONOCIDO",
                "manifesto_cuota_inicial": "NO_INFORMA",
                "forma_pago_declarada": "no_informa",
                "cita_observada": "NO_OBSERVADA",
            }
        ]
    )
    if not score_reglas(caso_sin_datos)[0] == 0:
        raise ValueError(
            "Contrato incumplido: score_reglas(caso_sin_datos)[0] == 0"
        )
    if not np.isclose(
        score_reglas(caso_sin_datos.assign(cita_observada="SI"))[0], 40 / 90
    ):
        raise ValueError(
            "Contrato incumplido: np.isclose(score_reglas(cas"
            "o_sin_datos.assign(cita_observada='SI'))[0], 40 "
            "/ 90)"
        )
    if (
        not inicial_de_extraccion(
            {
                "dinero": {
                    "cuota_inicial": {
                        "valor": None,
                        "minimo": None,
                        "evidencias": [],
                    }
                }
            }
        )
        == "NO_INFORMA"
    ):
        raise ValueError(
            "Contrato incumplido: inicial_de_extraccion({'din"
            "ero': {'cuota_inicial': {'valor': None, 'minimo'"
            ": None, 'evidencias': []}}}) == 'NO_INFORMA'"
        )
    if (
        not inicial_de_extraccion(
            {
                "dinero": {
                    "cuota_inicial": {
                        "valor": 0,
                        "minimo": None,
                        "evidencias": [{"texto": "No tengo inicial"}],
                    }
                }
            }
        )
        == "NO"
    ):
        raise ValueError(
            "Contrato incumplido: inicial_de_extraccion({'din"
            "ero': {'cuota_inicial': {'valor': 0, 'minimo': N"
            "one, 'evidencias': [{'texto': 'No tengo inicial'"
            "}]}}}) == 'NO'"
        )
    if elegir_ultima(["2026-08-01", "2026-08-01 10:00:00"])[0] is not None:
        raise ValueError(
            "Contrato incumplido: elegir_ultima(['2026-08-01'"
            ", '2026-08-01 10:00:00'])[0] is None"
        )
    if not elegir_ultima(["2026-08-01", "2026-08-02 10:00:00"])[0] == 1:
        raise ValueError(
            "Contrato incumplido: elegir_ultima(['2026-08-01'"
            ", '2026-08-02 10:00:00'])[0] == 1"
        )
    from .archivos import guardar_json, huella

    actuales.to_csv(
        DATA / "priorizacion_leads.csv", index=False, encoding="utf-8"
    )
    guardar_json(DATA / "priorizacion_leads.json", registros(actuales))
    guardar_json(DATA / "contexto_priorizacion.json", contextos)
    guardar_json(
        DATA / "incidencias_modelado.json",
        {"version": VERSION, "incidencias": incidencias},
    )
    joblib.dump(
        {
            "pipeline": modelo_final,
            "columnas": columnas_elegidas,
            "version": VERSION,
            "candidato": elegido,
            "uso": "experimental_no_operativo",
        },
        OUT / "modelo_experimental.joblib",
    )
    ficha = {
        "version": VERSION,
        "semilla": SEED,
        "candidato_elegido": elegido,
        "columnas": columnas_elegidas,
        "C": 1.0,
        "class_weight": None,
        "seleccion": (
            "Configuración fijada por la revisión del noteboo"
            "k 04; no se selecciona usando esta ejecución."
        ),
        "entrenamiento_final": "2026-03-01 a 2026-06-30",
        "historicos_entrenamiento": len(desarrollo),
        "historico_sha256": hashes_entrada["historico_cierres.csv"],
        "paquetes": {
            p: metadata.version(p)
            for p in ["pandas", "numpy", "scikit-learn", "joblib"]
        },
        "modelo_apto_produccion": False,
        "metodo_operativo": "reglas_evidencia_v1",
        "limitaciones": [
            "Datos sintéticos.",
            "No hay validación prospectiva ni calibración.",
            "Sin gestión no es Perdido.",
            (
                "Julio ya fue explorado; no se declara una evalua"
                "ción independiente."
            ),
            (
                "Reajuste fijo con marzo-junio; el flujo no cambi"
                "a automáticamente algoritmo ni pesos."
            ),
        ],
    }
    guardar_json(OUT / "ficha_modelo.json", ficha)
    salidas = [
        "priorizacion_leads.csv",
        "priorizacion_leads.json",
        "contexto_priorizacion.json",
        "incidencias_modelado.json",
    ]
    manifest = {
        "version": VERSION,
        "generador": "04_priorizar.py",
        "leads_priorizados": len(actuales),
        "modelo_apto_produccion": False,
        "metodo_prioridad": "reglas_evidencia_v1",
        "modelo_experimental": elegido,
        "temperaturas": actuales.temperatura.value_counts().to_dict(),
        "hashes_entrada": hashes_entrada,
        "hashes_salida": {p: huella(DATA / p) for p in salidas},
        "modelo_sha256": huella(OUT / "modelo_experimental.joblib"),
    }
    guardar_json(DATA / "manifest_clasificacion.json", manifest)
    return manifest
