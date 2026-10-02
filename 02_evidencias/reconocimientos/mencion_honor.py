"""Subtipo MENCION_HONOR: menciones, premios, distinciones, becas, honores de graduacion y
demas reconocimientos declarados (decisiones del usuario, 2026-09-29).

- Un solo tipo para todo: el nombre ya dice que es (merito docente, beca, anios de servicio,
  cum laude, best paper...); no se clasifica por reglas.
- Una evidencia = persona + nombre casi identico (misma regla que capacitacion). Las veces que
  la recibio se cuentan en `n_veces` y cada fecha en que la recibio va en `fechas`. No hay
  `fecha_inicio`/`fecha_fin`: una mencion es un hecho puntual, no un periodo.
- Numeros en el nombre: uno sustantivo ("25 AÑOS", "NIVEL II") impide agrupar; uno de
  edicion u ocurrencia (un anio, "XV EDICION") no, y se conserva en `ediciones` (`es.numeros_en_nombre`).
- TIPO de la fuente: M = mencion, P = premio (confirmado por el usuario); va al texto si existe.
- Texto: "NOMBRE, Tipo: ..., Otorgado por: ..., Pais: ...". La institucion sin "ESPOL" (si
  solo era ESPOL se omite) y omitida si ya esta en el nombre; el pais solo si es del exterior.
- Nombres genericos ("DIPLOMA DE HONOR", "RECONOCIMIENTO") SI son evidencia: la institucion
  les da contexto.
- No son evidencia (quedan en `registros_no_considerados.csv`):
  - registros cuyo nombre de mencion es un nombre de persona (dato personal). Lista cerrada
    por IDMENCIONHONOR (`_NOMBRE_DE_PERSONA`) para no escribir los nombres en el codigo; en
    no considerados la descripcion queda vacia;
  - nombres sin tema ("N.A.").
"""
from __future__ import annotations

from collections import Counter

import pandas as pd

from evidencias import esquema as es
from evidencias.capacitacion.comun import _certificadores_texto
from evidencias.investigacion.ponencia import limpiar_nombre
from evidencias.investigacion.publicacion import _parecidos
from evidencias.reconocimientos.fuentes import ARCHIVO_MENCIONES

TIPO_ID = "MENCION_HONOR"
PREFIJO_ID = "REC-MEN"
TIPOS = {"M": "MENCIÓN", "P": "PREMIO"}

# Revisados con el usuario (2026-09-29): 21 registros de 2 personas
_NOMBRE_DE_PERSONA = {
    3161, 3496, 3497, 3498, 3499, 3500, 3501, 3502, 3534, 3535, 3536, 3537, 3538, 3539, 3540,
    3541, 3542, 3543, 3550, 3551, 3552,
}
_SIN_TEMA = {"", "N A"}

MOTIVO_NOMBRE_DE_PERSONA = "nombre de la mención es un nombre de persona (dato personal)"
MOTIVO_SIN_TEMA = "nombre sin tema"

def _agrupar(registros: list[dict]) -> list[list[dict]]:
    """Registros de UNA persona agrupados por nombre casi identico (misma regla que
    capacitacion) y con los mismos numeros sustantivos."""
    representantes: list[tuple[str, tuple]] = []
    grupo_de: dict[str, int] = {}
    for r in registros:
        clave = r["_CLAVE"]
        if clave not in grupo_de:
            sust = es.numeros_en_nombre(clave)[0]
            i = next((i for i, (rep, s) in enumerate(representantes) if s == sust and _parecidos(rep, clave)), None)
            if i is None:
                representantes.append((clave, sust))
                i = len(representantes) - 1
            grupo_de[clave] = i
    grupos: list[list[dict]] = [[] for _ in representantes]
    for r in registros:
        grupos[grupo_de[r["_CLAVE"]]].append(r)
    return grupos


def _texto(nombre: str, tipos: list[str], instituciones: list[str], paises_exterior: list[str]) -> str:
    partes = [nombre]
    if tipos:
        partes.append(f"Tipo: {'; '.join(t.lower() for t in tipos)}")
    if instituciones:
        partes.append(f"Otorgado por: {'; '.join(instituciones)}")
    if paises_exterior:
        partes.append(f"País: {'; '.join(p.title() for p in paises_exterior)}")
    return ", ".join(partes)


