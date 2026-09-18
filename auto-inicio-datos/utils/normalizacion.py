"""Normaliza y consolida conservando decisiones y trazabilidad."""

from pathlib import Path

from .reglas_normalizacion import (
    clave_modelo,
    clave_texto,
    escribir_csv,
    evidencia_orden,
    fecha_exportable,
    id_consolidado,
    limpiar_texto,
    nombres_compatibles,
    normalizar_fecha,
    normalizar_telefono,
    secuencia_posible,
    tabla_exportable,
    validar_numero,
    valor_json,
    valores_informados,
)


def ejecutar(root: Path) -> dict:
    """Normaliza y consolida conservando decisiones y trazabilidad.

    Args:
        root: Directorio de trabajo con data y outputs.

    Returns:
        Resumen verificable de la etapa.
    """
    import json

    import pandas as pd

    from .ingestion import ejecutar as ingerir

    raiz_proyecto = root
    ruta_datos = root / "data/raw"
    fuentes = ingerir(root)
    leads, catalogo_motos, asesores, historico_cierres, conversaciones = (
        fuentes[k]
        for k in [
            "leads",
            "catalogo_motos",
            "asesores",
            "historico_cierres",
            "conversaciones",
        ]
    )
    conversaciones_df = pd.DataFrame(conversaciones)
    tablas = {k: v for k, v in fuentes.items() if k != "conversaciones"}
    import re

    datos_normalizados = {
        nombre: tabla.copy(deep=True) for nombre, tabla in tablas.items()
    }
    datos_normalizados["conversaciones"] = conversaciones_df.copy(deep=True)

    for nombre, tabla in datos_normalizados.items():
        for columna in (
            tablas[nombre].columns
            if nombre in tablas
            else conversaciones_df.columns
        ):
            if columna == "mensajes":
                continue
            if pd.api.types.is_object_dtype(
                tabla[columna]
            ) or pd.api.types.is_string_dtype(tabla[columna]):
                tabla[columna + "_normalizado"] = (
                    tabla[columna].map(limpiar_texto).astype("string")
                )
                if columna.endswith("_id") or columna == "sku":
                    tabla[columna + "_normalizado"] = tabla[
                        columna + "_normalizado"
                    ].str.upper()
                elif columna == "email":
                    tabla[columna + "_normalizado"] = tabla[
                        columna + "_normalizado"
                    ].str.lower()
    categorias = {
        "canal": {
            clave_texto(v): v
            for v in ["WhatsApp", "Meta Ads", "Formulario Web"]
        },
        "estado_gestion": {
            clave_texto(v): v
            for v in [
                "Contactado",
                "Cotización enviada",
                "Descartado",
                "En proceso",
                "No contesta",
                "Sin gestión",
            ]
        },
        "activo": {"si": "SI", "no": "NO"},
        "manifesto_cuota_inicial": {
            "si": "SI",
            "no": "NO",
            "no_informa": "NO_INFORMA",
        },
        "pidio_cita": {"si": "SI", "no": "NO"},
        "forma_pago_declarada": {
            "contado": "contado",
            "credito": "credito",
            "no_informa": "no_informa",
        },
        "desenlace": {
            clave_texto(v): v for v in ["Cerrado", "Perdido", "Sin gestión"]
        },
    }
    ciudades = [
        "Barranquilla",
        "Bello",
        "Bogotá",
        "Cartagena",
        "Itagüí",
        "Medellín",
        "Montería",
        "Rionegro",
        "Santa Marta",
        "Soacha",
        "Soledad",
    ]
    categorias["ciudad"] = {clave_texto(v): v for v in ciudades}
    categorias["ciudad"].update(
        {
            "b/quilla": "Barranquilla",
            "bogota dc": "Bogotá",
            "bogota d.c.": "Bogotá",
            "cartagena de indias": "Cartagena",
            "rio negro": "Rionegro",
            "sta marta": "Santa Marta",
        }
    )
    for nombre, tabla in datos_normalizados.items():
        for columna, equivalencias in categorias.items():
            if columna not in tabla:
                continue
            claves = tabla[columna].map(clave_texto)
            tabla[columna + "_normalizado"] = claves.map(equivalencias).astype(
                "string"
            )
            tabla[columna + "_estado"] = claves.map(
                lambda clave, equivalencias=equivalencias: (
                    "faltante"
                    if clave is None
                    else "valido"
                    if clave in equivalencias
                    else "no_reconocido"
                )
            )
            if nombre == "leads":
                pass

    leads_normalizados = datos_normalizados["leads"]
    leads_normalizados[["telefono_normalizado", "telefono_estado"]] = (
        pd.DataFrame(
            leads["telefono"].map(normalizar_telefono).tolist(),
            index=leads.index,
        )
    )

    campos_fecha = {
        "leads": ["fecha_registro", "fecha_primer_contacto"],
        "asesores": ["fecha_ingreso"],
        "historico_cierres": ["fecha_registro"],
        "conversaciones": ["fecha_inicio"],
    }
    for nombre, columnas in campos_fecha.items():
        tabla = datos_normalizados[nombre]
        for campo in columnas:
            nuevas = [
                campo + sufijo
                for sufijo in [
                    "_normalizado",
                    "_estado",
                    "_precision",
                    "_criterio",
                ]
            ]
            tabla[nuevas] = pd.DataFrame(
                tabla[campo].map(normalizar_fecha).tolist(),
                index=tabla.index,
                columns=nuevas,
            )
            tabla[nuevas[0]] = pd.to_datetime(tabla[nuevas[0]])

    tabla = datos_normalizados["leads"]
    campos_lead = ["fecha_registro", "fecha_primer_contacto"]
    tabla["orden_fechas_detectado"] = "DMY_por_defecto"
    tabla["comentario_orden_fechas"] = ""
    for indice, fila in tabla.iterrows():
        evidencias = [evidencia_orden(fila[campo]) for campo in campos_lead]
        mixto = "MDY" in evidencias and "DMY" in evidencias
        if mixto:
            ordenes = evidencias
            regla = "origen_mixto_resuelto_por_valores"
            motivo = (
                "El mismo lead combina día-mes y mes-día. Cada va"
                "lor >12 identifica el día de su campo. Se corrig"
                "en ambos a año-mes-día sin convertir un día ineq"
                "uívoco en mes."
            )
        elif "MDY" in evidencias:
            ordenes = ["MDY", "MDY"]
            regla = "MDY_por_evidencia_del_lead"
            motivo = (
                "Un campo del lead tiene un valor central mayor q"
                "ue 12: es el día. Se interpreta mes-día en todas"
                " sus fechas con año al final, incluidas las numé"
                "ricamente ambiguas. Las ISO no cambian."
            )
        else:
            ordenes = ["DMY", "DMY"]
            regla = (
                "DMY_por_evidencia_del_lead"
                if "DMY" in evidencias
                else "DMY_por_defecto"
            )
            motivo = (
                "Día-mes-año para fechas con año al final; ISO si"
                "n cambios. No hay evidencia de un día en la posi"
                "ción central."
            )
        resultados = [
            normalizar_fecha(fila[campo], orden)
            for campo, orden in zip(campos_lead, ordenes, strict=False)
        ]
        if not any(evidencias) and secuencia_posible(resultados) is False:
            alternativa = [
                normalizar_fecha(fila[campo], "MDY") for campo in campos_lead
            ]
            if secuencia_posible(alternativa) is True:
                resultados = alternativa
                regla = "MDY_por_coherencia_del_lead"
                motivo = (
                    "Sin valores >12 que fijen el orden, día-mes sitú"
                    "a el contacto antes del registro. La inversión c"
                    "onjunta de las fechas con año al final del mismo"
                    " lead restaura la secuencia; ISO sin cambios. In"
                    "ferencia documentada."
                )
        if secuencia_posible(resultados) is False:
            opciones = []
            for campo, _evidencia, actual in zip(
                campos_lead, evidencias, resultados, strict=False
            ):
                texto = str(fila[campo]).strip()
                m = re.match(
                    "^(\\d{1,2})[-/](\\d{1,2})[-/]\\d{4}(?:\\D|$)", texto
                )
                ambiguo = bool(
                    m and all(1 <= int(v) <= 12 for v in m.groups())
                )
                opciones.append(
                    [
                        normalizar_fecha(fila[campo], orden)
                        for orden in ["DMY", "MDY"]
                    ]
                    if ambiguo
                    else [actual]
                )
            pares = {}
            for registro in opciones[0]:
                for contacto in opciones[1]:
                    if secuencia_posible([registro, contacto]) is True:
                        pares[registro[0], contacto[0]] = [registro, contacto]
            if len(pares) == 1:
                resultados = next(iter(pares.values()))
                regla = "origen_mixto_por_coherencia_unica"
                motivo = (
                    "La fuente mezcla órdenes dentro del lead. Manten"
                    "iendo ISO y los días inequívocos (>12), una sola"
                    " combinación de sus campos ambiguos sitúa el reg"
                    "istro antes del contacto. Se usa esa combinación"
                    " y se documenta la inferencia; salida ISO en amb"
                    "os campos."
                )
        tabla.at[indice, "orden_fechas_detectado"] = regla
        tabla.at[indice, "comentario_orden_fechas"] = motivo
        for campo, resultado in zip(campos_lead, resultados, strict=False):
            fecha, estado, precision, comentario = resultado
            tabla.at[indice, campo + "_normalizado"] = fecha
            tabla.at[indice, campo + "_estado"] = estado
            tabla.at[indice, campo + "_precision"] = precision
            tabla.at[indice, campo + "_criterio"] = comentario + " " + motivo
    revision_fechas = []
    for nombre, columnas in campos_fecha.items():
        tabla = datos_normalizados[nombre]
        identificador = (
            "conversacion_id"
            if nombre == "conversaciones"
            else "asesor_id"
            if nombre == "asesores"
            else "lead_id"
        )
        for campo in columnas:
            for indice, fila in tabla.loc[
                tabla[campo + "_estado"].eq("invalida")
            ].iterrows():
                revision_fechas.append(
                    {
                        "tabla": nombre,
                        "id": fila[identificador],
                        "campo": campo,
                        "fila_dataframe": indice,
                        "original": fila[campo],
                        "estado": "invalida",
                        "normalizado": pd.NaT,
                        "criterio": fila[campo + "_criterio"],
                    }
                )
    tabla = datos_normalizados["leads"]
    tabla["secuencia_fechas_estado"] = "no_evaluable"
    tabla["secuencia_fechas_comentario"] = (
        "Falta al menos una fecha válida para comparar registro y contacto."
    )
    for indice, fila in tabla.iterrows():
        resultados = [
            (
                fila[campo + "_normalizado"],
                fila[campo + "_estado"],
                fila[campo + "_precision"],
            )
            for campo in campos_lead
        ]
        coherente = secuencia_posible(resultados)
        if coherente is None:
            continue
        tabla.at[indice, "secuencia_fechas_estado"] = (
            "coherente" if coherente else "contacto_anterior_registro"
        )
        comentario = (
            (
                "Registro y primer contacto mantienen orden crono"
                "lógico con la precisión disponible."
            )
            if coherente
            else f"El contacto ({resultados[1][0]}) sigue siendo anterior al registro ({resultados[0][0]}) tras aplicar la regla por lead. Las fechas son válidas, pero su relación requiere revisión; no se inventa una fecha."
        )
        tabla.at[indice, "secuencia_fechas_comentario"] = comentario
        if not coherente:
            revision_fechas.append(
                {
                    "tabla": "leads",
                    "id": fila["lead_id"],
                    "campo": "fecha_primer_contacto",
                    "fila_dataframe": indice,
                    "original": fila["fecha_primer_contacto"],
                    "estado": "secuencia_inconsistente",
                    "normalizado": resultados[1][0],
                    "criterio": comentario,
                }
            )
    fechas_por_revisar = pd.DataFrame(
        revision_fechas,
        columns=[
            "tabla",
            "id",
            "campo",
            "fila_dataframe",
            "original",
            "estado",
            "normalizado",
            "criterio",
        ],
    )
    fechas_por_revisar.loc[fechas_por_revisar["estado"].eq("invalida")].copy()
    fechas_por_revisar.loc[
        fechas_por_revisar["estado"].eq("secuencia_inconsistente")
    ].copy()
    with pd.option_context(
        "display.max_rows",
        None,
        "display.max_columns",
        None,
        "display.max_colwidth",
        None,
    ):
        pass

    referencias = []
    for _, moto in catalogo_motos.iterrows():
        nombre = f"{moto['marca']} {moto['linea']}"
        referencias.append(
            {
                "sku": moto["sku"],
                "nombre": nombre,
                "marca": clave_modelo(moto["marca"]),
                "completo": clave_modelo(nombre),
                "linea": clave_modelo(moto["linea"]),
            }
        )

    def emparejar_modelo(valor):
        """Emparejar modelo."""
        clave = clave_modelo(valor)
        if clave is None:
            return (pd.NA, pd.NA, "faltante", pd.NA)
        candidatos = [
            r for r in referencias if clave in [r["completo"], r["linea"]]
        ]
        estado = "coincidencia_exacta"
        if not candidatos:
            candidatos = [
                r
                for r in referencias
                if r["completo"].startswith(clave + " ")
                or r["linea"].startswith(clave + " ")
            ]
            estado = "abreviatura_unica"
        opciones = "; ".join(r["nombre"] for r in candidatos) or pd.NA
        if len(candidatos) == 1 and clave != candidatos[0]["marca"]:
            return (
                candidatos[0]["nombre"],
                candidatos[0]["sku"],
                estado,
                opciones,
            )
        return (
            pd.NA,
            pd.NA,
            "ambiguo" if candidatos else "sin_coincidencia",
            opciones,
        )

    for nombre, campo in [
        ("leads", "modelo_interes_texto"),
        ("historico_cierres", "modelo_cotizado"),
    ]:
        tabla = datos_normalizados[nombre]
        columnas = [
            campo + "_normalizado",
            "modelo_sku",
            "modelo_estado",
            "modelo_candidatos",
        ]
        tabla[columnas] = pd.DataFrame(
            tabla[campo].map(emparejar_modelo).tolist(), index=tabla.index
        )
    reglas_numericas = {
        "catalogo_motos": {
            "precio_lista": (False, False),
            "cilindraje": (True, False),
            "unidades_disponibles": (True, True),
        },
        "asesores": {"capacidad_diaria_leads": (True, False)},
        "historico_cierres": {
            "precio_lista": (False, False),
            "horas_al_primer_contacto": (False, True),
            "numero_contactos": (True, True),
        },
    }

    revision_numerica = []
    for nombre, reglas in reglas_numericas.items():
        tabla = datos_normalizados[nombre]
        identificador = {
            "catalogo_motos": "sku",
            "asesores": "asesor_id",
            "historico_cierres": "lead_id",
        }[nombre]
        for campo, (entero, permite_cero) in reglas.items():
            resultado = tabla[campo].map(
                lambda v, entero=entero, permite_cero=permite_cero: (
                    validar_numero(v, entero, permite_cero)
                )
            )
            tabla[campo + "_normalizado"] = pd.Series(
                [v[0] for v in resultado],
                index=tabla.index,
                dtype="Int64" if entero else "Float64",
            )
            tabla[campo + "_estado"] = [v[1] for v in resultado]
            for indice in tabla.index[tabla[campo + "_estado"] != "valido"]:
                revision_numerica.append(
                    {
                        "tabla": nombre,
                        "fila_dataframe": indice,
                        "id": tabla.at[indice, identificador],
                        "campo": campo,
                        "original": tabla.at[indice, campo],
                        "estado": tabla.at[indice, campo + "_estado"],
                    }
                )
    numeros_por_revisar = pd.DataFrame(
        revision_numerica,
        columns=[
            "tabla",
            "fila_dataframe",
            "id",
            "campo",
            "original",
            "estado",
        ],
    )
    numeros_por_revisar.loc[numeros_por_revisar["estado"] != "faltante"]
    numeros_por_revisar.loc[numeros_por_revisar["estado"] == "faltante"]
    with pd.option_context("display.max_rows", None):
        pass
    with pd.option_context("display.max_rows", None):
        pass
    conteos_validacion = []
    for nombre, tabla in datos_normalizados.items():
        for campo in [c for c in tabla.columns if c.endswith("_estado")]:
            for estado, cantidad in (
                tabla[campo].value_counts(dropna=False).items()
            ):
                conteos_validacion.append(
                    {
                        "tabla": nombre,
                        "validacion": campo,
                        "estado": estado,
                        "registros": cantidad,
                    }
                )
    revision_duplicados = datos_normalizados["leads"].copy(deep=True)
    revision_duplicados["fila_dataframe"] = revision_duplicados.index
    revision_duplicados["fila_original_repetida"] = leads.duplicated(
        keep=False
    )
    revision_duplicados["nombre_clave_comparacion"] = revision_duplicados[
        "nombre_cliente"
    ].map(clave_texto)
    claves_duplicados = ["empresa_id_normalizado", "telefono_normalizado"]
    elegibles = (
        revision_duplicados["telefono_estado"].eq("valido")
        & revision_duplicados["empresa_id_normalizado"].notna()
        & revision_duplicados["telefono_normalizado"].notna()
    )
    base_duplicados = revision_duplicados.loc[elegibles].copy()
    candidatos_duplicados = base_duplicados.loc[
        base_duplicados.duplicated(subset=claves_duplicados, keep=False)
    ].copy()
    candidatos_duplicados = candidatos_duplicados.sort_values(
        claves_duplicados + ["fila_dataframe"]
    )
    candidatos_duplicados["grupo_duplicado"] = (
        candidatos_duplicados.groupby(claves_duplicados, sort=True).ngroup()
        + 1
    ).map(lambda numero: f"DUP-{numero:03d}")
    resumen_grupos = []
    for grupo_id, grupo in candidatos_duplicados.groupby(
        "grupo_duplicado", sort=True
    ):
        nombres = grupo["nombre_clave_comparacion"].nunique(dropna=True)
        correos = grupo["email_normalizado"].nunique(dropna=True)
        nombres_faltantes = int(grupo["nombre_clave_comparacion"].isna().sum())
        correos_faltantes = int(grupo["email_normalizado"].isna().sum())
        filas_distintas = len(grupo[list(leads.columns)].drop_duplicates())
        resumen_grupos.append(
            {
                "grupo": grupo_id,
                "empresa": grupo["empresa_id_normalizado"].iloc[0],
                "telefono": grupo["telefono_normalizado"].iloc[0],
                "filas": len(grupo),
                "ids_distintos": grupo["lead_id"].nunique(),
                "filas_originales_distintas": filas_distintas,
                "filas_en_repeticiones_exactas": int(
                    grupo["fila_original_repetida"].sum()
                ),
                "nombres_distintos": nombres,
                "nombres_faltantes": nombres_faltantes,
                "correos_distintos": correos,
                "correos_faltantes": correos_faltantes,
                "canales_distintos": grupo["canal_normalizado"].nunique(
                    dropna=True
                ),
                "lectura_inicial": "Todas las filas son idénticas"
                if filas_distintas == 1
                else "Revisar diferencias de nombre o correo"
                if nombres > 1 or correos > 1
                else (
                    "Datos de identidad compatibles; revisar consulta"
                    "s y faltantes"
                ),
            }
        )
    pd.DataFrame(
        resumen_grupos,
        columns=[
            "grupo",
            "empresa",
            "telefono",
            "filas",
            "ids_distintos",
            "filas_originales_distintas",
            "filas_en_repeticiones_exactas",
            "nombres_distintos",
            "nombres_faltantes",
            "correos_distintos",
            "correos_faltantes",
            "canales_distintos",
            "lectura_inicial",
        ],
    )
    with pd.option_context(
        "display.max_rows", None, "display.max_columns", None
    ):
        pass
    with pd.option_context(
        "display.max_rows",
        None,
        "display.max_columns",
        None,
        "display.max_colwidth",
        80,
    ):
        pass
    grupo_a_revisar = "DUP-001"
    candidatos_duplicados.loc[
        candidatos_duplicados["grupo_duplicado"] == grupo_a_revisar
    ]
    with pd.option_context(
        "display.max_columns", None, "display.max_colwidth", None
    ):
        pass
    claves_por_tabla = {
        "leads": "lead_id_normalizado",
        "asesores": "asesor_id_normalizado",
        "catalogo_motos": "sku_normalizado",
        "historico_cierres": "lead_id_normalizado",
        "conversaciones": "conversacion_id_normalizado",
    }
    revision_ids = []
    ids_repetidos = {}
    for nombre, clave in claves_por_tabla.items():
        origen = datos_normalizados[nombre]
        repetidos = origen[clave].notna() & origen[clave].duplicated(
            keep=False
        )
        ids_repetidos[nombre] = origen.loc[repetidos].copy()
        revision_ids.append(
            {
                "tabla": nombre,
                "clave": clave,
                "ids_faltantes": int(origen[clave].isna().sum()),
                "ids_repetidos_distintos": origen.loc[
                    repetidos, clave
                ].nunique(),
                "filas_con_id_repetido": int(repetidos.sum()),
            }
        )
    leads_relaciones = datos_normalizados["leads"]
    conversaciones_relaciones = datos_normalizados["conversaciones"]
    referencia_leads = (
        leads_relaciones.loc[leads_relaciones["lead_id_normalizado"].notna()]
        .groupby("lead_id_normalizado", as_index=False)
        .agg(
            filas_lead=("lead_id_normalizado", "size"),
            empresas_distintas=("empresa_id_normalizado", "nunique"),
            empresas_faltantes=(
                "empresa_id_normalizado",
                lambda s: int(s.isna().sum()),
            ),
            empresa_identificada=(
                "empresa_id_normalizado",
                lambda s: (
                    s.dropna().iloc[0]
                    if s.nunique() == 1 and s.notna().all()
                    else pd.NA
                ),
            ),
        )
    )
    revision_conversaciones = conversaciones_relaciones[
        [
            "conversacion_id_normalizado",
            "lead_id_normalizado",
            "fecha_inicio_normalizado",
        ]
    ].merge(
        referencia_leads,
        on="lead_id_normalizado",
        how="left",
        validate="many_to_one",
        indicator=True,
    )
    revision_conversaciones["estado_relacion"] = "lead_unico"
    revision_conversaciones.loc[
        revision_conversaciones["filas_lead"].gt(1), "estado_relacion"
    ] = "id_lead_repetido"
    revision_conversaciones.loc[
        revision_conversaciones["_merge"].eq("both")
        & revision_conversaciones["empresa_identificada"].isna(),
        "estado_relacion",
    ] = "empresa_no_determinable"
    revision_conversaciones.loc[
        revision_conversaciones["_merge"].eq("left_only"), "estado_relacion"
    ] = "sin_lead"
    revision_conversaciones.loc[
        revision_conversaciones["estado_relacion"].eq("sin_lead")
    ].copy()
    with pd.option_context(
        "display.max_rows", None, "display.max_columns", None
    ):
        pass
    asesores_relaciones = datos_normalizados["asesores"]
    claves_punto = ["empresa_id_normalizado", "punto_venta_id_normalizado"]
    pares_puntos = asesores_relaciones[claves_punto].dropna().drop_duplicates()
    revision_puntos = leads_relaciones[
        ["lead_id_normalizado"] + claves_punto
    ].copy()
    revision_puntos.insert(0, "fila_dataframe", leads_relaciones.index)
    revision_puntos = revision_puntos.merge(
        pares_puntos,
        on=claves_punto,
        how="left",
        validate="many_to_one",
        indicator=True,
    )
    leads_punto_inconsistente = revision_puntos.loc[
        revision_puntos["_merge"].eq("left_only")
    ].copy()
    empresas_por_punto = pares_puntos.groupby("punto_venta_id_normalizado")[
        "empresa_id_normalizado"
    ].nunique()
    empresas_por_punto.loc[empresas_por_punto.gt(1)]
    if (
        asesores_relaciones["asesor_id_normalizado"].isna().any()
        or asesores_relaciones["asesor_id_normalizado"].duplicated().any()
    ):
        raise ValueError(
            "Revisar IDs de asesores antes de calcular cobertura y capacidad."
        )
    cobertura_filas = []
    for (empresa, punto), grupo in asesores_relaciones.groupby(
        claves_punto, dropna=False
    ):
        activos = grupo.loc[grupo["activo_normalizado"].eq("SI")]
        capacidad_valida = (
            activos["capacidad_diaria_leads_estado"].eq("valido").all()
        )
        cobertura_filas.append(
            {
                "empresa": empresa,
                "punto": punto,
                "asesores": len(grupo),
                "activos": len(activos),
                "estado_activo_desconocido": int(
                    grupo["activo_normalizado"].isna().sum()
                ),
                "capacidad_teorica_activos": activos[
                    "capacidad_diaria_leads_normalizado"
                ].sum()
                if capacidad_valida
                else pd.NA,
            }
        )
    pd.DataFrame(cobertura_filas)
    catalogo_relaciones = datos_normalizados["catalogo_motos"]
    if (
        catalogo_relaciones["sku_normalizado"].isna().any()
        or catalogo_relaciones["sku_normalizado"].duplicated().any()
    ):
        raise ValueError("Revisar SKUs antes de comprobar disponibilidad.")
    disponibilidad_catalogo = catalogo_relaciones[
        ["sku_normalizado", "puntos_venta_disponibles_normalizado"]
    ].copy()
    disponibilidad_catalogo["punto"] = disponibilidad_catalogo[
        "puntos_venta_disponibles_normalizado"
    ].str.split("|", regex=False)
    disponibilidad_catalogo = disponibilidad_catalogo.explode("punto")
    disponibilidad_catalogo["punto"] = (
        disponibilidad_catalogo["punto"]
        .astype("string")
        .str.strip()
        .str.upper()
    )
    disponibilidad_catalogo.loc[
        ~disponibilidad_catalogo["punto"].isin(
            pares_puntos["punto_venta_id_normalizado"]
        )
    ].copy()
    pares_disponibilidad = set(
        disponibilidad_catalogo[["sku_normalizado", "punto"]]
        .dropna()
        .itertuples(index=False, name=None)
    )
    pares_empresa_punto = set(pares_puntos.itertuples(index=False, name=None))
    skus_conocidos = set(catalogo_relaciones["sku_normalizado"].dropna())
    revision_disponibilidad = leads_relaciones[
        [
            "lead_id_normalizado",
            "empresa_id_normalizado",
            "punto_venta_id_normalizado",
            "modelo_interes_texto",
            "modelo_interes_texto_normalizado",
            "modelo_sku",
            "modelo_estado",
        ]
    ].copy()
    revision_disponibilidad.insert(0, "fila_dataframe", leads_relaciones.index)

    def comprobar_disponibilidad(fila):
        """Comprobar disponibilidad."""
        if pd.isna(fila["modelo_sku"]):
            return "no_evaluable_modelo_pendiente"
        if fila["modelo_sku"] not in skus_conocidos:
            return "no_evaluable_sku_desconocido"
        empresa, punto = (
            fila["empresa_id_normalizado"],
            fila["punto_venta_id_normalizado"],
        )
        if (
            pd.isna(empresa)
            or pd.isna(punto)
            or (empresa, punto) not in pares_empresa_punto
        ):
            return "no_evaluable_empresa_punto"
        return (
            "listado_en_punto"
            if (fila["modelo_sku"], punto) in pares_disponibilidad
            else "no_listado_en_punto"
        )

    revision_disponibilidad["disponibilidad"] = revision_disponibilidad.apply(
        comprobar_disponibilidad, axis=1
    )
    leads_modelo_no_disponible = revision_disponibilidad.loc[
        revision_disponibilidad["disponibilidad"].eq("no_listado_en_punto")
    ].copy()
    with pd.option_context("display.max_columns", None):
        pass
    grupos_fila_exacta = leads.groupby(
        list(leads.columns), dropna=False, sort=False
    ).ngroup()
    primera_fila_por_grupo = (
        pd.Series(leads.index, index=leads.index)
        .groupby(grupos_fila_exacta)
        .first()
    )
    filas_conservadas = grupos_fila_exacta.map(primera_fila_por_grupo)
    trazabilidad_filas = pd.DataFrame(
        {
            "fila_origen": leads.index,
            "lead_id_origen": leads["lead_id"],
            "empresa_origen": leads["empresa_id"],
            "fila_conservada": filas_conservadas,
        }
    )
    trazabilidad_filas["accion"] = "conservar"
    trazabilidad_filas.loc[
        trazabilidad_filas["fila_origen"].ne(
            trazabilidad_filas["fila_conservada"]
        ),
        "accion",
    ] = "repeticion_exacta"
    mascara_conservar = ~leads.duplicated(keep="first")
    leads_sin_repeticiones_exactas = (
        datos_normalizados["leads"].loc[mascara_conservar].copy(deep=True)
    )
    leads_sin_repeticiones_exactas.insert(
        0, "fila_origen", leads_sin_repeticiones_exactas.index
    )
    leads.duplicated(keep=False)
    base_propuestas = leads_sin_repeticiones_exactas.loc[
        leads_sin_repeticiones_exactas["telefono_estado"].eq("valido")
        & leads_sin_repeticiones_exactas["empresa_id_normalizado"].notna()
    ].copy()
    base_propuestas["nombre_clave_comparacion"] = base_propuestas[
        "nombre_cliente"
    ].map(clave_texto)
    claves_cliente = ["empresa_id_normalizado", "telefono_normalizado"]
    consultas_candidatas = base_propuestas.loc[
        base_propuestas.duplicated(claves_cliente, keep=False)
    ].copy()
    consultas_candidatas = consultas_candidatas.sort_values(
        claves_cliente + ["fila_origen"]
    )
    consultas_candidatas["grupo_propuesto"] = (
        consultas_candidatas.groupby(claves_cliente, sort=True).ngroup() + 1
    ).map(lambda numero: f"CLI-PROP-{numero:03d}")
    propuestas = []
    for codigo, grupo in consultas_candidatas.groupby(
        "grupo_propuesto", sort=True
    ):
        nombres = grupo["nombre_clave_comparacion"].nunique(dropna=True)
        correos = grupo["email_normalizado"].nunique(dropna=True)
        nombres_faltantes = grupo["nombre_clave_comparacion"].isna().any()
        nombre_completo = (
            grupo["nombre_clave_comparacion"]
            .map(
                lambda v: (
                    isinstance(v, str)
                    and len(v.split()) >= 2
                    and all(len(parte.strip(".")) > 1 for parte in v.split())
                )
            )
            .all()
        )
        identidad_compatible = (
            nombres == 1
            and (not nombres_faltantes)
            and nombre_completo
            and (correos <= 1)
        )
        motivos = []
        if nombres > 1:
            motivos.append("nombres diferentes; pueden incluir abreviaturas")
        if nombres_faltantes:
            motivos.append("nombre faltante")
        if not nombre_completo:
            motivos.append("nombre incompleto o con iniciales")
        if correos > 1:
            motivos.append("correos diferentes")
        if grupo["email_normalizado"].isna().any():
            motivos.append("correo faltante en alguna consulta")
        if identidad_compatible:
            motivos.insert(
                0,
                (
                    "mismo nombre completo normalizado y sin correos "
                    "contradictorios"
                ),
            )
        propuestas.append(
            {
                "grupo": codigo,
                "empresa": grupo["empresa_id_normalizado"].iloc[0],
                "telefono": grupo["telefono_normalizado"].iloc[0],
                "consultas": len(grupo),
                "lead_ids": ", ".join(grupo["lead_id"].astype(str)),
                "nombres_originales": " | ".join(
                    grupo["nombre_cliente"].dropna().astype(str).unique()
                ),
                "correos_normalizados": " | ".join(
                    grupo["email_normalizado"].dropna().unique()
                ),
                "propuesta": "agrupar_cliente_conservar_consultas"
                if identidad_compatible
                else "revision_manual_identidad",
                "motivo": "; ".join(motivos)
                or "revisar evidencia de identidad",
                "consultas_con_fecha_pendiente": int(
                    grupo["fecha_registro_estado"]
                    .isin(["ambigua", "invalida", "faltante"])
                    .sum()
                ),
                "consultas_con_modelo_pendiente": int(
                    (
                        ~grupo["modelo_estado"].isin(
                            ["coincidencia_exacta", "abreviatura_unica"]
                        )
                    ).sum()
                ),
            }
        )
    pd.DataFrame(propuestas)
    with pd.option_context(
        "display.max_rows",
        None,
        "display.max_columns",
        None,
        "display.max_colwidth",
        100,
    ):
        pass
    referencia_consolidada = leads_sin_repeticiones_exactas[
        ["lead_id_normalizado", "empresa_id_normalizado", "fila_origen"]
    ].copy()
    if (
        referencia_consolidada["lead_id_normalizado"].isna().any()
        or referencia_consolidada["lead_id_normalizado"].duplicated().any()
    ):
        raise ValueError(
            "Quedan IDs de lead faltantes o repetidos; revisa"
            "r antes de unir conversaciones."
        )
    if referencia_consolidada["empresa_id_normalizado"].isna().any():
        raise ValueError(
            "Hay leads sin empresa; revisar antes de asignar "
            "pertenencia a conversaciones."
        )
    datos_normalizados["conversaciones"][
        [
            "conversacion_id_normalizado",
            "lead_id_normalizado",
            "fecha_inicio_normalizado",
        ]
    ].merge(
        referencia_consolidada,
        on="lead_id_normalizado",
        how="left",
        validate="many_to_one",
        indicator=True,
    )
    import hashlib
    from itertools import combinations

    consultas_resueltas = leads_sin_repeticiones_exactas.copy(deep=True)
    consultas_resueltas["lead_consolidado_id"] = [
        id_consolidado(
            str(fila["empresa_id_normalizado"]),
            "consulta:" + str(fila["lead_id_normalizado"]),
        )
        for _, fila in consultas_resueltas.iterrows()
    ]
    consultas_resueltas["regla_identidad"] = "consulta_individual"
    decisiones_identidad = []
    for codigo, grupo in consultas_candidatas.groupby(
        "grupo_propuesto", sort=True
    ):
        compatibles = all(
            (
                nombres_compatibles(a, b)
                for a, b in combinations(grupo["nombre_cliente"].tolist(), 2)
            )
        )
        empresa = grupo["empresa_id_normalizado"].iloc[0]
        telefono = grupo["telefono_normalizado"].iloc[0]
        if compatibles:
            identificador = id_consolidado(
                str(empresa), "telefono:" + telefono
            )
            consultas_resueltas.loc[grupo.index, "lead_consolidado_id"] = (
                identificador
            )
            consultas_resueltas.loc[grupo.index, "regla_identidad"] = (
                "empresa_telefono_nombre_compatible"
            )
        decisiones_identidad.append(
            {
                "grupo": codigo,
                "empresa": empresa,
                "telefono": telefono,
                "lead_ids": grupo["lead_id_normalizado"].tolist(),
                "consultas": len(grupo),
                "decision": "agrupado"
                if compatibles
                else "separado_por_identidad_incierta",
                "correos_distintos": grupo["email_normalizado"].nunique(
                    dropna=True
                ),
                "nombres_originales": grupo["nombre_cliente"].tolist(),
            }
        )
    decisiones_identidad = pd.DataFrame(decisiones_identidad)
    with pd.option_context(
        "display.max_rows", None, "display.max_colwidth", 100
    ):
        pass

    filas_consolidadas = []
    for identificador, grupo in consultas_resueltas.groupby(
        "lead_consolidado_id", sort=True
    ):
        nombres = valores_informados(grupo["nombre_cliente_normalizado"])
        nombre_presentacion = (
            max(
                nombres,
                key=lambda v: (
                    sum(len(t.strip(".")) > 1 for t in v.split()),
                    len(v),
                ),
            )
            if nombres
            else pd.NA
        )
        filas_consolidadas.append(
            {
                "lead_consolidado_id": identificador,
                "empresa_id": grupo["empresa_id_normalizado"].iloc[0],
                "nombre_presentacion": nombre_presentacion,
                "nombres_declarados": nombres,
                "telefonos": valores_informados(grupo["telefono_normalizado"]),
                "telefono_utilizable": bool(
                    grupo["telefono_estado"].eq("valido").all()
                ),
                "correos": valores_informados(grupo["email_normalizado"]),
                "varios_correos": grupo["email_normalizado"].nunique(
                    dropna=True
                )
                > 1,
                "ciudades": valores_informados(grupo["ciudad_normalizado"]),
                "canales": valores_informados(grupo["canal_normalizado"]),
                "puntos_venta": valores_informados(
                    grupo["punto_venta_id_normalizado"]
                ),
                "modelos_identificados": valores_informados(
                    grupo["modelo_interes_texto_normalizado"]
                ),
                "modelos_declarados": valores_informados(
                    grupo["modelo_interes_texto"]
                ),
                "consultas_con_modelo_pendiente": int(
                    (
                        ~grupo["modelo_estado"].isin(
                            ["coincidencia_exacta", "abreviatura_unica"]
                        )
                    ).sum()
                ),
                "primera_fecha_registro_resuelta": grupo[
                    "fecha_registro_normalizado"
                ].min(),
                "ultima_fecha_registro_resuelta": grupo[
                    "fecha_registro_normalizado"
                ].max(),
                "consultas_con_fecha_registro_pendiente": int(
                    grupo["fecha_registro_normalizado"].isna().sum()
                ),
                "lead_ids_origen": grupo["lead_id_normalizado"].tolist(),
                "numero_consultas": len(grupo),
                "reglas_identidad": valores_informados(
                    grupo["regla_identidad"]
                ),
            }
        )
    leads_consolidados = pd.DataFrame(filas_consolidadas)
    mapa_origen_consolidado = trazabilidad_filas.merge(
        consultas_resueltas[
            ["fila_origen", "lead_consolidado_id", "regla_identidad"]
        ].rename(columns={"fila_origen": "fila_conservada"}),
        on="fila_conservada",
        how="left",
        validate="many_to_one",
    )
    referencia_identidad = consultas_resueltas[
        [
            "lead_id_normalizado",
            "empresa_id_normalizado",
            "lead_consolidado_id",
        ]
    ]
    conversaciones_resueltas = datos_normalizados["conversaciones"].merge(
        referencia_identidad,
        on="lead_id_normalizado",
        how="left",
        validate="many_to_one",
        indicator=True,
    )
    leads_consolidados.loc[leads_consolidados["canales"].map(len).gt(1)]
    with pd.option_context("display.max_columns", None):
        pass
    filas_excepciones = []
    campos_originales = {
        "leads": list(leads.columns),
        "asesores": list(asesores.columns),
        "catalogo_motos": list(catalogo_motos.columns),
        "historico_cierres": list(historico_cierres.columns),
        "conversaciones": list(conversaciones_df.columns),
    }
    estados_resueltos = {
        "valido",
        "valida",
        "resuelta_por_contexto",
        "coincidencia_exacta",
        "abreviatura_unica",
    }
    for nombre, tabla in datos_normalizados.items():
        columna_id = {
            "leads": "lead_id",
            "historico_cierres": "lead_id",
            "asesores": "asesor_id",
            "catalogo_motos": "sku",
            "conversaciones": "conversacion_id",
        }[nombre]
        for columna in [c for c in tabla.columns if c.endswith("_estado")]:
            campo = columna[: -len("_estado")]
            if campo == "modelo":
                campo = (
                    "modelo_interes_texto"
                    if nombre == "leads"
                    else "modelo_cotizado"
                )
            if campo not in campos_originales[nombre]:
                continue
            for indice, fila in tabla.loc[
                ~tabla[columna].isin(estados_resueltos)
            ].iterrows():
                filas_excepciones.append(
                    {
                        "tabla": nombre,
                        "fila_origen": indice,
                        "id": fila[columna_id],
                        "campo": campo,
                        "valor_original": fila[campo],
                        "estado": fila[columna],
                        "comentario": fila.get(
                            campo + "_criterio",
                            "Revisar el estado indicado y el valor original.",
                        ),
                    }
                )
    pd.DataFrame(filas_excepciones)
    with pd.option_context("display.max_rows", None):
        pass
    decisiones_identidad.loc[decisiones_identidad["decision"].ne("agrupado")]
    if not len(mapa_origen_consolidado) == len(leads):
        raise ValueError("Se perdió trazabilidad de filas.")
    if not mapa_origen_consolidado["lead_consolidado_id"].notna().all():
        raise ValueError(
            "Contrato incumplido: mapa_origen_consolidado['le"
            "ad_consolidado_id'].notna().all()"
        )
    if not leads_consolidados["lead_consolidado_id"].is_unique:
        raise ValueError(
            "Contrato incumplido: leads_consolidados['lead_co"
            "nsolidado_id'].is_unique"
        )
    if (
        not consultas_resueltas.groupby("lead_consolidado_id")[
            "empresa_id_normalizado"
        ]
        .nunique()
        .eq(1)
        .all()
    ):
        raise ValueError("Se mezclaron empresas.")
    if not set(consultas_resueltas["lead_id_normalizado"]) == set(
        datos_normalizados["leads"]["lead_id_normalizado"]
    ):
        raise ValueError(
            "Contrato incumplido: set(consultas_resueltas['le"
            "ad_id_normalizado']) == set(datos_normalizados['"
            "leads']['lead_id_normalizado'])"
        )
    if not leads_consolidados["numero_consultas"].sum() == len(
        consultas_resueltas
    ):
        raise ValueError(
            "Contrato incumplido: leads_consolidados['numero_"
            "consultas'].sum() == len(consultas_resueltas)"
        )
    if not len(conversaciones_resueltas) == len(conversaciones):
        raise ValueError(
            "Contrato incumplido: len(conversaciones_resuelta"
            "s) == len(conversaciones)"
        )
    if (
        not conversaciones_resueltas.loc[
            conversaciones_resueltas["_merge"].eq("left_only"),
            "lead_consolidado_id",
        ]
        .isna()
        .all()
    ):
        raise ValueError(
            "Contrato incumplido: conversaciones_resueltas.lo"
            "c[conversaciones_resueltas['_merge'].eq('left_on"
            "ly'), 'lead_consolidado_id'].isna().all()"
        )
    ids_con_conversacion = set(
        datos_normalizados["conversaciones"]["lead_id_normalizado"].dropna()
    )
    marcadores_prueba = {"prueba", "prueba prueba", "test", "test test"}
    revision_telefonos_invalidos = []
    for indice, fila in consultas_resueltas.loc[
        consultas_resueltas["telefono_estado"].ne("valido")
    ].iterrows():
        utiles = []
        nombre = clave_texto(fila["nombre_cliente"])
        if nombre and nombre not in marcadores_prueba:
            utiles.append("nombre distinto de un marcador de prueba")
        for campo in [
            "email_normalizado",
            "modelo_interes_texto",
            "ciudad_normalizado",
            "canal_normalizado",
            "campania_normalizado",
        ]:
            if pd.notna(limpiar_texto(fila[campo])):
                utiles.append(campo)
        if pd.notna(fila["fecha_registro_normalizado"]):
            utiles.append("fecha de registro válida")
        if pd.notna(fila["fecha_primer_contacto_normalizado"]):
            utiles.append("primer contacto válido")
        if (
            pd.notna(fila["estado_gestion_normalizado"])
            and fila["estado_gestion_normalizado"] != "Sin gestión"
        ):
            utiles.append("gestión comercial registrada")
        if fila["lead_id_normalizado"] in ids_con_conversacion:
            utiles.append("conversación asociada")
        decision = (
            "conservar_con_anotacion"
            if utiles
            else "excluir_sin_valor_recuperable"
        )
        comentario = (
            "Teléfono inválido; conservar porque contiene: "
            + ", ".join(utiles)
            + "."
            if utiles
            else (
                "Teléfono inválido, nombre vacío/de prueba y sin "
                "señales comerciales recuperables ni conversación"
                ". Excluido solo del resultado limpio."
            )
        )
        revision_telefonos_invalidos.append(
            {
                "fila_origen": indice,
                "lead_id": fila["lead_id_normalizado"],
                "empresa": fila["empresa_id_normalizado"],
                "telefono_original": fila["telefono"],
                "telefono_estado": fila["telefono_estado"],
                "decision": decision,
                "comentario": comentario,
            }
        )
    revision_telefonos_invalidos = pd.DataFrame(revision_telefonos_invalidos)
    filas_excluidas = set(
        revision_telefonos_invalidos.loc[
            revision_telefonos_invalidos["decision"].eq(
                "excluir_sin_valor_recuperable"
            ),
            "fila_origen",
        ]
    )
    registros_excluidos = consultas_resueltas.loc[
        consultas_resueltas.index.isin(filas_excluidas)
    ].copy()
    consultas_limpias = consultas_resueltas.loc[
        ~consultas_resueltas.index.isin(filas_excluidas)
    ].copy()
    consultas_limpias["anotacion_telefono"] = consultas_limpias.index.map(
        revision_telefonos_invalidos.set_index("fila_origen")[
            "comentario"
        ].to_dict()
    )
    ids_limpios = set(consultas_limpias["lead_consolidado_id"])
    leads_limpios = leads_consolidados.loc[
        leads_consolidados["lead_consolidado_id"].isin(ids_limpios)
    ].copy()
    conversaciones_limpias = conversaciones_resueltas.copy(deep=True)
    vinculo_valido = conversaciones_limpias["lead_consolidado_id"].isin(
        ids_limpios
    )
    conversaciones_limpias["lead_id_recibido"] = conversaciones_limpias[
        "lead_id"
    ]
    conversaciones_limpias["lead_id_vinculado"] = conversaciones_limpias[
        "lead_id_normalizado"
    ].where(vinculo_valido, pd.NA)
    conversaciones_limpias.loc[
        ~vinculo_valido, ["lead_consolidado_id", "empresa_id_normalizado"]
    ] = pd.NA
    conversaciones_limpias["estado_vinculo"] = vinculo_valido.map(
        {True: "identificado", False: "lead_y_empresa_desconocidos"}
    )
    conversaciones_limpias["anotacion_vinculo"] = vinculo_valido.map(
        {
            True: "Vinculada al lead de origen y a su empresa.",
            False: (
                "El ID recibido no corresponde a un lead conserva"
                "do. Se mantiene la conversación íntegra; lead y "
                "empresa vinculados desconocidos (NULL para base "
                "de datos)."
            ),
        }
    )
    conversaciones_pendientes = conversaciones_limpias.loc[
        ~vinculo_valido
    ].copy()
    trazabilidad_salida_limpia = mapa_origen_consolidado.copy()
    trazabilidad_salida_limpia["estado_salida"] = trazabilidad_salida_limpia[
        "fila_conservada"
    ].map(
        lambda f: (
            "excluido_sin_valor_recuperable"
            if f in filas_excluidas
            else "conservado"
        )
    )
    trazabilidad_salida_limpia["motivo_exclusion"] = (
        trazabilidad_salida_limpia["fila_conservada"].map(
            revision_telefonos_invalidos.loc[
                revision_telefonos_invalidos["decision"].eq(
                    "excluir_sin_valor_recuperable"
                )
            ]
            .set_index("fila_origen")["comentario"]
            .to_dict()
        )
    )
    fechas_por_revisar["estado_registro"] = fechas_por_revisar.apply(
        lambda r: (
            "excluido_sin_valor_recuperable"
            if r["tabla"] == "leads" and r["fila_dataframe"] in filas_excluidas
            else "conservado"
        ),
        axis=1,
    )
    with pd.option_context(
        "display.max_columns", None, "display.max_colwidth", None
    ):
        pass
    if not len(consultas_limpias) + len(registros_excluidos) == len(
        consultas_resueltas
    ):
        raise ValueError(
            "Contrato incumplido: len(consultas_limpias) + le"
            "n(registros_excluidos) == len(consultas_resuelta"
            "s)"
        )
    if (
        not consultas_limpias["lead_consolidado_id"]
        .isin(leads_limpios["lead_consolidado_id"])
        .all()
    ):
        raise ValueError(
            "Contrato incumplido: consultas_limpias['lead_con"
            "solidado_id'].isin(leads_limpios['lead_consolida"
            "do_id']).all()"
        )
    if not leads_limpios["numero_consultas"].sum() == len(consultas_limpias):
        raise ValueError(
            "Contrato incumplido: leads_limpios['numero_consu"
            "ltas'].sum() == len(consultas_limpias)"
        )
    if not len(conversaciones_limpias) == len(conversaciones_resueltas):
        raise ValueError(
            "Contrato incumplido: len(conversaciones_limpias)"
            " == len(conversaciones_resueltas)"
        )
    if not conversaciones_pendientes["lead_id_vinculado"].isna().all():
        raise ValueError(
            "Contrato incumplido: conversaciones_pendientes['"
            "lead_id_vinculado'].isna().all()"
        )
    if not conversaciones_pendientes["empresa_id_normalizado"].isna().all():
        raise ValueError(
            "Contrato incumplido: conversaciones_pendientes['"
            "empresa_id_normalizado'].isna().all()"
        )
    from collections import Counter

    incidencias = []

    def registrar(
        tipo,
        tabla,
        fila,
        identificador,
        campo,
        original,
        resultado,
        accion,
        motivo,
        detalle=None,
    ):
        """Registrar."""
        incidencias.append(
            valor_json(
                {
                    "incidencia_id": f"INC-{len(incidencias) + 1:06d}",
                    "tipo": tipo,
                    "tabla": tabla,
                    "fila_dataframe": fila,
                    "id_origen": identificador,
                    "campo": campo,
                    "valor_original": original,
                    "valor_resultante": resultado,
                    "accion": accion,
                    "motivo": motivo,
                    "detalle": detalle,
                }
            )
        )

    id_tabla = {
        "leads": "lead_id",
        "asesores": "asesor_id",
        "catalogo_motos": "sku",
        "historico_cierres": "lead_id",
        "conversaciones": "conversacion_id",
    }
    for nombre, tabla in datos_normalizados.items():
        for indice, fila in tabla.iterrows():
            identificador = fila[id_tabla[nombre]]
            for campo in campos_originales[nombre]:
                if campo == "mensajes":
                    continue
                original = fila[campo]
                normalizado = fila.get(campo + "_normalizado", original)
                estado = fila.get(campo + "_estado")
                if campo in ["modelo_interes_texto", "modelo_cotizado"]:
                    estado = fila.get("modelo_estado")
                comentario = fila.get(campo + "_criterio")
                vacio = pd.isna(original) or (
                    isinstance(original, str) and (not original.strip())
                )
                if vacio:
                    registrar(
                        "faltante",
                        nombre,
                        indice,
                        identificador,
                        campo,
                        original,
                        normalizado,
                        "conservar_sin_imputar",
                        comentario
                        or (
                            "Campo no informado; no se inventa un valor. Pued"
                            "e ser opcional según el contexto."
                        ),
                    )
                elif estado and estado not in estados_resueltos:
                    registrar(
                        "valor_no_resuelto",
                        nombre,
                        indice,
                        identificador,
                        campo,
                        original,
                        normalizado,
                        "conservar_original_y_marcar",
                        comentario
                        or f"Estado de validación: {estado}. El valor no se reemplaza por una suposición.",
                        {
                            "estado": estado,
                            "candidatos": fila.get("modelo_candidatos")
                            if campo.startswith("modelo")
                            else None,
                        },
                    )
                elif campo + "_normalizado" in tabla.columns and valor_json(
                    original
                ) != valor_json(normalizado):
                    registrar(
                        "normalizacion",
                        nombre,
                        indice,
                        identificador,
                        campo,
                        original,
                        normalizado,
                        "normalizar_en_copia",
                        comentario
                        or (
                            "Aplicación de las reglas explícitas de limpieza,"
                            " equivalencia o conversión de tipo del notebook."
                        ),
                        {"estado": estado},
                    )
                if estado in ["abreviatura_unica", "resuelta_por_contexto"]:
                    registrar(
                        "inferencia_documentada",
                        nombre,
                        indice,
                        identificador,
                        campo,
                        original,
                        normalizado,
                        "conservar_marca_de_inferencia",
                        comentario
                        or (
                            "Asignación a la única referencia compatible del "
                            "catálogo, según la regla de abreviaturas."
                        ),
                    )
    for indice, fila in (
        datos_normalizados["leads"]
        .loc[
            datos_normalizados["leads"]["orden_fechas_detectado"].isin(
                [
                    "MDY_por_evidencia_del_lead",
                    "origen_mixto_resuelto_por_valores",
                    "MDY_por_coherencia_del_lead",
                    "origen_mixto_por_coherencia_unica",
                ]
            )
        ]
        .iterrows()
    ):
        registrar(
            "orden_fechas_corregido",
            "leads",
            indice,
            fila["lead_id"],
            "fechas_del_lead",
            {
                "registro": fila["fecha_registro"],
                "contacto": fila["fecha_primer_contacto"],
            },
            {
                "registro": fila["fecha_registro_normalizado"],
                "contacto": fila["fecha_primer_contacto_normalizado"],
            },
            fila["orden_fechas_detectado"],
            fila["comentario_orden_fechas"],
        )
    for _, fila in fechas_por_revisar.loc[
        fechas_por_revisar["estado"].eq("secuencia_inconsistente")
    ].iterrows():
        registrar(
            "secuencia_fechas",
            fila["tabla"],
            fila["fila_dataframe"],
            fila["id"],
            fila["campo"],
            fila["original"],
            fila["normalizado"],
            "conservar_y_marcar",
            fila["criterio"],
        )
    for _, fila in trazabilidad_filas.loc[
        trazabilidad_filas["accion"].eq("repeticion_exacta")
    ].iterrows():
        registrar(
            "duplicado_exacto",
            "leads",
            fila["fila_origen"],
            fila["lead_id_origen"],
            None,
            leads.loc[fila["fila_origen"]].to_dict(),
            {"fila_conservada": fila["fila_conservada"]},
            "excluir_repeticion_de_salida",
            (
                "Todas las columnas originales son idénticas a ot"
                "ra fila; se conserva la primera aparición y el v"
                "ínculo de trazabilidad."
            ),
        )
    for _, fila in decisiones_identidad.iterrows():
        registrar(
            "duplicado_identidad",
            "leads",
            None,
            fila["lead_ids"],
            None,
            fila["nombres_originales"],
            fila["decision"],
            "agrupar_sin_perder_consultas"
            if fila["decision"] == "agrupado"
            else "mantener_separados",
            (
                "Misma empresa, teléfono válido y evaluación expl"
                "ícita de compatibilidad de todos los pares de no"
                "mbres."
            ),
            fila.to_dict(),
        )
    for telefono, grupo in (
        datos_normalizados["leads"]
        .loc[datos_normalizados["leads"]["telefono_estado"].eq("valido")]
        .groupby("telefono_normalizado")
    ):
        if grupo["empresa_id_normalizado"].nunique() > 1:
            registrar(
                "telefono_en_varias_empresas",
                "leads",
                None,
                grupo["lead_id"].tolist(),
                "telefono",
                telefono,
                telefono,
                "mantener_separados_por_empresa",
                (
                    "Coincidencia entre empresas; nunca se fusionan i"
                    "dentidades de empresas distintas."
                ),
                {
                    "empresas": sorted(
                        grupo["empresa_id_normalizado"].unique().tolist()
                    )
                },
            )
    for _, fila in conversaciones_pendientes.iterrows():
        registrar(
            "conversacion_sin_lead",
            "conversaciones",
            None,
            fila["conversacion_id"],
            "lead_id",
            fila["lead_id_recibido"],
            None,
            "conservar_con_vinculo_desconocido",
            fila["anotacion_vinculo"],
            {"empresa": None, "estado_vinculo": fila["estado_vinculo"]},
        )
    for _, fila in revision_telefonos_invalidos.iterrows():
        registrar(
            "exclusion_registro"
            if fila["decision"].startswith("excluir")
            else "telefono_invalido_con_valor",
            "leads",
            fila["fila_origen"],
            fila["lead_id"],
            "telefono",
            fila["telefono_original"],
            None,
            fila["decision"],
            fila["comentario"],
            leads.loc[fila["fila_origen"]].to_dict(),
        )
    for _, fila in leads_modelo_no_disponible.iterrows():
        registrar(
            "modelo_no_listado_en_punto",
            "leads",
            fila["fila_dataframe"],
            fila["lead_id_normalizado"],
            "modelo_interes_texto",
            fila["modelo_interes_texto"],
            fila["modelo_sku"],
            "conservar_interes_y_catalogo",
            (
                "El SKU identificado no está listado en el punto "
                "asignado. Observación comercial, no error demost"
                "rado del catálogo."
            ),
            {"punto": fila["punto_venta_id_normalizado"]},
        )
    for _, fila in leads_punto_inconsistente.iterrows():
        registrar(
            "empresa_punto_no_reconocido",
            "leads",
            fila["fila_dataframe"],
            fila["lead_id_normalizado"],
            "punto_venta_id",
            fila["punto_venta_id_normalizado"],
            None,
            "conservar_y_marcar",
            ("El par empresa/punto no aparece en la referencia de asesores."),
        )
    for conversacion in conversaciones:
        for posicion, mensaje in enumerate(conversacion["mensajes"], 1):
            for campo in ["emisor", "hora", "texto"]:
                if not mensaje.get(campo):
                    registrar(
                        "mensaje_campo_faltante",
                        "conversaciones",
                        None,
                        conversacion["conversacion_id"],
                        campo,
                        mensaje.get(campo),
                        None,
                        "conservar_mensaje",
                        "Campo ausente en mensaje original.",
                        {"orden_mensaje": posicion},
                    )
    reporte_incidencias = {
        "version": 1,
        "fuente": "02_normalizar.py y data/raw",
        "politicas": {
            "separacion_empresa": (
                "No fusionar entre empresas, aunque coincidan nom"
                "bre, teléfono y correo."
            ),
            "modelos": (
                "Conservar todos los intereses, sin excluir leads"
                " por modelo faltante o ambiguo."
            ),
            "conversaciones": (
                "Conservar todas; vínculo desconocido como null y"
                " marca explícita, preservando el ID recibido."
            ),
            "eliminaciones": (
                "Solo en salidas limpias; conservar fuente y expl"
                "icación de cada exclusión."
            ),
            "fechas": (
                "Consultar la regla y los comentarios de la secci"
                "ón 8; cada corrección figura por campo."
            ),
        },
        "resumen": {
            "eventos": len(incidencias),
            "por_tipo": dict(Counter(i["tipo"] for i in incidencias)),
            "filas_leads_recibidas": len(leads),
            "consultas_conservadas": len(consultas_limpias),
            "identidades_conservadas": len(leads_limpios),
            "conversaciones_conservadas": len(conversaciones_limpias),
            "conversaciones_sin_vinculo": len(conversaciones_pendientes),
            "registros_excluidos_sin_valor": len(registros_excluidos),
        },
        "incidencias": incidencias,
    }
    ruta_incidencias = (
        raiz_proyecto / "outputs" / "calidad_datos" / "incidencias_datos.json"
    )
    ruta_incidencias.parent.mkdir(parents=True, exist_ok=True)
    ruta_incidencias.write_text(
        json.dumps(
            reporte_incidencias, ensure_ascii=False, indent=2, allow_nan=False
        ),
        encoding="utf-8",
    )
    if not len(conversaciones_limpias) == len(conversaciones):
        raise ValueError(
            "Contrato incumplido: len(conversaciones_limpias)"
            " == len(conversaciones)"
        )
    if not conversaciones_limpias["mensajes"].tolist() == [
        c["mensajes"] for c in conversaciones
    ]:
        raise ValueError(
            "Contrato incumplido: conversaciones_limpias['men"
            "sajes'].tolist() == [c['mensajes'] for c in conv"
            "ersaciones]"
        )
    if not consultas_limpias["modelo_interes_texto"].equals(
        consultas_resueltas.loc[
            consultas_limpias.index, "modelo_interes_texto"
        ]
    ):
        raise ValueError(
            "Contrato incumplido: consultas_limpias['modelo_i"
            "nteres_texto'].equals(consultas_resueltas.loc[co"
            "nsultas_limpias.index, 'modelo_interes_texto'])"
        )
    import shutil

    ruta_processed = raiz_proyecto / "data" / "processed"
    ruta_processed.mkdir(parents=True, exist_ok=True)

    consultas_exportadas = tabla_exportable(
        consultas_limpias, list(leads.columns)
    )
    asesores_exportados = tabla_exportable(
        datos_normalizados["asesores"], list(asesores.columns)
    )
    historico_exportado = tabla_exportable(
        datos_normalizados["historico_cierres"],
        list(historico_cierres.columns),
    )
    exportaciones_csv = {
        "leads.csv": leads_limpios,
        "consultas_leads.csv": consultas_exportadas,
        "asesores.csv": asesores_exportados,
        "historico_cierres.csv": historico_exportado,
        "trazabilidad_leads.csv": trazabilidad_salida_limpia,
    }
    for nombre, tabla in exportaciones_csv.items():
        escribir_csv(tabla, ruta_processed / nombre)
    shutil.copyfile(
        ruta_datos / "catalogo_motos.csv",
        ruta_processed / "catalogo_motos.csv",
    )
    conversaciones_exportadas = []
    for _, fila in conversaciones_limpias.iterrows():
        conversaciones_exportadas.append(
            valor_json(
                {
                    "conversacion_id": fila["conversacion_id_normalizado"],
                    "lead_id": fila["lead_id_vinculado"],
                    "lead_consolidado_id": fila["lead_consolidado_id"],
                    "empresa_id": fila["empresa_id_normalizado"],
                    "lead_id_recibido": fila["lead_id_recibido"],
                    "canal": fila["canal_normalizado"],
                    "fecha_inicio": fecha_exportable(
                        fila["fecha_inicio_normalizado"],
                        fila["fecha_inicio_precision"],
                    ),
                    "fecha_inicio_original": fila["fecha_inicio"],
                    "fecha_inicio_estado": fila["fecha_inicio_estado"],
                    "fecha_inicio_criterio": fila["fecha_inicio_criterio"],
                    "estado_vinculo": fila["estado_vinculo"],
                    "anotacion_vinculo": fila["anotacion_vinculo"],
                    "mensajes": fila["mensajes"],
                }
            )
        )
    (ruta_processed / "conversaciones.json").write_text(
        json.dumps(
            conversaciones_exportadas,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    shutil.copyfile(
        ruta_incidencias, ruta_processed / "incidencias_datos.json"
    )
    conteos_exportados = {
        nombre: len(tabla) for nombre, tabla in exportaciones_csv.items()
    }
    conteos_exportados.update(
        {
            "catalogo_motos.csv": len(catalogo_motos),
            "conversaciones.json": len(conversaciones_exportadas),
            "incidencias_datos.json": len(reporte_incidencias["incidencias"]),
        }
    )
    manifest = {
        "version": 1,
        "generador": "02_normalizar.py",
        "codificacion": "UTF-8",
        "separador_csv": ",",
        "nota_conteos": (
            "Incidencias cuenta eventos; trazabilidad incluye"
            " filas excluidas. No son clientes activos."
        ),
        "fuentes": {
            archivo.name: hashlib.sha256(archivo.read_bytes()).hexdigest()
            for archivo in sorted(ruta_datos.iterdir())
            if archivo.suffix in [".csv", ".json"]
        },
        "archivos": {
            nombre: {
                "registros": cantidad,
                "sha256": hashlib.sha256(
                    (ruta_processed / nombre).read_bytes()
                ).hexdigest(),
            }
            for nombre, cantidad in conteos_exportados.items()
        },
        "politicas": reporte_incidencias["politicas"],
    }
    (ruta_processed / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (ruta_processed / "README.md").write_text(
        (
            "# Datos procesados\n\nGenerados ejecutando complet"
            "o `02_normalizar.py`. No editar a mano: se regen"
            "eran.\n\n## Archivos principales\n\n- `leads.csv`: u"
            "na identidad por empresa, clave `lead_consolidad"
            "o_id`.\n- `consultas_leads.csv`: consultas distin"
            "tas con `lead_id` de origen y vínculo `lead_cons"
            "olidado_id`. Incluye valores normalizados, origi"
            "nales y diagnósticos.\n- `conversaciones.json`: t"
            "odas las conversaciones y mensajes. `lead_id` en"
            "laza a consultas y `lead_consolidado_id` a leads"
            ". Los vínculos desconocidos son null; `lead_id_r"
            "ecibido` conserva la referencia original.\n- `ase"
            "sores.csv`: asesores normalizados, con originale"
            "s y validaciones.\n- `catalogo_motos.csv`: copia "
            "exacta del original.\n- `historico_cierres.csv`: "
            "histórico normalizado; sus leads no pertenecen a"
            "l conjunto actual.\n\n## Auditoría\n\n- `trazabilida"
            "d_leads.csv`: todas las filas recibidas, incluid"
            "as repeticiones y el registro excluido, con moti"
            "vos.\n- `incidencias_datos.json`: hallazgos y dec"
            "isiones. Incluye el registro excluido como evide"
            "ncia; no es un cliente activo.\n- `manifest.json`"
            ": conteos y hashes de archivos fuente y generado"
            "s.\n\n## Convenciones y límites\n\nCSV en UTF-8, com"
            "a como separador y faltantes vacíos. Las listas "
            "se guardan como JSON dentro del CSV. JSON usa nu"
            "ll para desconocidos. Fechas normalizadas en año"
            "-mes-día, con hora cuando existe; las columnas `"
            "_original` mantienen el valor recibido.\n\nLos mod"
            "elos ambiguos o ausentes se conservan. LD-01501 "
            "(prueba prueba) se excluye por no aportar valor "
            "recuperable. Las conversaciones sin lead siguen "
            "presentes con empresa desconocida. Las identidad"
            "es nunca se fusionan entre empresas.\n\nLa identid"
            "ad y algunas interpretaciones de fecha se resuel"
            "ven con reglas documentadas: son inferencias, no"
            " verificación de identidad real. Fechas vacías p"
            "ermanecen vacías. Las fechas agregadas de leads "
            "no deben tratarse como horas exactas cuando la f"
            "uente solo informa el día.\n\nEstos archivos compl"
            "etan ingestión, normalización y consolidación. N"
            "o sustituyen la base de datos final exigida por "
            "la prueba.\n"
        ),
        encoding="utf-8",
    )
    leads_guardados = pd.read_csv(
        ruta_processed / "leads.csv",
        dtype={"lead_consolidado_id": "string", "empresa_id": "string"},
    )
    consultas_guardadas = pd.read_csv(
        ruta_processed / "consultas_leads.csv",
        dtype={"lead_id": "string", "telefono": "string"},
    )
    conversaciones_guardadas = json.loads(
        (ruta_processed / "conversaciones.json").read_text(encoding="utf-8")
    )
    if not len(leads_guardados) == len(leads_limpios):
        raise ValueError(
            "Contrato incumplido: len(leads_guardados) == len(leads_limpios)"
        )
    if not len(consultas_guardadas) == len(consultas_limpias):
        raise ValueError(
            "Contrato incumplido: len(consultas_guardadas) =="
            " len(consultas_limpias)"
        )
    if not len(conversaciones_guardadas) == len(conversaciones):
        raise ValueError(
            "Contrato incumplido: len(conversaciones_guardada"
            "s) == len(conversaciones)"
        )
    if not "LD-01501" not in set(consultas_guardadas["lead_id"]):
        raise ValueError(
            "Contrato incumplido: 'LD-01501' not in set(consu"
            "ltas_guardadas['lead_id'])"
        )
    if not all(
        "LD-01501" not in json.loads(ids)
        for ids in leads_guardados["lead_ids_origen"]
    ):
        raise ValueError(
            "Contrato incumplido: all(('LD-01501' not in json"
            ".loads(ids) for ids in leads_guardados['lead_ids"
            "_origen']))"
        )
    if not leads_guardados["lead_consolidado_id"].is_unique:
        raise ValueError(
            "Contrato incumplido: leads_guardados['lead_conso"
            "lidado_id'].is_unique"
        )
    if not consultas_guardadas["lead_id"].is_unique:
        raise ValueError(
            "Contrato incumplido: consultas_guardadas['lead_id'].is_unique"
        )
    empresas_salida = leads_guardados.set_index("lead_consolidado_id")[
        "empresa_id"
    ].to_dict()
    if not all(
        (
            empresas_salida[fila["lead_consolidado_id"]] == fila["empresa_id"]
            for _, fila in consultas_guardadas.iterrows()
        )
    ):
        raise ValueError(
            "Contrato incumplido: all((empresas_salida[fila['"
            "lead_consolidado_id']] == fila['empresa_id'] for"
            " _, fila in consultas_guardadas.iterrows()))"
        )
    consulta_por_id = consultas_guardadas.set_index("lead_id").to_dict("index")
    for original, guardada in zip(
        conversaciones, conversaciones_guardadas, strict=False
    ):
        if not original["conversacion_id"] == guardada["conversacion_id"]:
            raise ValueError(
                "Contrato incumplido: original['conversacion_id']"
                " == guardada['conversacion_id']"
            )
        if not original["lead_id"] == guardada["lead_id_recibido"]:
            raise ValueError(
                "Contrato incumplido: original['lead_id'] == guar"
                "dada['lead_id_recibido']"
            )
        if not original["mensajes"] == guardada["mensajes"]:
            raise ValueError(
                "Contrato incumplido: original['mensajes'] == gua"
                "rdada['mensajes']"
            )
        if guardada["lead_id"] is None:
            if not (
                guardada["empresa_id"] is None
                and guardada["lead_consolidado_id"] is None
            ):
                raise ValueError(
                    "Contrato incumplido: guardada['empresa_id'] is N"
                    "one and guardada['lead_consolidado_id'] is None"
                )
            if not guardada["estado_vinculo"] == "lead_y_empresa_desconocidos":
                raise ValueError(
                    "Contrato incumplido: guardada['estado_vinculo'] "
                    "== 'lead_y_empresa_desconocidos'"
                )
        else:
            consulta = consulta_por_id[guardada["lead_id"]]
            if (
                not guardada["lead_consolidado_id"]
                == consulta["lead_consolidado_id"]
            ):
                raise ValueError(
                    "Contrato incumplido: guardada['lead_consolidado_"
                    "id'] == consulta['lead_consolidado_id']"
                )
            if not guardada["empresa_id"] == consulta["empresa_id"]:
                raise ValueError(
                    "Contrato incumplido: guardada['empresa_id'] == c"
                    "onsulta['empresa_id']"
                )
    if (
        not (ruta_processed / "catalogo_motos.csv").read_bytes()
        == (ruta_datos / "catalogo_motos.csv").read_bytes()
    ):
        raise ValueError(
            "Contrato incumplido: (ruta_processed / 'catalogo"
            "_motos.csv').read_bytes() == (ruta_datos / 'cata"
            "logo_motos.csv').read_bytes()"
        )
    for nombre in [
        "asesores.csv",
        "catalogo_motos.csv",
        "historico_cierres.csv",
        "trazabilidad_leads.csv",
    ]:
        if (
            not len(pd.read_csv(ruta_processed / nombre))
            == conteos_exportados[nombre]
        ):
            raise ValueError(
                "Contrato incumplido: len(pd.read_csv(ruta_proces"
                "sed / nombre)) == conteos_exportados[nombre]"
            )
    for nombre, detalle in manifest["archivos"].items():
        if (
            not hashlib.sha256(
                (ruta_processed / nombre).read_bytes()
            ).hexdigest()
            == detalle["sha256"]
        ):
            raise ValueError(
                "Contrato incumplido: hashlib.sha256((ruta_proces"
                "sed / nombre).read_bytes()).hexdigest() == detal"
                "le['sha256']"
            )
    return manifest
