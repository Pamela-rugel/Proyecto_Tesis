import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { buscarAvanzada, getEquipos, getSeccionesBusqueda } from "../api/client";
import { LoadingBlock, ErrorBlock } from "../components/LoadingBlock";
import PersonaFicha from "../components/PersonaFicha";
import FiltrosEstructurados from "../components/FiltrosEstructurados";
import type { ResultadoAvanzado } from "../api/client";

const EJEMPLOS = [
  "conocimientos y experiencia en talento humano",
  "experiencia en gestión de proyectos de vinculación con la comunidad",
  "administración de servidores y redes",
];

export default function BusquedaCombinadaPage() {
  const [consulta, setConsulta] = useState("");
  const [topN, setTopN] = useState(10);
  const [seleccion, setSeleccion] = useState<ResultadoAvanzado | null>(null);

  const [vigencia, setVigencia] = useState("Cualquiera");
  const [tipoSel, setTipoSel] = useState<string[]>([]);
  const [nivelSel, setNivelSel] = useState<string[]>([]);
  const [minPub, setMinPub] = useState(0);
  const [minExpAdmin, setMinExpAdmin] = useState(0);
  const [maxIrregularidad, setMaxIrregularidad] = useState(0);
  const [minDuracionMediana, setMinDuracionMediana] = useState(0);
  const [minCargosEspol, setMinCargosEspol] = useState(0);
  const [maxCargosEspol, setMaxCargosEspol] = useState(0);
  const [seccionesSel, setSeccionesSel] = useState<string[]>([]);

  // Reutiliza /api/equipos solo para poblar las opciones de tipo/nivel del bloque de
  // filtros (mismas listas que "Formar equipos") — no dispara la búsqueda combinada.
  const opcionesQuery = useQuery({ queryKey: ["equipos-opciones"], queryFn: () => getEquipos({
    vigencia: "Cualquiera", tipo: [], nivel: [], minPublicaciones: 0,
    minExpAdmin: 0, maxIrregularidad: 0, minDuracionMediana: 0, minCargosEspol: 0, maxCargosEspol: 0,
  }) });

  const seccionesQuery = useQuery({ queryKey: ["secciones-busqueda"], queryFn: getSeccionesBusqueda });

  function toggleSeccion(clave: string) {
    setSeccionesSel((prev) => (prev.includes(clave) ? prev.filter((s) => s !== clave) : [...prev, clave]));
  }

  const mutation = useMutation({
    mutationFn: () =>
      buscarAvanzada({
        consulta, topN, vigencia, tipo: tipoSel, nivel: nivelSel,
        minPublicaciones: minPub, minExpAdmin, maxIrregularidad, minDuracionMediana,
        minCargosEspol, maxCargosEspol, secciones: seccionesSel,
      }),
    onSuccess: () => setSeleccion(null),
  });

  function buscar() {
    if (!consulta.trim()) return;
    mutation.mutate();
  }

  return (
    <div className="space-y-5">
      <div className="bg-white rounded-xl border border-slate-200 p-4">
        <h3 className="font-semibold text-sm mb-1 text-slate-700">
          Describe el conocimiento o experiencia que buscas, y aplica filtros estructurados
        </h3>
        <p className="text-sm text-slate-500 mb-2">
          A diferencia de "Formar equipos" (solo filtros), aquí describes libremente el conocimiento
          o experiencia que buscas y además aplicas filtros estructurados: primero se filtra por los
          criterios de abajo (cargos, permanencia, vigencia...) y luego se ordena por afinidad al
          texto SOLO entre quienes cumplen esos filtros — nadie que cumple los filtros se pierde por
          baja afinidad de texto.
        </p>
        <p className="text-xs text-slate-400 mb-3">
          Ejemplos: {EJEMPLOS.map((e) => `"${e}"`).join(" · ")}
        </p>

        <div className="flex flex-col sm:flex-row gap-2">
          <input
            type="text"
            value={consulta}
            onChange={(e) => setConsulta(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && buscar()}
            placeholder="Ej: conocimientos y experiencia en talento humano"
            className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-espol-blue"
          />
          <button
            onClick={buscar}
            disabled={mutation.isPending}
            className="px-4 py-2 text-sm rounded-md bg-espol-navy text-white hover:bg-espol-blue disabled:opacity-50 transition-colors"
          >
            Buscar
          </button>
        </div>
        <div className="flex flex-wrap items-center gap-3 mt-3">
          <label className="text-xs font-semibold text-slate-500">Número de resultados</label>
          <input
            type="range"
            min={3}
            max={25}
            value={topN}
            onChange={(e) => setTopN(Number(e.target.value))}
            className="w-40"
          />
          <span className="text-xs text-slate-600">{topN}</span>
        </div>

        <div className="mt-3">
          <label className="text-xs font-semibold text-slate-500 block mb-1.5">
            Buscar en (vacío = todo el perfil)
          </label>
          <p className="text-xs text-slate-400 mb-2">
            Sin nada seleccionado, se compara contra el perfil completo — si alguien tiene una
            trayectoria larga, un tema puntual (ej. "investigación en IA") puede diluirse entre el
            resto de su historial. Elige una o más secciones para comparar solo contra ese texto
            específico; con varias, se promedia la afinidad entre ellas.
          </p>
          <div className="flex flex-wrap gap-2">
            {seccionesQuery.data?.secciones.map((s) => {
              const activo = seccionesSel.includes(s.clave);
              return (
                <button
                  key={s.clave}
                  type="button"
                  onClick={() => toggleSeccion(s.clave)}
                  title={`${s.n_personas} personas tienen esta sección`}
                  className={`px-3 py-1 text-xs rounded-full border transition-colors ${
                    activo
                      ? "bg-espol-navy text-white border-espol-navy"
                      : "bg-white text-slate-600 border-slate-300 hover:border-espol-blue"
                  }`}
                >
                  {s.etiqueta}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      <FiltrosEstructurados
        state={{
          vigencia, setVigencia, tipoSel, setTipoSel,
          nivelSel, setNivelSel, minPub, setMinPub, minExpAdmin, setMinExpAdmin,
          maxIrregularidad, setMaxIrregularidad, minDuracionMediana, setMinDuracionMediana,
          minCargosEspol, setMinCargosEspol, maxCargosEspol, setMaxCargosEspol,
        }}
        opcionesTipo={opcionesQuery.data?.opciones.tipo_empleado ?? []}
        opcionesNivel={opcionesQuery.data?.opciones.nivel_academico ?? []}
      />

      {mutation.isPending && <LoadingBlock label="Buscando..." />}
      {mutation.isError && <ErrorBlock message="No se pudo completar la búsqueda." />}

      {mutation.data && (
        <div className="bg-white rounded-xl border border-slate-200 p-4">
          <p className="text-xs text-slate-500 mb-3">
            {mutation.data.n_candidatos_tras_filtros} personas cumplen los filtros estructurados —
            ordenadas del más al menos afín a tu consulta. Selecciona una fila para ver el perfil
            profesional completo.
          </p>
          <div className="overflow-auto rounded-lg border border-slate-200">
            <table className="min-w-full text-sm">
              <thead className="bg-slate-50">
                <tr>
                  <th className="text-left px-3 py-2 font-medium text-xs uppercase tracking-wide text-slate-500">#</th>
                  <th className="text-left px-3 py-2 font-medium text-xs uppercase tracking-wide text-slate-500">Nombre</th>
                  <th className="text-left px-3 py-2 font-medium text-xs uppercase tracking-wide text-slate-500">Vigente</th>
                  <th className="text-left px-3 py-2 font-medium text-xs uppercase tracking-wide text-slate-500">Cargo actual</th>
                  <th className="text-left px-3 py-2 font-medium text-xs uppercase tracking-wide text-slate-500">Cargos ESPOL</th>
                  <th className="text-left px-3 py-2 font-medium text-xs uppercase tracking-wide text-slate-500">Permanencia típica (años)</th>
                  <th className="text-left px-3 py-2 font-medium text-xs uppercase tracking-wide text-slate-500">Por qué coincide</th>
                </tr>
              </thead>
              <tbody>
                {mutation.data.resultados.map((r) => (
                  <tr
                    key={r.id_persona}
                    onClick={() => setSeleccion(r)}
                    className={`border-t border-slate-100 cursor-pointer transition-colors hover:bg-slate-50 ${
                      seleccion?.id_persona === r.id_persona ? "bg-espol-blue/5" : ""
                    }`}
                  >
                    <td className="px-3 py-2">{r.rango}</td>
                    <td className="px-3 py-2 font-medium">
                      <Link
                        to={`/persona/${r.id_persona}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        className="text-espol-blue hover:text-espol-navy transition-colors"
                      >
                        {r.nombre_completo}
                      </Link>
                    </td>
                    <td className="px-3 py-2">
                      <span
                        className={`px-2 py-0.5 text-xs rounded-full ${
                          r.vigente ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-500"
                        }`}
                      >
                        {r.vigente ? "Vigente" : "No vigente"}
                      </span>
                    </td>
                    <td className="px-3 py-2">{r.cargo_actual ?? "No vigente"}</td>
                    <td className="px-3 py-2">{r.n_cargos_espol ?? "-"}</td>
                    <td className="px-3 py-2">{r.duracion_mediana_tramo_anios ?? "-"}</td>
                    <td className="px-3 py-2 text-slate-500 max-w-md">{r.evidencia}</td>
                  </tr>
                ))}
                {mutation.data.resultados.length === 0 && (
                  <tr>
                    <td colSpan={7} className="px-3 py-4 text-center text-slate-400">
                      Nadie cumple los filtros estructurados aplicados — prueba con criterios menos
                      estrictos.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {seleccion && (
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <PersonaFicha
            idPersona={seleccion.id_persona}
            coincidenciaSemantica={{ rango: seleccion.rango, consulta: mutation.data?.consulta ?? consulta }}
          />
        </div>
      )}
    </div>
  );
}
