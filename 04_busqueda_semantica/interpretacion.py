"""Interpretación automática de la consulta con un LLM (Groq), con salida JSON validada.

Solo se envía la consulta y el catálogo de tipos con ejemplos SINTÉTICOS (nunca datos de
personas). Modelo, temperatura 0 y `reasoning_effort="low"` fijos (reproducibilidad; sin "low"
la latencia era de 10–35 s y hubo salidas que no cumplían el esquema). Si el LLM no responde o
su salida no es válida, se usa el RESPALDO: la consulta completa como una sola capacidad buscada
en todos los tipos.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Literal

from pydantic import BaseModel, ValidationError

from busqueda.comun import BUSQUEDA_DIR, MODELO_LLM, MODELO_LLM_ALTERNO, TIPOS

TipoId = Literal[tuple(TIPOS)]  # type: ignore[valid-type]


class Reformulacion(BaseModel):
    tipo: TipoId
    texto: str


class Capacidad(BaseModel):
    id: str
    descripcion: str
    tema: str
    importancia: Literal["obligatoria", "deseable"]
    tipos: list[TipoId]
    reformulaciones: list[Reformulacion]


class Idioma(BaseModel):
    idioma: str
    nivel_minimo: Literal["basico", "intermedio", "avanzado"] | None


class RequisitosPersona(BaseModel):
    nivel_formacion_minimo: Literal["tercer_nivel", "maestria", "doctorado"] | None
    idiomas: list[Idioma]


class RequisitoMixto(BaseModel):
    capacidad: str
    anios_minimos: float


class Interpretacion(BaseModel):
    capacidades: list[Capacidad]
    requisitos_persona: RequisitosPersona
    requisitos_mixtos: list[RequisitoMixto]
    vigencia: Literal["vigentes", "no_vigentes", "todos", "no_especificada"]


def _esquema_estricto() -> dict:
    s = Interpretacion.model_json_schema()

    def ajustar(n):
        if isinstance(n, dict):
            if n.get("type") == "object" and "properties" in n:
                n["required"] = list(n["properties"])
                n["additionalProperties"] = False
            for v in n.values():
                ajustar(v)
        elif isinstance(n, list):
            for v in n:
                ajustar(v)
    ajustar(s)
    return s


_CATALOGO = "\n".join(f"- {t}: {d}. Formato de ejemplo: «{e}»" for t, (d, e) in TIPOS.items())
PROMPT_SISTEMA = f"""Eres el intérprete de consultas de un buscador de personal de una universidad (ESPOL).
Cada persona está descrita por EVIDENCIAS de estos tipos:
{_CATALOGO}

Convierte la consulta del usuario en JSON:
- capacidades: separa la consulta en capacidades INDEPENDIENTES (una por cada cosa distinta que se pide; si pide una sola cosa, una sola capacidad). Haber trabajado en una unidad, dependencia o institución concreta ("haya trabajado en la GTSI", "experiencia en el CIBE") es SIEMPRE una capacidad aparte, separada de cualquier conocimiento o tema que también se pida. Para cada capacidad:
  - id: "C1", "C2", … en orden.
  - descripcion: la capacidad en pocas palabras, en español, sin palabras de relleno ("experiencia en", "conocimiento de" solo si son parte del sentido).
  - tema: SOLO el tema o área de la capacidad, SIN palabras que indiquen el tipo de evidencia o actividad ("proyectos de investigación en", "docencia en cursos de", "experiencia en", "haber trabajado en" van fuera). Si el término técnico se usa también en inglés, agrégalo entre paréntesis. Ejemplos: "proyectos de investigación en acuicultura" → "acuicultura (aquaculture)"; "docencia en cursos de estadística" → "estadística"; "haya trabajado en el CIBE" → "Centro de Investigaciones Biotecnológicas del Ecuador (CIBE)". El tema debe ser tan general como lo pide la consulta (no lo especialices).
  - importancia: "obligatoria" salvo que la consulta la marque como opcional ("idealmente", "de preferencia", "sería un plus", "si es posible", "deseable") → "deseable".
  - tipos: los tipos de evidencia donde realmente se acreditaría esa capacidad (2 a 5, del más al menos pertinente). Para "experiencia" o "haber trabajado en", incluye los tipos de trayectoria (cargo de planta, contrato, función adicional, experiencia externa) y actividades de carga cuando apliquen. Una capacitación corta acredita menos "experiencia" que un cargo, un proyecto o una materia dictada.
  - reformulaciones: para cada tipo elegido, cómo se vería el TEXTO de una evidencia de ese tipo que la acredite, imitando el formato de ejemplo de ese tipo. Cada reformulación habla SOLO de su capacidad (no mezcles otras capacidades de la consulta) y no inventa nombres de personas ni instituciones concretas.