def construir(df: pd.DataFrame) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    """Devuelve (evidencias, reporte, registros_no_considerados)."""
    d = df.assign(_NOMBRE=df["NOMBREMENCION"].map(limpiar_nombre))
    d["_CLAVE"] = d["_NOMBRE"].map(es.normalizar_para_comparar)
    d["_MOTIVO"] = None
    d.loc[d["_CLAVE"].isin(_SIN_TEMA), "_MOTIVO"] = MOTIVO_SIN_TEMA
    d.loc[d["IDMENCIONHONOR"].isin(_NOMBRE_DE_PERSONA), "_MOTIVO"] = MOTIVO_NOMBRE_DE_PERSONA
    excluidos, v = d[d["_MOTIVO"].notna()], d[d["_MOTIVO"].isna()]

    por_persona: dict[int, list[dict]] = {}
    for r in v.to_dict("records"):
        por_persona.setdefault(int(r["IDPERSONA"]), []).append(r)

    filas = []
    for idp, registros in por_persona.items():
        for grupo in _agrupar(registros):
            grupo = sorted(grupo, key=lambda r: (pd.isna(r["FECHA"]), r["FECHA"] if pd.notna(r["FECHA"]) else 0))
            # El nombre mas frecuente; en empate, el primero que aparece
            nombre = Counter(r["_NOMBRE"] for r in grupo).most_common(1)[0][0]
            tipos = es.unicos(TIPOS.get(r["TIPO"]) for r in grupo)
            instituciones = es.unicos(es.limpiar_para_mostrar(r["INSTITUCION"]) for r in grupo)
            paises = es.unicos(es.texto_limpio(r["PAIS"]) for r in grupo)
            paises_exterior = [p for p in paises if p.upper() != "ECUADOR"]
            fechas = [r["FECHA"] for r in grupo if pd.notna(r["FECHA"])]
            atributos = {
                "nombre": nombre,
                "nombres_originales": es.unicos(es.limpiar_para_mostrar(r["NOMBREMENCION"]) for r in grupo),
                "ediciones": es.unicos(e for r in grupo for e in es.numeros_en_nombre(r["_CLAVE"])[1]),
                "tipos": tipos,
                "n_veces": len(grupo),
                "fechas": es.unicos(es.fecha_iso(f) for f in sorted(fechas)),
                "instituciones": instituciones,
                "paises": paises,
                "es_exterior": bool(paises_exterior),
                "tiene_archivo_respaldo": any(not es.valor_nulo(r["REFARCHIVO"]) for r in grupo),
                "_origen": {"fuente": ARCHIVO_MENCIONES.name,
                            "ids_mencion_honor": sorted(int(r["IDMENCIONHONOR"]) for r in grupo)},
            }
            filas.append(es.nueva_evidencia(
                es.generar_evidencia_id(PREFIJO_ID, idp, grupo[0]["_CLAVE"]), idp, TIPO_ID,
                _texto(nombre, tipos, _certificadores_texto(nombre, instituciones), paises_exterior),
                atributos,
            ))

    evidencias = es.a_dataframe(filas)
    no_considerados = pd.DataFrame({
        "persona_id": excluidos["IDPERSONA"].astype(int),
        "tipo_id": TIPO_ID,
        "motivo": excluidos["_MOTIVO"],
        "id_origen": excluidos["IDMENCIONHONOR"].astype(int),
        # el nombre de persona no se copia a ninguna salida
        "descripcion": excluidos["NOMBREMENCION"].map(es.limpiar_para_mostrar).where(
            excluidos["_MOTIVO"] != MOTIVO_NOMBRE_DE_PERSONA),
        "fecha": excluidos["FECHA"].map(es.fecha_iso),
    })
    n_veces = evidencias["atributos"].str.extract(r'"n_veces": (\d+)')[0].astype(int)
    reporte = {
        "registros_en_poblacion": len(d),
        "no_considerados_por_motivo": excluidos["_MOTIVO"].value_counts().to_dict(),
        "registros_sin_fecha": int(v["FECHA"].isna().sum()),
        "registros_sin_pais": int(v["PAIS"].isna().sum()),
        "registros_agrupados_en_otra_evidencia": int(len(v) - len(evidencias)),
        "evidencias": len(evidencias),
        "evidencias_recibidas_mas_de_una_vez": int((n_veces > 1).sum()),
    }
    return evidencias, reporte, no_considerados
