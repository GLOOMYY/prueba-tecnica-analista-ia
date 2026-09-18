"""Extrae hechos con evidencia, caché y descarte por inconsistencias."""

from datetime import UTC
from pathlib import Path

from dominio.contrato_extraccion import (
    PROMPT,
    SCHEMA,
    Dinero,
    Estricto,
    Extraccion,
    Hallazgo,
    Monto,
    Respuesta,
    crear_normalizador,
)
from dominio.cuota_ia import reservar_cuota

from .reglas_extraccion import (
    agrupar,
    entrada,
    errores_tecnicos,
    normalizar_nombre,
    simple,
)


def ejecutar(root: Path, permitir_api: bool = True) -> dict:
    """Extrae hechos con evidencia, caché y descarte por inconsistencias.

    Args:
        root: Directorio de trabajo con data y outputs.
        permitir_api: Permite peticiones nuevas cuando falta caché.

    Returns:
        Resumen verificable de la etapa.
    """
    import hashlib
    import json
    import os
    import re
    import time
    from datetime import datetime
    from pathlib import Path
    from typing import Literal

    import pandas as pd
    from dotenv import dotenv_values
    from google import genai
    from google.genai import types

    ROOT = root
    OUT = ROOT / "outputs/extraccion_ia_v2"
    COMPARTIDA = (
        Path(__file__).resolve().parents[1] / "outputs/extraccion_ia_v2"
    )
    OUT.mkdir(parents=True, exist_ok=True)
    CACHE = COMPARTIDA / "cache"
    CACHE.mkdir(parents=True, exist_ok=True)
    MODELO = "gemini-3.5-flash-lite"
    EJECUTAR_API = permitir_api
    MAX_INTENTOS_PILOTO = 240
    INTERVALO_SEGUNDOS = 6.1
    VERSION_PROMPT = "2.0"
    CONFIG = {"max_output_tokens": 24000}

    def guardar(path, obj):
        """Guardar."""
        temporal = path.with_suffix(path.suffix + ".tmp")
        temporal.write_text(
            json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporal.replace(path)

    conversaciones = json.loads(
        (ROOT / "data/processed/conversaciones.json").read_text(
            encoding="utf-8"
        )
    )
    catalogo = pd.read_csv(ROOT / "data/processed/catalogo_motos.csv")
    import copy
    import threading
    from decimal import Decimal

    LOCK = threading.RLock()
    VERSION_NORMALIZADOR = "2.5"

    enriquecer, convertir_expresion, catalogo_exactos = crear_normalizador(
        catalogo,
        modelo=MODELO,
        version_prompt=VERSION_PROMPT,
        version_normalizador=VERSION_NORMALIZADOR,
    )
    guardar(OUT / "schema.json", SCHEMA)
    (OUT / "prompt.txt").write_text(PROMPT, encoding="utf-8")

    BITACORA = COMPARTIDA / "llamadas.json"
    historial = (
        json.loads(BITACORA.read_text(encoding="utf-8"))
        if BITACORA.exists()
        else []
    )
    cliente = None

    def pedir(grupo, modalidad):
        """Pedir."""
        nonlocal cliente
        if not 1 <= len(grupo) <= 5:
            raise ValueError("Tamaño de grupo inválido")
        empresas = {c["empresa_id"] for c in grupo}
        if not (
            len(empresas) == 1 and (None not in empresas or len(grupo) == 1)
        ):
            raise ValueError("No se pueden mezclar empresas")
        payload = entrada(grupo)
        especificacion = {
            "modelo": MODELO,
            "prompt": PROMPT,
            "schema": SCHEMA,
            "config": CONFIG,
            "entrada": payload,
            "modalidad": modalidad,
        }
        huella = hashlib.sha256(
            json.dumps(
                especificacion, sort_keys=True, ensure_ascii=False
            ).encode()
        ).hexdigest()
        archivo = CACHE / f"{huella}.json"
        if archivo.exists():
            registro = json.loads(archivo.read_text(encoding="utf-8"))
        else:
            if not EJECUTAR_API:
                raise RuntimeError(
                    "Falta caché y EJECUTAR_API=False; no se hicieron llamadas."
                )
            with LOCK:
                if cliente is None:
                    clave = os.environ.get("API_KEY_GEMINI") or dotenv_values(
                        Path(__file__).resolve().parents[2] / ".env"
                    ).get("API_KEY_GEMINI")
                    if not clave:
                        raise RuntimeError(
                            "Falta API_KEY_GEMINI en .env o en el entorno."
                        )
                    cliente = genai.Client(
                        api_key=clave,
                        http_options=types.HttpOptions(
                            timeout=120000,
                            retry_options=types.HttpRetryOptions(attempts=1),
                        ),
                    )
                    del clave
            for intento in range(2):
                with LOCK:
                    if (
                        sum(
                            e["fecha_utc"][:10]
                            == datetime.now(UTC).date().isoformat()
                            for e in historial
                        )
                        >= MAX_INTENTOS_PILOTO
                    ):
                        raise RuntimeError(
                            "Se alcanzó el tope persistido de intentos diarios."
                        )
                    if historial:
                        time.sleep(
                            max(
                                0,
                                INTERVALO_SEGUNDOS
                                - (
                                    time.time() - historial[-1]["inicio_epoch"]
                                ),
                            )
                        )
                    evento = {
                        "huella": huella,
                        "modalidad": modalidad,
                        "modelo": MODELO,
                        "ids": [c["conversacion_id"] for c in grupo],
                        "inicio_epoch": time.time(),
                        "fecha_utc": datetime.now(UTC).isoformat(),
                        "estado": "iniciado",
                    }
                    historial.append(evento)
                    guardar(BITACORA, historial)
                try:
                    if not reservar_cuota(MODELO):
                        raise RuntimeError(
                            "Cuota compartida agotada; reanudar."
                        )
                    respuesta = cliente.models.generate_content(
                        model=MODELO,
                        contents=json.dumps(payload, ensure_ascii=False),
                        config=types.GenerateContentConfig(
                            **CONFIG,
                            system_instruction=PROMPT,
                            response_mime_type="application/json",
                            response_json_schema=SCHEMA,
                        ),
                    )
                except Exception as exc:
                    codigo = getattr(exc, "code", None)
                    with LOCK:
                        evento.update(
                            estado="error",
                            tipo=type(exc).__name__,
                            codigo=codigo,
                            segundos=round(
                                time.time() - evento["inicio_epoch"], 2
                            ),
                        )
                        guardar(BITACORA, historial)
                    if intento == 0 and (
                        codigo in (500, 502, 503, 504)
                        or type(exc).__name__
                        in ("ConnectError", "ReadTimeout")
                    ):
                        time.sleep(10)
                        continue
                    raise RuntimeError(
                        f"Gemini no completó la petición: {type(exc).__name__}, código {codigo}. Detenido; ver bitácora sin credenciales."
                    ) from None
                registro = {
                    "huella": huella,
                    "modelo": MODELO,
                    "version_prompt": VERSION_PROMPT,
                    "modalidad": modalidad,
                    "ids": evento["ids"],
                    "fecha_utc": evento["fecha_utc"],
                    "segundos": round(time.time() - evento["inicio_epoch"], 2),
                    "uso": respuesta.usage_metadata.model_dump(mode="json")
                    if respuesta.usage_metadata
                    else {},
                    "texto": respuesta.text or "",
                }
                guardar(archivo, registro)
                with LOCK:
                    evento.update(
                        estado="recibido",
                        segundos=registro["segundos"],
                        uso=registro["uso"],
                    )
                    guardar(BITACORA, historial)
                break
        try:
            parsed = Respuesta.model_validate_json(registro["texto"])
            resultados = [r.model_dump() for r in parsed.conversaciones]
            recibidos = [r["conversacion_id"] for r in resultados]
            if not (
                len(recibidos) == len(set(recibidos))
                and set(recibidos) == set(registro["ids"])
            ):
                raise ValueError("IDs incorrectos")
        except Exception:
            guardar(
                OUT / f"error_validacion_{huella}.json",
                {
                    "huella": huella,
                    "motivo": "JSON, esquema o IDs inválidos; revisar respuesta en caché.",
                },
            )
            raise RuntimeError(
                "Respuesta inválida conservada en caché para revi"
                "sión; no se reenvía automáticamente."
            ) from None
        originales = {c["conversacion_id"]: c for c in grupo}
        return [
            dict(
                enriquecer(r, originales[r["conversacion_id"]]), huella=huella
            )
            for r in resultados
        ]

    POR_CONVERSACION = COMPARTIDA / "por_conversacion"
    POR_CONVERSACION.mkdir(exist_ok=True)

    def huella_conversacion(c):
        """Huella conversacion."""
        spec = {
            "entrada": entrada([c]),
            "modelo": MODELO,
            "prompt": PROMPT,
            "schema": SCHEMA,
            "config": CONFIG,
            "normalizador": VERSION_NORMALIZADOR,
        }
        return hashlib.sha256(
            json.dumps(spec, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()

    def procesar(cs, modalidad):
        """Procesar."""
        disponibles = {}
        faltan = []
        for c in cs:
            h = huella_conversacion(c)
            p = POR_CONVERSACION / f"{h}.json"
            if p.exists():
                r = json.loads(p.read_text(encoding="utf-8"))
                if r.get("huella_conversacion") != h:
                    raise ValueError("Huella de caché incompatible.")
                # El catálogo puede cambiar sin cambiar el mensaje del cliente.
                r["catalogo"] = []
                for mencion in r["extraccion"]["modelos_interes"]:
                    candidatos = catalogo_exactos.get(
                        normalizar_nombre(mencion["valor"] or ""), []
                    )
                    r["catalogo"].append(
                        {
                            "mencion": mencion["valor"],
                            "sku": candidatos[0]
                            if len(candidatos) == 1
                            else None,
                        }
                    )
                r.update(
                    {
                        k: c.get(k)
                        for k in [
                            "lead_id",
                            "lead_consolidado_id",
                            "empresa_id",
                            "estado_vinculo",
                        ]
                    }
                )
                disponibles[c["conversacion_id"]] = r
            else:
                faltan.append(c)
        grupos = agrupar(faltan)

        def ejecutar_grupo(grupo):
            """Ejecutar grupo."""
            nuevos = pedir(grupo, modalidad)
            for r in nuevos:
                cid = r["extraccion"]["conversacion_id"]
                c = next(c for c in grupo if c["conversacion_id"] == cid)
                r["huella_conversacion"] = huella_conversacion(c)
                guardar(
                    POR_CONVERSACION / f"{r['huella_conversacion']}.json", r
                )
            return nuevos

        from concurrent.futures import ThreadPoolExecutor, as_completed

        pendientes = {}
        restantes = iter(grupos)
        terminados = 0
        with ThreadPoolExecutor(max_workers=3) as executor:
            for grupo in list(grupos[:3]):
                next(restantes)
                pendientes[executor.submit(ejecutar_grupo, grupo)] = grupo
            while pendientes:
                futuro = next(as_completed(pendientes))
                pendientes.pop(futuro)
                try:
                    nuevos = futuro.result()
                except Exception:
                    for f in pendientes:
                        f.cancel()
                    raise
                for r in nuevos:
                    disponibles[r["extraccion"]["conversacion_id"]] = r
                terminados += 1
                guardar(
                    OUT / "avance.json",
                    {
                        "modalidad": modalidad,
                        "completadas": len(disponibles),
                        "total": len(cs),
                        "grupo": terminados,
                        "grupos_nuevos": len(grupos),
                    },
                )
                siguiente = next(restantes, None)
                if siguiente is not None:
                    pendientes[executor.submit(ejecutar_grupo, siguiente)] = (
                        siguiente
                    )
        return [disponibles[c["conversacion_id"]] for c in cs]

    por_id = {c["conversacion_id"]: c for c in conversaciones}
    resultados = procesar(conversaciones, "completo")

    candidatos = [
        (i, r) for i, r in enumerate(resultados) if errores_tecnicos(r)
    ]
    revisiones = []
    for posicion, previo in candidatos[:20]:
        cid = previo["extraccion"]["conversacion_id"]
        nuevo = pedir([por_id[cid]], "revision_evidencia")[0]
        mejora = errores_tecnicos(nuevo) < errores_tecnicos(previo)
        revisiones.append(
            {
                "conversacion_id": cid,
                "errores_antes": errores_tecnicos(previo),
                "errores_despues": errores_tecnicos(nuevo),
                "respuesta_previa": previo["huella"],
                "respuesta_nueva": nuevo["huella"],
                "adoptada": mejora,
            }
        )
        if mejora:
            nuevo["huella_conversacion"] = huella_conversacion(por_id[cid])
            nuevo["incidencias"].append(
                {
                    "campo": "extraccion",
                    "tipo": "reextraccion_por_evidencia_invalida",
                    "detalle": (
                        "Se repitió individualmente una respuesta con evi"
                        "dencia inválida; ambas respuestas originales se "
                        "conservan."
                    ),
                    "antes": previo["huella"],
                    "despues": nuevo["huella"],
                    "estado": "corregido_por_regla",
                }
            )
            guardar(
                POR_CONVERSACION / f"{nuevo['huella_conversacion']}.json",
                nuevo,
            )
            resultados[posicion] = nuevo
    if revisiones:
        guardar(OUT / "revisiones_evidencia.json", revisiones)
    from collections import Counter

    plain = simple
    sources = por_id
    indice_resultados = {
        r["extraccion"]["conversacion_id"]: r for r in resultados
    }
    checks = []
    for cid, r in indice_resultados.items():
        c = sources[cid]
        for n, m in enumerate(c["mensajes"], 1):
            if m["emisor"] != "cliente":
                continue
            t = plain(m["texto"])
            field = None
            expected = None
            if t.startswith("de contado, ya tengo la plata lista, "):
                field = "presupuesto_total"
            elif "inicial" in t and "tengo" in t:
                field = "cuota_inicial"
            if field is None:
                continue
            if t in (
                "no tengo inicial",
                "no tengo con que dar la inicial ahora",
            ):
                expected = 0
            else:
                matches = list(
                    re.finditer(
                        "\\d+(?:[.,]\\d+)*\\s*(?:millonzitos|millones|palos|mil)?",
                        t,
                    )
                )
                if len(matches) != 1:
                    continue
                raw = matches[0].group().strip()
                number = (
                    re.match("[\\d.,]+", raw)
                    .group()
                    .replace(".", "")
                    .replace(",", ".")
                )
                factor = (
                    1000000
                    if any(
                        u in raw for u in ["millonzitos", "millones", "palos"]
                    )
                    else 1000
                    if "mil" in raw
                    else 1
                )
                expected = float(Decimal(number) * factor)
            actual = r["extraccion"]["dinero"][field]["valor"]
            checks.append(
                {
                    "conversacion_id": cid,
                    "mensaje": n,
                    "campo": field,
                    "esperado": expected,
                    "obtenido": actual,
                    "cumple": actual == expected,
                    "texto_original": m["texto"],
                }
            )
    catalog = catalogo.to_dict("records")
    grouped = {}
    for c in checks:
        grouped.setdefault((c["conversacion_id"], c["campo"]), []).append(c)
    checks = []
    for group in grouped.values():
        if len({c["esperado"] for c in group}) > 1:
            base = group[-1].copy()
            base.update(
                esperado=None,
                cumple=base["obtenido"] is None,
                motivo="Declaraciones incompatibles; conservar desconocido.",
                declaraciones=group,
            )
            checks.append(base)
        else:
            checks.extend(group)
    model_checks = []
    for cid, r in indice_resultados.items():
        texts = [
            plain(m["texto"])
            for m in sources[cid]["mensajes"]
            if m["emisor"] == "cliente"
        ]
        expected = {
            c["sku"]
            for c in catalog
            if any(plain(c["marca"] + " " + c["linea"]) in t for t in texts)
        }
        actual = {m["sku"] for m in r["catalogo"] if m["sku"]}
        model_checks.append(
            {
                "conversacion_id": cid,
                "skus_explicitos": sorted(expected),
                "skus_extraidos": sorted(actual),
                "cumple": expected == actual,
            }
        )
    summary = {
        "conversaciones_auditadas": len(indice_resultados),
        "comprobaciones_montos": len(checks),
        "fallos_montos": [x for x in checks if not x["cumple"]],
        "fallos_modelos": [x for x in model_checks if not x["cumple"]],
        "estados": dict(
            Counter(r["estado_extraccion"] for r in indice_resultados.values())
        ),
        "incidencias_pendientes": [
            {"conversacion_id": cid, **i}
            for cid, r in indice_resultados.items()
            for i in r["incidencias"]
            if i["estado"] == "pendiente_revision"
        ],
    }
    guardar(
        OUT / "auditoria_cobertura.json",
        {"resumen": summary, "montos": checks, "modelos": model_checks},
    )
    if summary["fallos_montos"] or summary["fallos_modelos"]:
        raise RuntimeError(
            "La auditoría detectó importes o modelos explícit"
            "os omitidos; revisar antes de exportar."
        )
    from typing import Any

    from pydantic import TypeAdapter

    class MontoNormalizado(Monto):  # noqa: D101 - Preservar el esquema Gemini aprobado.
        valor: float | None
        minimo: float | None
        maximo: float | None
        aproximado: bool | None
        moneda: str | None

    class DineroNormalizado(Dinero):  # noqa: D101 - Preservar el esquema Gemini aprobado.
        presupuesto_total: MontoNormalizado
        cuota_inicial: MontoNormalizado
        cuota_mensual_maxima: MontoNormalizado

    class HallazgoNormalizado(Hallazgo):  # noqa: D101 - Preservar el esquema Gemini aprobado.
        origen: Literal["modelo", "regla_local"]

    class ExtraccionNormalizada(Extraccion):  # noqa: D101 - Preservar el esquema Gemini aprobado.
        dinero: DineroNormalizado
        inconsistencias: list[HallazgoNormalizado]
        cambios_de_declaracion: list[HallazgoNormalizado]

    class CoincidenciaCatalogo(Estricto):  # noqa: D101 - Preservar el esquema Gemini aprobado.
        mencion: str | None
        sku: str | None

    class IncidenciaNormalizacion(Estricto):  # noqa: D101 - Preservar el esquema Gemini aprobado.
        campo: str
        tipo: str
        detalle: str
        antes: Any
        despues: Any
        estado: Literal["pendiente_revision", "corregido_por_regla"]

    class ResultadoNormalizado(Estricto):  # noqa: D101 - Preservar el esquema Gemini aprobado.
        lead_id: str | None
        lead_consolidado_id: str | None
        empresa_id: str | None
        estado_vinculo: str | None
        extraccion: ExtraccionNormalizada
        catalogo: list[CoincidenciaCatalogo]
        incidencias: list[IncidenciaNormalizacion]
        estado_extraccion: Literal[
            "requiere_revision", "validada_automaticamente"
        ]
        revision_semantica: str
        modelo: str
        version_prompt: str
        version_normalizador: str
        huella: str
        huella_conversacion: str

    contrato_final = TypeAdapter(list[ResultadoNormalizado])
    contrato_final.validate_python(resultados)
    guardar(
        OUT / "schema_resultados_normalizados.json",
        contrato_final.json_schema(),
    )
    if len(resultados) != len(conversaciones) or len(
        {r["extraccion"]["conversacion_id"] for r in resultados}
    ) != len(conversaciones):
        raise ValueError(
            "La exportación requiere exactamente una extracci"
            "ón por conversación."
        )
    for r in resultados:
        c = por_id[r["extraccion"]["conversacion_id"]]
        if any(
            r[k] != c[k]
            for k in ["empresa_id", "lead_id", "lead_consolidado_id"]
        ):
            raise ValueError("Vínculo alterado durante la extracción.")
    incidencias_finales = []
    filas = []
    for r in resultados:
        e = r["extraccion"]
        cid = e["conversacion_id"]
        base = {
            "conversacion_id": cid,
            "empresa_id": r["empresa_id"],
            "lead_id": r["lead_id"],
            "origen": "03_extraer_ia",
            "version_prompt": VERSION_PROMPT,
        }
        for i in r["incidencias"]:
            incidencias_finales.append({**base, **i})
        for i in e["inconsistencias"]:
            incidencias_finales.append(
                {
                    **base,
                    "tipo": "inconsistencia_candidata_ia"
                    if i["origen"] == "modelo"
                    else "inconsistencia_detectada_por_regla",
                    "estado": "pendiente_revision_semantica",
                    "detalle": i,
                }
            )
        for i in e["limitaciones"]:
            incidencias_finales.append(
                {
                    **base,
                    "tipo": "limitacion_ia",
                    "estado": "informativo",
                    "detalle": i,
                }
            )
        if r["empresa_id"] is None:
            incidencias_finales.append(
                {
                    **base,
                    "tipo": "empresa_desconocida",
                    "estado": "sin_vinculo",
                    "detalle": (
                        "Conversación conservada; no se asigna a una empr"
                        "esa por inferencia."
                    ),
                }
            )
        filas.append(
            {
                **base,
                "modelos": "; ".join(
                    m["valor"] or "" for m in e["modelos_interes"]
                ),
                "presupuesto": e["dinero"]["presupuesto_total"]["valor"],
                "inicial": e["dinero"]["cuota_inicial"]["valor"],
                "cuota_maxima": e["dinero"]["cuota_mensual_maxima"]["valor"],
                "forma_pago": e["forma_pago"]["valor"],
                "intencion": e["intencion_declarada"]["valor"],
                "objecion": e["objecion_principal"]["valor"],
                "pidio_cita": e["cita"]["cliente_solicito"]["estado"],
                "pidio_cotizacion": e["cotizacion"]["cliente_solicito"][
                    "estado"
                ],
                "acepto_cotizacion": e["cotizacion"]["cliente_acepto"][
                    "estado"
                ],
                "estado_extraccion": r["estado_extraccion"],
                "mensajes_originales": "\n".join(
                    (
                        f"{n}. {m['emisor']}: {m['texto']}"
                        for n, m in enumerate(por_id[cid]["mensajes"], 1)
                    )
                ),
            }
        )
    guardar(OUT / "resultados_completos.json", resultados)
    guardar(OUT / "incidencias_ia.json", incidencias_finales)
    destino = ROOT / "data/processed"
    guardar(destino / "extracciones_conversaciones_ia.json", resultados)
    guardar(destino / "incidencias_extraccion_ia.json", incidencias_finales)
    revision = pd.DataFrame(filas)
    revision.to_csv(
        OUT / "revision_completa.csv", index=False, encoding="utf-8-sig"
    )
    uso = []
    for llamada in historial:
        if llamada["estado"] == "recibido":
            u = llamada.get("uso", {})
            modelo_usado = (
                llamada.get("modelo")
                or json.loads(
                    (CACHE / f"{llamada['huella']}.json").read_text(
                        encoding="utf-8"
                    )
                )["modelo"]
            )
            uso.append(
                {
                    "modelo": modelo_usado,
                    "modalidad": llamada["modalidad"],
                    "peticiones": 1,
                    "entrada": u.get("prompt_token_count") or 0,
                    "salida": u.get("candidates_token_count") or 0,
                    "total": u.get("total_token_count") or 0,
                }
            )
    guardar(OUT / "consumo.json", uso)
    resumen = {
        "modelo": MODELO,
        "version_prompt": VERSION_PROMPT,
        "version_normalizador": VERSION_NORMALIZADOR,
        "conversaciones": len(resultados),
        "empresas_desconocidas": int(revision["empresa_id"].isna().sum()),
        "piloto": "validado_en_etapa_de_desarrollo_no_repetido",
        "comprobaciones_montos_fuente": len(checks),
        "comprobaciones_modelos_fuente": len(model_checks),
        "registros_con_campos_pendientes": sum(
            r["estado_extraccion"] == "requiere_revision" for r in resultados
        ),
        "incidencias": len(incidencias_finales),
        "intentos_api_v2": len(historial),
        "estado": "extraccion_completa_con_incidencias_trazables",
        "revision_semantica_exhaustiva": False,
    }
    guardar(OUT / "resumen.json", resumen)
    guardar(
        destino / "manifest_extraccion_ia.json",
        {
            **resumen,
            "fuente_sha256": hashlib.sha256(
                (destino / "conversaciones.json").read_bytes()
            ).hexdigest(),
            "resultados_sha256": hashlib.sha256(
                (destino / "extracciones_conversaciones_ia.json").read_bytes()
            ).hexdigest(),
            "incidencias_sha256": hashlib.sha256(
                (destino / "incidencias_extraccion_ia.json").read_bytes()
            ).hexdigest(),
            "schema_sha256": hashlib.sha256(
                json.dumps(SCHEMA, sort_keys=True).encode()
            ).hexdigest(),
        },
    )
    pendientes_importes = []
    for r in resultados:
        for hallazgo in r["extraccion"]["inconsistencias"]:
            if hallazgo["origen"] == "regla_local" and hallazgo[
                "campo"
            ].startswith("dinero."):
                pendientes_importes.append(
                    {
                        "conversacion_id": r["extraccion"]["conversacion_id"],
                        "empresa_id": r["empresa_id"],
                        "lead_id": r["lead_id"],
                        "campo": hallazgo["campo"],
                        "valor_final": None,
                        "motivo": hallazgo["descripcion"],
                        "declaraciones": hallazgo["evidencias"],
                    }
                )
    guardar(OUT / "pendientes_importes.json", pendientes_importes)
    POLITICA_DESCARTE = "excluir_conversaciones_con_inconsistencias_v1"

    def detectar_inconsistencias_fuente(conversacion):
        """Detectar inconsistencias fuente."""
        mensajes = conversacion["mensajes"]
        hallazgos = []

        def ev(i):
            """Ev."""
            return {
                "mensaje": i + 1,
                "emisor": mensajes[i]["emisor"],
                "texto": mensajes[i]["texto"],
            }

        def agregar(tipo, descripcion, indices):
            """Agregar."""
            hallazgos.append(
                {
                    "origen": "regla_local_sobre_fuente",
                    "tipo": tipo,
                    "descripcion": descripcion,
                    "evidencias": [ev(i) for i in indices],
                }
            )

        for i, m in enumerate(mensajes):
            if m["emisor"] != "asesor":
                continue
            t = simple(m["texto"])
            previos = [
                (j, x)
                for j, x in enumerate(mensajes[:i])
                if x["emisor"] == "cliente"
            ]
            if "con esa inicial" in t:
                declaraciones = []
                for j, x in previos:
                    if "inicial" not in simple(x["texto"]):
                        continue
                    try:
                        monto = convertir_expresion(x["texto"])
                        if any(
                            monto[k] is not None
                            for k in ["valor", "minimo", "maximo"]
                        ):
                            declaraciones.append(j)
                    except ValueError:
                        pass
                if not declaraciones:
                    agregar(
                        "referencia_a_inicial_no_declarada",
                        (
                            "El asesor utiliza «esa inicial» sin una declarac"
                            "ión previa de su importe por el cliente."
                        ),
                        [j for j, _ in previos] + [i],
                    )
            if "estudio de credito" in t:
                pagos = [
                    (j, x)
                    for j, x in previos
                    if re.search(
                        "\\bde contado\\b|\\ba credito\\b|\\bfinanciada\\b",
                        simple(x["texto"]),
                    )
                ]
                if pagos and "de contado" in simple(pagos[-1][1]["texto"]):
                    agregar(
                        "estudio_credito_tras_contado",
                        (
                            "El asesor ofrece un estudio de crédito después d"
                            "e que el cliente declaró pago de contado."
                        ),
                        [pagos[-1][0], i],
                    )

        def precio(i):
            """Precio."""
            importes = re.findall(
                "\\$\\s*(\\d{1,3}(?:\\.\\d{3})+|\\d+)", mensajes[i]["texto"]
            )
            return (
                Decimal(importes[0].replace(".", ""))
                if len(importes) == 1
                else None
            )

        for i, m in enumerate(mensajes):
            if m["emisor"] != "cliente" or "mas economico" not in simple(
                m["texto"]
            ):
                continue
            anteriores = [
                j
                for j in range(i)
                if mensajes[j]["emisor"] == "asesor" and precio(j) is not None
            ]
            posteriores = [
                j
                for j in range(i + 1, len(mensajes))
                if mensajes[j]["emisor"] == "asesor" and precio(j) is not None
            ]
            if anteriores and posteriores:
                a, b = (anteriores[-1], posteriores[0])
                if precio(b) > precio(a):
                    agregar(
                        "alternativa_mas_economica_con_precio_superior",
                        (
                            "La alternativa solicitada como más económica tie"
                            "ne un precio explícito superior al modelo previo"
                            "."
                        ),
                        [a, i, b],
                    )
        return hallazgos

    aprobadas = []
    descartadas = []
    adicionales_fuente = []
    for registro in resultados:
        cid = registro["extraccion"]["conversacion_id"]
        motivos = [
            {
                "origen": h["origen"],
                "tipo": "inconsistencia_en_extraccion",
                **h,
            }
            for h in registro["extraccion"]["inconsistencias"]
        ]
        motivos.extend(
            {
                "origen": "validador_extraccion",
                "tipo": i["tipo"],
                "descripcion": i["detalle"],
                "campo": i["campo"],
            }
            for i in registro["incidencias"]
            if i["estado"] == "pendiente_revision"
        )
        nuevos = detectar_inconsistencias_fuente(por_id[cid])
        motivos.extend(nuevos)
        adicionales_fuente.extend(
            {"conversacion_id": cid, "empresa_id": registro["empresa_id"], **h}
            for h in nuevos
        )
        if motivos:
            descartadas.append(
                {
                    "conversacion_id": cid,
                    "empresa_id": registro["empresa_id"],
                    "lead_id": registro["lead_id"],
                    "lead_consolidado_id": registro["lead_consolidado_id"],
                    "estado": "descartada_del_conjunto_utilizable",
                    "politica": POLITICA_DESCARTE,
                    "motivos": motivos,
                    "conversacion_original": por_id[cid],
                    "extraccion_original": registro,
                }
            )
        else:
            aprobadas.append(registro)
    ids_aprobadas = {r["extraccion"]["conversacion_id"] for r in aprobadas}
    ids_descartadas = {r["conversacion_id"] for r in descartadas}
    if (
        ids_aprobadas & ids_descartadas
        or ids_aprobadas | ids_descartadas != set(por_id)
    ):
        raise ValueError(
            "La partición debe conservar cada conversación ex"
            "actamente una vez."
        )
    if any(
        r["extraccion"]["inconsistencias"]
        or r["estado_extraccion"] == "requiere_revision"
        for r in aprobadas
    ):
        raise ValueError(
            "Se intentó conservar una extracción con inconsis"
            "tencias o pendientes."
        )
    contrato_final.validate_python(aprobadas)
    guardar(OUT / "resultados_utilizables.json", aprobadas)
    guardar(OUT / "conversaciones_descartadas.json", descartadas)
    guardar(
        OUT / "inconsistencias_adicionales_fuente.json", adicionales_fuente
    )
    guardar(destino / "extracciones_conversaciones_ia.json", aprobadas)
    guardar(
        destino / "extracciones_conversaciones_descartadas.json", descartadas
    )
    guardar(
        destino / "conversaciones_utilizables_ia.json",
        [c for c in conversaciones if c["conversacion_id"] in ids_aprobadas],
    )
    incidencias_con_decision = []
    for incidencia in incidencias_finales:
        nueva = copy.deepcopy(incidencia)
        if nueva.get("conversacion_id") in ids_descartadas:
            nueva["decision_registro"] = (
                "descartado_por_instruccion_del_usuario"
            )
        incidencias_con_decision.append(nueva)
    for d in descartadas:
        incidencias_con_decision.append(
            {
                "conversacion_id": d["conversacion_id"],
                "empresa_id": d["empresa_id"],
                "tipo": "descarte_por_inconsistencias",
                "estado": "excluido_por_decision_usuario",
                "politica": POLITICA_DESCARTE,
                "motivos": d["motivos"],
            }
        )
    guardar(
        destino / "incidencias_extraccion_ia.json", incidencias_con_decision
    )
    guardar(OUT / "incidencias_ia.json", incidencias_con_decision)
    revision.loc[revision["conversacion_id"].isin(ids_aprobadas)].to_csv(
        OUT / "revision_utilizables.csv", index=False, encoding="utf-8-sig"
    )
    pd.DataFrame(
        [
            {
                "conversacion_id": d["conversacion_id"],
                "empresa_id": d["empresa_id"],
                "lead_id": d["lead_id"],
                "motivos": " | ".join(
                    m.get("descripcion", "") for m in d["motivos"]
                ),
            }
            for d in descartadas
        ]
    ).to_csv(
        OUT / "revision_descartadas.csv", index=False, encoding="utf-8-sig"
    )
    resumen.update(
        conversaciones_extraidas=len(resultados),
        conversaciones_utilizables=len(aprobadas),
        conversaciones_descartadas=len(descartadas),
        politica_descarte=POLITICA_DESCARTE,
        registros_utilizables_con_campos_pendientes=0,
        incidencias=len(incidencias_con_decision),
        estado="extraccion_completa_filtrada_por_inconsistencias",
    )
    guardar(OUT / "resumen.json", resumen)
    manifest = json.loads(
        (destino / "manifest_extraccion_ia.json").read_text(encoding="utf-8")
    )
    manifest.update(resumen)
    manifest.update(
        registros_archivo_resultados=len(aprobadas),
        resultados_sha256=hashlib.sha256(
            (destino / "extracciones_conversaciones_ia.json").read_bytes()
        ).hexdigest(),
        incidencias_sha256=hashlib.sha256(
            (destino / "incidencias_extraccion_ia.json").read_bytes()
        ).hexdigest(),
        descartadas_sha256=hashlib.sha256(
            (
                destino / "extracciones_conversaciones_descartadas.json"
            ).read_bytes()
        ).hexdigest(),
        conversaciones_utilizables_sha256=hashlib.sha256(
            (destino / "conversaciones_utilizables_ia.json").read_bytes()
        ).hexdigest(),
    )
    guardar(destino / "manifest_extraccion_ia.json", manifest)
    for pendiente in pendientes_importes:
        pendiente["decision"] = "descartado_por_instruccion_del_usuario"
    guardar(OUT / "pendientes_importes.json", pendientes_importes)
    if cliente is not None:
        cliente.close()
    return manifest