- requisitos_persona: SIEMPRE un objeto. nivel_formacion_minimo = null salvo que la consulta exija un nivel (doctorado, maestría…). Los IDIOMAS pedidos van SIEMPRE aquí (idioma en mayúsculas, p. ej. "INGLÉS", y su nivel mínimo), NUNCA como capacidad. Un requisito que va aquí NO se repite como capacidad.
- requisitos_mixtos: si la consulta pide una cantidad mínima de AÑOS para una capacidad, {{capacidad: id, anios_minimos}}. Si no, lista vacía.
- vigencia: "no_vigentes" si pide personas que ya no trabajan en la institución; "vigentes" si pide explícitamente personal actual; "todos" si pide ambos; si no dice nada, "no_especificada".
No agregues capacidades que la consulta no pide. Responde solo el JSON."""


def respaldo(consulta: str) -> Interpretacion:
    """Sin LLM: la consulta completa como una capacidad en todos los tipos (línea base)."""
    return Interpretacion(
        capacidades=[Capacidad(id="C1", descripcion=consulta.strip(), tema=consulta.strip(), importancia="obligatoria",
                               tipos=list(TIPOS), reformulaciones=[])],
        requisitos_persona=RequisitosPersona(nivel_formacion_minimo=None, idiomas=[]),
        requisitos_mixtos=[], vigencia="no_especificada")


def _archivo_cache():
    return BUSQUEDA_DIR / "cache_interpretaciones.json"


def _clave(consulta: str) -> str:
    base = json.dumps([MODELO_LLM, PROMPT_SISTEMA, consulta.strip().lower()], ensure_ascii=False)
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:20]


def interpretar(consulta: str, usar_llm: bool = True) -> tuple[Interpretacion, dict]:
    """(interpretación, meta). meta: fuente ('llm' | 'cache' | 'respaldo'), modelo, segundos, error."""
    if not usar_llm:
        return respaldo(consulta), {"fuente": "respaldo", "motivo": "LLM desactivado"}
    cache_f = _archivo_cache()
    cache = json.loads(cache_f.read_text(encoding="utf-8")) if cache_f.exists() else {}
    clave = _clave(consulta)
    if clave in cache:
        return Interpretacion.model_validate(cache[clave]), {"fuente": "cache", "modelo": MODELO_LLM}
    if not os.environ.get("GROQ_API_KEY"):
        return respaldo(consulta), {"fuente": "respaldo", "motivo": "falta GROQ_API_KEY"}

    from groq import Groq, RateLimitError

    cliente = Groq(timeout=60, max_retries=0)
    t0, error = time.time(), None
    # principal (con un reintento) → alterno → respaldo. Ante un 429 se espera lo que pide la API
    # (límite por minuto del plan gratuito), hasta 20 s.
    agotados: set[str] = set()
    for modelo in (MODELO_LLM, MODELO_LLM, MODELO_LLM_ALTERNO, MODELO_LLM_ALTERNO):
        if modelo in agotados:
            continue
        try:
            r = cliente.chat.completions.create(
                model=modelo, temperature=0, reasoning_effort="low",
                messages=[{"role": "system", "content": PROMPT_SISTEMA}, {"role": "user", "content": consulta}],
                response_format={"type": "json_schema",
                                 "json_schema": {"name": "interpretacion", "schema": _esquema_estricto(), "strict": True}})
            interp = Interpretacion.model_validate_json(r.choices[0].message.content)
            interp = _normalizar(interp)
            cache[clave] = interp.model_dump()
            BUSQUEDA_DIR.mkdir(parents=True, exist_ok=True)
            cache_f.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
            return interp, {"fuente": "llm", "modelo": modelo, "segundos": round(time.time() - t0, 1)}
        except ValidationError as e:
            error = f"salida no válida ({e.error_count()} errores)"
        except RateLimitError as e:
            if "per day" in str(e):  # cuota DIARIA agotada (TPD/RPD): esperar no sirve → siguiente modelo
                agotados.add(modelo)
                error = f"cuota diaria de Groq agotada para {modelo}"
                continue
            error = "límite por minuto de Groq (429)"
            espera = e.response.headers.get("retry-after") if e.response is not None else None
            time.sleep(min(float(espera or 10), 20))
        except Exception as e:  # noqa: BLE001 — cualquier fallo del servicio → respaldo
            error = f"{type(e).__name__}: {str(e)[:160]}"
    return respaldo(consulta), {"fuente": "respaldo", "motivo": error, "modelo": MODELO_LLM}


def _normalizar(i: Interpretacion) -> Interpretacion:
    """Ids C1..Cn coherentes (el LLM a veces usa otros nombres) y tipos sin repetir."""
    mapa = {}
    for n, c in enumerate(i.capacidades, 1):
        mapa[c.id] = f"C{n}"
        c.id = f"C{n}"
        c.tipos = list(dict.fromkeys(c.tipos)) or list(TIPOS)
    for m in i.requisitos_mixtos:
        m.capacidad = mapa.get(m.capacidad, m.capacidad)
    return i
