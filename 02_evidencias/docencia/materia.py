"""Subtipo DOCENCIA_MATERIA: materias que la persona dicto (decisiones del usuario, 2026-09-30).

- Una evidencia = persona + nombre de materia casi identico (similitud >= 0.95) y con los
  mismos numeros sustantivos (`es.numeros_en_nombre`: "CALCULO I" y "CALCULO II" son
  evidencias distintas). El codigo cambia con la malla (MECG1022 -> MECG1043 para la misma
  materia): los codigos van en una lista.
- Cada semestre en que la dicto es un periodo ("2021-1S"; 0S = intensivo). Sin
  `fecha_inicio`/`fecha_fin`: dictar una materia en semestres salteados no es un periodo
  continuo; los semestres van en `periodos`.
- TIPOCURSO: P = paralelo principal, G = componente practico (paralelos 101, 102...).
  Interpretacion del usuario, coherente con los datos: ninguna materia tiene solo G y las
  que no tienen practica (Investigacion I, Comunicacion I) solo tienen P. No indica grado o
  posgrado. Va en `componentes`, no en el texto.
- Estudiantes: una sola vez por paralelo principal (el practico tiene los mismos); si en un
  periodo solo dicto el practico, se cuentan los del practico.
- Texto: "MATERIA, UNIDAD (SIGLA)", la unidad sin "ESPOL" (si era ESPOL misma, se omite).
- No son evidencia (quedan en `registros_no_considerados.csv`): cursos que empiezan despues
  de la fecha de corte, cursos sin nombre de materia y, desde 2015, cursos sin APROBADO = S en
  ningun extracto. Antes de 2015 APROBADO vale N en el 100 % de los cursos: solo se registraban
  los aprobados, asi que todos cuentan (usuario, 2026-09-30).
- Paréntesis final del nombre ("MÉTODOS NUMÉRICOS (2005)", "CONTABILIDAD GUBERNAMENTAL (AUDIT.)"):
  marca malla, carrera o jornada, no otra materia. Se quita del nombre y del texto y se guarda
  en `variantes`; el nombre tal cual queda en `nombres_originales`.
- Periodos: "2021-1S", "2021-2S", "2021-0S" (intensivo), "2005-MOD" (modulo corto de CELEX o
  de los programas de tecnologia) o solo el anio si la fuente no trae fechas (2002-2003).
"""
from __future__ import annotations

import re
from collections import Counter

import pandas as pd

from evidencias import esquema as es
from evidencias.investigacion.ponencia import limpiar_nombre
from evidencias.investigacion.proyecto_investigacion import sigla_de_unidad
from evidencias.investigacion.publicacion import _agrupar_titulos

TIPO_ID = "DOCENCIA_MATERIA"
PREFIJO_ID = "DOC-MAT"
COMPONENTES = {"P": "PRINCIPAL", "G": "PRACTICO"}

MOTIVO_INICIO_FUTURO = "curso que empieza después de la fecha de corte"
MOTIVO_NO_APROBADO = "carga no aprobada (desde 2015, APROBADO distinto de S)"
ANIO_INICIO_APROBACION = 2015
MOTIVO_SIN_NOMBRE = "curso sin nombre de materia"


_PARENTESIS_FINAL = re.compile(r"^(.*?)\s*\(\s*([^()]*?)\s*\)\s*$")


def _separar_variante(nombre) -> tuple[str | None, str | None]:
    """("MÉTODOS NUMÉRICOS (2005)") -> ("MÉTODOS NUMÉRICOS", "2005"). El paréntesis final marca
    la malla, carrera, jornada o programa para el que se dictó (2005, AUDIT., IAL, IIT95, TN…),
    no una materia distinta (usuario, 2026-09-30). Si no hay nada antes del paréntesis, el nombre
    se deja como está."""
    t = es.limpiar_para_mostrar(nombre)
    m = _PARENTESIS_FINAL.match(t) if t else None
    if not m or not m.group(1).strip() or not m.group(2):
        return t, None
    return m.group(1).strip(), m.group(2)


def _unidad(r, siglas: dict) -> dict | None:
    nombre = es.limpiar_para_mostrar(r["NOMBREUNIDAD"])
    if not nombre:
        return None
    sigla = sigla_de_unidad(nombre, siglas) or es.texto_limpio(r["CODUNIDAD"])
    return {"unidad": nombre, "sigla": sigla}


def _unidad_texto(u: dict) -> str | None:
    nombre = es.quitar_espol(u["unidad"])
    if not nombre:
        return None  # la unidad era ESPOL misma
    sigla = u["sigla"]
    return f"{nombre} ({sigla})" if sigla and sigla.upper() not in nombre.upper().split() else nombre


def _periodo(p: pd.DataFrame) -> dict:
    """Un semestre de la persona en la materia (uno o varios paralelos)."""
    principales = p[p["TIPOCURSO"] == "P"]
    contados = principales if len(principales) else p
    porcentajes = [float(x) for x in p["PORC"].dropna()]
    return {
        "periodo": p["PERIODO"].iloc[0],
        "codigos": es.unicos(p["CODIGOMATERIA"]),
        "paralelos": sorted(es.unicos(str(x) for x in p["PARALELO"]), key=lambda x: (len(x), x)),
        "componentes": [COMPONENTES[t] for t in ("P", "G") if (p["TIPOCURSO"] == t).any()],
        "estudiantes": int(contados["NUMREGISTRADOS"].fillna(0).sum()),
        "porcentaje": min(porcentajes) if porcentajes else None,
        "tipos_profesor": es.unicos(p["TIPOPROFESOR"]),
        "termino_deducido": bool(p["TERMINO_DEDUCIDO"].any()),
        "ids_curso": sorted(int(x) for x in p["IDCURSO"]),
    }


