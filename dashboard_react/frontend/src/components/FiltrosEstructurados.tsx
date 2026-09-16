export const VIGENCIA_OPTS = ["Cualquiera", "Solo vigentes", "Solo no vigentes"];

// TURBULENCIA_TRAMOS es un coeficiente de variación (desviación estándar / promedio de la
// duración de sus cargos en ESPOL) - NO mide cuántas veces cambió de cargo (eso es
// N_TRANSICIONES_ROL, otra columna), mide qué tan DESIGUAL es la duración de sus cargos
// entre sí: alguien con 10 cargos de 2 años cada uno tiene turbulencia baja (todos duraron
// igual) aunque cambió 10 veces; alguien con 2 cargos, uno de 8 años y otro de 3 meses,
// tiene turbulencia alta aunque cambió una sola vez. Por eso NO se llama "rotación" ni
// "variable" en la UI (el usuario 2026-09-16 interpretó "Variable" como "cambia mucho de
// cargo", que es exactamente lo que este número no mide). Categorías traducidas a
// percentiles reales de la población (ver notebooks/01_preprocesamiento: p25=0.67,
// mediana=1.08, p75=1.4).
export const ESTABILIDAD_OPTS: { label: string; value: number; ayuda: string }[] = [
  { label: "Sin límite", value: 0, ayuda: "No filtra por esto." },
  {
    label: "Muy estable",
    value: 0.67,
    ayuda: "Entre el 25% de personas cuyos cargos duraron todos tiempos parecidos entre sí (sin mezclar uno muy largo con otro muy corto).",
  },
  {
    label: "Estable",
    value: 1.08,
    ayuda: "Criterio promedio de la población (mediana) — ni muy estricto ni muy permisivo.",
  },
  {
    label: "Irregular",
    value: 1.4,
    ayuda: "Permite hasta el 75% de la población — solo descarta a quienes mezclan cargos muy largos con cargos muy cortos.",
  },
];

export interface FiltrosEstructuradosState {
  vigencia: string;
  setVigencia: (v: string) => void;
  tipoSel: string[];
  setTipoSel: (v: string[]) => void;
  nivelSel: string[];
  setNivelSel: (v: string[]) => void;
  minPub: number;
  setMinPub: (v: number) => void;
  minExpAdmin: number;
  setMinExpAdmin: (v: number) => void;
  maxIrregularidad: number;
  setMaxIrregularidad: (v: number) => void;
  minDuracionMediana: number;
  setMinDuracionMediana: (v: number) => void;
  minCargosEspol: number;
  setMinCargosEspol: (v: number) => void;
  maxCargosEspol: number;
  setMaxCargosEspol: (v: number) => void;
}

interface Props {
  state: FiltrosEstructuradosState;
  opcionesTipo: string[];
  opcionesNivel: string[];
}

/** Bloque de filtros estructurados (perfil, vigencia, tipo, nivel, publicaciones,
 * experiencia administrativa, estabilidad de carrera) compartido entre "Formar equipos"
 * (`EquiposPage`) y "Búsqueda combinada" (`BusquedaCombinadaPage`) — misma UI en ambas
 * pantallas, un solo lugar para mantenerla consistente. */
