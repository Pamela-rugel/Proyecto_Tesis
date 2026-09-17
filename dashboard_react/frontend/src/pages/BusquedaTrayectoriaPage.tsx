import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { buscarAvanzadaTrayectoria, getEquipos } from "../api/client";
import { LoadingBlock, ErrorBlock } from "../components/LoadingBlock";
import PersonaFicha from "../components/PersonaFicha";
import FiltrosEstructurados from "../components/FiltrosEstructurados";
import type { ResultadoAvanzado } from "../api/client";

const EJEMPLOS = [
  "permanencia larga y estabilidad en un mismo cargo",
  "movilidad entre cargos y unidades distintas",
  "trayectoria concentrada en una sola unidad",
];

// Pagina exploratoria (capa de comparacion, no reemplaza "Busqueda combinada"): mismos
// filtros estructurados que /api/buscar_avanzado, pero el ranking semantico usa el
// embedding de TRAYECTORIA (cargo/unidad/permanencia/estabilidad/movilidad) en vez del
// embedding general (temas/conocimiento/formacion/produccion academica) - ver
// notebooks/07_embeddings/07_embeddings.ipynb, seccion 7.
export default function BusquedaTrayectoriaPage() {
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

  const opcionesQuery = useQuery({ queryKey: ["equipos-opciones"], queryFn: () => getEquipos({
    vigencia: "Cualquiera", tipo: [], nivel: [], minPublicaciones: 0,
    minExpAdmin: 0, maxIrregularidad: 0, minDuracionMediana: 0, minCargosEspol: 0, maxCargosEspol: 0,
  }) });

  const mutation = useMutation({
    mutationFn: () =>
      buscarAvanzadaTrayectoria({
        consulta, topN, vigencia, tipo: tipoSel, nivel: nivelSel,
        minPublicaciones: minPub, minExpAdmin, maxIrregularidad, minDuracionMediana,
        minCargosEspol, maxCargosEspol,
      }),
    onSuccess: () => setSeleccion(null),
  });

  function buscar() {
    if (!consulta.trim()) return;
    mutation.mutate();
  }

  return (
    <div className="space-y-5">
      <div className="bg-white rounded-xl border border-amber-200 bg-amber-50/60 p-4">
        <p className="text-xs text-amber-800 font-medium">
          Vista exploratoria — el orden de resultados aquí se basa únicamente en el patrón de
          TRAYECTORIA (cargo, unidad, permanencia, estabilidad, movilidad), no en temas o
          conocimiento. Útil para comparar contra "Búsqueda combinada" (que sí usa
          conocimiento/formación/producción académica).
        </p>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-4">
        <h3 className="font-semibold text-sm mb-1 text-slate-700">
          Describe el patrón de trayectoria que buscas, y aplica filtros estructurados
        </h3>
        <p className="text-sm text-slate-500 mb-2">
          A diferencia de "Búsqueda combinada" (que ordena por afinidad temática/de
          conocimiento), aquí se ordena por afinidad al patrón de CARRERA de la persona:
          permanencia, cambios de cargo, cambios de unidad, estabilidad — no por lo que sabe
          o investiga.
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
            placeholder="Ej: permanencia larga y estabilidad en un mismo cargo"
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
            ordenadas por afinidad de TRAYECTORIA a tu consulta (no por tema/conocimiento).
            Selecciona una fila para ver el perfil profesional completo.
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
                  <th className="text-left px-3 py-2 font-medium text-xs uppercase tracking-wide text-slate-500">Por qué coincide (trayectoria)</th>
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
                      Nadie cumple los filtros estructurados aplicados, o no tiene embedding de
                      trayectoria (sin tramo de rol estructural) — prueba con criterios menos
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
            origenBusqueda="trayectoria"
          />
        </div>
      )}
    </div>
  );
}