def construir(cursos: pd.DataFrame, mapa_siglas: dict,
              fecha_corte: pd.Timestamp) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    """Devuelve (evidencias, reporte, registros_no_considerados)."""
    siglas = {es.normalizar_para_comparar(k): v for k, v in mapa_siglas.items()}
    partes = cursos["NOMMATERIA"].map(_separar_variante)
    d = cursos.assign(_NOMBRE=partes.str[0].map(limpiar_nombre), _VARIANTE=partes.str[1])
    d["_CLAVE"] = d["_NOMBRE"].map(lambda x: es.normalizar_para_comparar(x) if x else "")
    d["_MOTIVO"] = None
    # Antes de 2015 solo se registraban los cursos aprobados y APROBADO vale N en todos (valor
    # por defecto): cuentan todos. Desde 2015 solo cuenta APROBADO = S (usuario, 2026-09-30).
    d.loc[(d["ANIO"] >= ANIO_INICIO_APROBACION) & (d["APROBADO"] != "S"), "_MOTIVO"] = MOTIVO_NO_APROBADO
    d.loc[d["FECHA_INICIO"] > fecha_corte, "_MOTIVO"] = MOTIVO_INICIO_FUTURO
    d.loc[d["_CLAVE"] == "", "_MOTIVO"] = MOTIVO_SIN_NOMBRE
    excluidos, v = d[d["_MOTIVO"].notna()], d[d["_MOTIVO"].isna()]

    filas = []
    for idp, g in v.groupby("IDPERSONA", sort=False):
        for grupo in _agrupar_titulos(g, separar_por_numeros=True):
            grupo = grupo.sort_values(["FECHA_INICIO", "IDPERIODO"])
            periodos = [_periodo(p) for _, p in grupo.groupby("IDPERIODO", sort=False)]
            nombre = Counter(grupo["_NOMBRE"]).most_common(1)[0][0]
            unidades = []
            for _, r in grupo.iterrows():
                u = _unidad(r, siglas)
                if u and u not in unidades:
                    unidades.append(u)
            atributos = {
                "materia": nombre,
                "nombres_originales": es.unicos(grupo["NOMMATERIA"].map(es.limpiar_para_mostrar)),
                "variantes": es.unicos(grupo["_VARIANTE"]),
                "codigos": es.unicos(grupo["CODIGOMATERIA"]),
                "unidades": unidades,
                "componentes": [c for c in COMPONENTES.values() if any(c in p["componentes"] for p in periodos)],
                # Etiquetas sin repetir: varios modulos del mismo anio ("2005-MOD") o periodos sin
                # fechas ("2002") comparten etiqueta; cada uno sigue en `detalle_periodos`
                "n_periodos": len(es.unicos(p["periodo"] for p in periodos)),
                "periodos": es.unicos(p["periodo"] for p in periodos),
                "n_paralelos": sum(len(p["paralelos"]) for p in periodos),
                "n_estudiantes_total": sum(p["estudiantes"] for p in periodos),
                "es_compartida": any(p["porcentaje"] is not None and p["porcentaje"] < 100 for p in periodos),
                "tipos_profesor": es.unicos(t for p in periodos for t in p["tipos_profesor"]),
                "detalle_periodos": periodos,
                "_origen": {"fuentes": [f.name for f in _archivos(grupo)],
                            "ids_curso": sorted(int(x) for x in grupo["IDCURSO"])},
            }
            texto = ", ".join([nombre] + [t for t in (_unidad_texto(u) for u in unidades) if t])
            filas.append(es.nueva_evidencia(
                es.generar_evidencia_id(PREFIJO_ID, idp, grupo["_CLAVE"].iloc[0]), idp, TIPO_ID, texto, atributos,
            ))

    evidencias = es.a_dataframe(filas)
    no_considerados = pd.DataFrame({
        "persona_id": excluidos["IDPERSONA"].astype(int),
        "tipo_id": TIPO_ID,
        "motivo": excluidos["_MOTIVO"],
        "id_origen": excluidos["IDCURSO"].astype(int),
        "descripcion": excluidos["NOMMATERIA"].map(es.limpiar_para_mostrar),
        "periodo": excluidos["PERIODO"],
    })
    reporte = {
        "cursos_consolidados": len(d),
        "no_considerados_por_motivo": excluidos["_MOTIVO"].value_counts().to_dict(),
        "periodos_con_termino_deducido": sorted(v.loc[v["TERMINO_DEDUCIDO"], "PERIODO"].unique().tolist()),
        "cursos_sin_unidad": int(v["NOMBREUNIDAD"].isna().sum()),
        "evidencias": len(filas),
        "evidencias_con_componente_practico": sum('"PRACTICO"' in f["atributos"] for f in filas),
        "evidencias_compartidas": sum('"es_compartida": true' in f["atributos"] for f in filas),
    }
    return evidencias, reporte, no_considerados


def _archivos(grupo: pd.DataFrame):
    from evidencias.docencia.fuentes import ARCHIVOS_CARGA
    return [ARCHIVOS_CARGA[i - 1] for i in sorted({i for a in grupo["ARCHIVOS"] for i in a})]
