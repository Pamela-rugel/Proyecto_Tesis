"""Capa temporal normalizada: intervalos de cada evidencia (DISENO.md §4.4).

Las fechas están dentro de `atributos` con formatos distintos por tipo. Aquí se convierten a una
lista de intervalos [inicio, fin] con una precisión:

    dia        fechas exactas (trayectoria, proyectos, capacitaciones, ponencias)
    semestre   periodos académicos "AAAA-1S/2S/0S" (materias dictadas). APROXIMACIÓN declarada:
               1S = abr–sep, 2S = oct–mar del año siguiente, 0S = ene–mar, "AAAA-MOD" o "AAAA"
               = el año completo
    anio       solo años (actividades de carga, publicaciones): cada año = ene–dic
    solo_fin   solo la fecha de fin (títulos, tesis dirigidas): no sirve para duraciones
    puntual    fechas sueltas (menciones)
    sin_fecha  idiomas, formación en curso

Un intervalo sin fecha de fin se cierra en HOY solo si la persona es vigente (VIGENTE_ACTUALMENTE,
DEC-047..049); si no, se marca como abierto y no se cuenta (el atributo `vigente` de las
evidencias está inflado y no se usa).
"""
from __future__ import annotations

import re
from datetime import date

HOY = date.today()
_SEMESTRE = re.compile(r"^(\d{4})(?:-(1S|2S|0S|MOD))?$")


def _fecha(s) -> date | None:
    if not s or not isinstance(s, str):
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def _semestre(p: str) -> tuple[date, date] | None:
    m = _SEMESTRE.match(str(p).strip())
    if not m:
        return None
    anio, sem = int(m.group(1)), m.group(2)
    if sem == "1S":
        return date(anio, 4, 1), date(anio, 9, 30)
    if sem == "2S":
        return date(anio, 10, 1), date(anio + 1, 3, 31)
    if sem == "0S":
        return date(anio, 1, 1), date(anio, 3, 31)
    return date(anio, 1, 1), date(anio, 12, 31)


def intervalos(tipo: str, a: dict, persona_vigente: bool) -> tuple[list[tuple[date, date]], str, bool]:
    """(intervalos, precision, hay_abierto_no_contado) de una evidencia."""
    abierto = False
    salida: list[tuple[date, date]] = []

    def agregar(ini, fin):
        nonlocal abierto
        if ini is None:
            return
        if fin is None:
            if persona_vigente:
                fin = HOY
            else:
                abierto = True
                return
        if fin >= ini:
            salida.append((ini, min(fin, HOY)))

    if tipo == "DOCENCIA_MATERIA":
        for p in a.get("periodos") or []:
            iv = _semestre(p)
            if iv:
                salida.append(iv)
        return salida, "semestre" if salida else "sin_fecha", False
    if tipo in ("ACTIVIDAD_CARGA", "PUBLICACION"):
        for y in a.get("anios") or []:
            try:
                salida.append((date(int(y), 1, 1), date(int(y), 12, 31)))
            except (TypeError, ValueError):
                pass
        return salida, "anio" if salida else "sin_fecha", False
    if tipo == "MENCION_HONOR":
        for f in a.get("fechas") or []:
            d = _fecha(f)
            if d:
                salida.append((d, d))
        return salida, "puntual" if salida else "sin_fecha", False
    if tipo in ("FORMACION_TITULO", "TESIS_DIRIGIDA"):
        d = _fecha(a.get("fecha_fin"))
        return ([(d, d)] if d else []), ("solo_fin" if d else "sin_fecha"), False
    if tipo in ("IDIOMA", "FORMACION_EN_CURSO"):
        return [], "sin_fecha", False

    periodos = a.get("periodos")
    if isinstance(periodos, list) and periodos and isinstance(periodos[0], dict):
        for p in periodos:
            agregar(_fecha(p.get("inicio")), _fecha(p.get("fin")))
    else:
        agregar(_fecha(a.get("fecha_inicio")), _fecha(a.get("fecha_fin")))
    return salida, ("dia" if salida else ("sin_fecha" if not abierto else "dia")), abierto


def anios_union(intervalos_: list[tuple[date, date]]) -> float:
    """Años cubiertos por la UNIÓN de intervalos (periodos simultáneos no se cuentan dos veces)."""
    if not intervalos_:
        return 0.0
    orden = sorted(intervalos_)
    total, (ini, fin) = 0, orden[0]
    for a, b in orden[1:]:
        if a <= fin:
            fin = max(fin, b)
        else:
            total += (fin - ini).days + 1
            ini, fin = a, b
    total += (fin - ini).days + 1
    return round(total / 365.25, 2)


def rango_texto(intervalos_: list[tuple[date, date]], precision: str) -> str:
    """Texto corto para la explicación: '2019–2023', '2015-1S … 2018-2S', 'sin fecha'."""
    if not intervalos_:
        return "sin fecha"
    ini, fin = min(i for i, _ in intervalos_), max(f for _, f in intervalos_)
    if precision in ("solo_fin", "puntual"):
        return str(fin.year)
    if fin >= HOY:
        return f"{ini.year}–actualidad"
    return f"{ini.year}" if ini.year == fin.year else f"{ini.year}–{fin.year}"