export default function FiltrosEstructurados({ state: s, opcionesTipo, opcionesNivel }: Props) {
  function toggleMulti(list: string[], setList: (v: string[]) => void, value: string) {
    setList(list.includes(value) ? list.filter((x) => x !== value) : [...list, value]);
  }

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4 space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1.5">Vigencia</p>
          <select
            value={s.vigencia}
            onChange={(e) => s.setVigencia(e.target.value)}
            className="w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-espol-blue"
          >
            {VIGENCIA_OPTS.map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1.5">Tipo de empleado</p>
          <div className="flex flex-wrap gap-1.5">
            {opcionesTipo.map((t) => (
              <button
                key={t}
                onClick={() => toggleMulti(s.tipoSel, s.setTipoSel, t)}
                className={`px-2 py-1 text-xs rounded-md border transition-colors ${
                  s.tipoSel.includes(t) ? "bg-espol-blue text-white border-espol-blue" : "border-slate-300 text-slate-600 hover:bg-slate-50"
                }`}
              >
                {t}
              </button>
            ))}
          </div>
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1.5">Nivel académico máximo</p>
          <div className="flex flex-wrap gap-1.5 max-h-20 overflow-y-auto">
            {opcionesNivel.map((n) => (
              <button
                key={n}
                onClick={() => toggleMulti(s.nivelSel, s.setNivelSel, n)}
                className={`px-2 py-1 text-xs rounded-md border transition-colors ${
                  s.nivelSel.includes(n) ? "bg-espol-blue text-white border-espol-blue" : "border-slate-300 text-slate-600 hover:bg-slate-50"
                }`}
              >
                {n}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1.5">Mínimo de publicaciones</p>
          <input
            type="number"
            min={0}
            value={s.minPub}
            onChange={(e) => s.setMinPub(Number(e.target.value))}
            className="w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-espol-blue"
          />
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1.5">Mínimo de años de experiencia administrativa</p>
          <input
            type="number"
            min={0}
            step={0.5}
            value={s.minExpAdmin}
            onChange={(e) => s.setMinExpAdmin(Number(e.target.value))}
            className="w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-espol-blue"
          />
        </div>
      </div>

      <div className="border-t border-slate-100 pt-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1.5">Estabilidad de carrera</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <label className="text-xs text-slate-500 block mb-1">Regularidad en la duración de sus cargos</label>
            <select
              value={s.maxIrregularidad}
              onChange={(e) => s.setMaxIrregularidad(Number(e.target.value))}
              className="w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-espol-blue"
            >
              {ESTABILIDAD_OPTS.map((o) => (
                <option key={o.label} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
            <p className="text-xs text-slate-400 mt-1">
              {ESTABILIDAD_OPTS.find((o) => o.value === s.maxIrregularidad)?.ayuda}
              {" "}No mide cuántas veces cambió de cargo, sino si sus cargos duraron tiempos
              parecidos entre sí. Personas con un solo cargo en toda su carrera siempre pasan
              este filtro.
            </p>
          </div>
          <div>
            <label className="text-xs text-slate-500 block mb-1">Mínimo de años de permanencia típica por cargo</label>
            <input
              type="number"
              min={0}
              step={0.5}
              value={s.minDuracionMediana}
              onChange={(e) => s.setMinDuracionMediana(Number(e.target.value))}
              className="w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-espol-blue"
            />
            <p className="text-xs text-slate-400 mt-1">
              Duración mediana de sus cargos en ESPOL — filtra directamente cargos cortos (ej. 2-3
              meses) al exigir un mínimo, sin depender del texto de búsqueda.
            </p>
          </div>
          <div>
            <label className="text-xs text-slate-500 block mb-1">Mínimo de cargos distintos en ESPOL (0 = sin límite)</label>
            <input
              type="number"
              min={0}
              step={1}
              value={s.minCargosEspol}
              onChange={(e) => s.setMinCargosEspol(Number(e.target.value))}
              className="w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-espol-blue"
            />
            <p className="text-xs text-slate-400 mt-1">
              Cantidad de cargos distintos que tuvo en ESPOL (administrativo, docente u otros),
              contados por tramo real (renovaciones y periodos académicos consecutivos ya
              fusionados) — útil para exigir experiencia en varios cargos, no uno solo.
            </p>
          </div>
          <div>
            <label className="text-xs text-slate-500 block mb-1">Máximo de cargos distintos en ESPOL (0 = sin límite)</label>
            <input
              type="number"
              min={0}
              step={1}
              value={s.maxCargosEspol}
              onChange={(e) => s.setMaxCargosEspol(Number(e.target.value))}
              className="w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-espol-blue"
            />
            <p className="text-xs text-slate-400 mt-1">
              Descarta a quienes se han movido de cargo demasiadas veces. Personas con un solo
              cargo en toda su carrera siempre pasan este filtro (1 cargo ≤ cualquier máximo).
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
