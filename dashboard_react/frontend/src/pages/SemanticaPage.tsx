import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { buscarSemantica } from "../api/client";
import { LoadingBlock, ErrorBlock } from "../components/LoadingBlock";
import PersonaFicha from "../components/PersonaFicha";
import type { BusquedaResultado } from "../api/types";

const EJEMPLOS = [
  "experiencia en aprendizaje automático aplicado a imágenes médicas",
  "persona que haya trabajado fuera de ESPOL en el extranjero",
  "administración de servidores y redes",
  "gestión de proyectos de vinculación con la comunidad",
];

const VIGENCIA_OPTS = ["Cualquiera", "Solo vigentes", "Solo no vigentes"];

export default function SemanticaPage() {
  const [consulta, setConsulta] = useState("");
  const [topN, setTopN] = useState(10);
  const [vigencia, setVigencia] = useState("Cualquiera");
  const [seleccion, setSeleccion] = useState<BusquedaResultado | null>(null);

  const mutation = useMutation({
    mutationFn: () => buscarSemantica(consulta, topN, vigencia),
    onSuccess: () => setSeleccion(null),
  });

  function buscar() {
    if (!consulta.trim()) return;
    mutation.mutate();
  }

  return (
    <div className="space-y-5">
      <div className="bg-white rounded-xl border border-slate-200 p-4">
        <h3 className="font-semibold text-sm mb-1 text-slate-700">Describe lo que buscas, en tus propias palabras</h3>
        <p className="text-sm text-slate-500 mb-2">
          A diferencia de "Buscar persona" (que requiere saber el IDPERSONA exacto), aquí describes
          libremente el conocimiento, experiencia o trayectoria que necesitas y el sistema encuentra a
          las personas más afines por significado, no por palabras clave exactas.
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
            placeholder="Ej: persona con experiencia en gestión de proyectos de vinculación con la comunidad"
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

          <label className="text-xs font-semibold text-slate-500 ml-4">Vigencia</label>
          <select
            value={vigencia}
            onChange={(e) => setVigencia(e.target.value)}
            className="rounded-md border border-slate-300 px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-espol-blue"
          >
            {VIGENCIA_OPTS.map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
        </div>
      </div>

      {mutation.isPending && <LoadingBlock label="Buscando..." />}
      {mutation.isError && <ErrorBlock message="No se pudo completar la búsqueda semántica." />}

      {mutation.data && (
        <div className="bg-white rounded-xl border border-slate-200 p-4">
          <p className="text-xs text-slate-500 mb-3">
            Ordenado del más al menos afín a tu consulta (no se muestra un puntaje de similitud: no es
            un porcentaje de relevancia interpretable de forma absoluta). Selecciona una fila para ver
            el perfil profesional completo.
          </p>
          <div className="overflow-auto rounded-lg border border-slate-200">
            <table className="min-w-full text-sm">
              <thead className="bg-slate-50">
                <tr>
                  <th className="text-left px-3 py-2 font-medium text-xs uppercase tracking-wide text-slate-500">#</th>
                  <th className="text-left px-3 py-2 font-medium text-xs uppercase tracking-wide text-slate-500">IDPERSONA</th>
                  <th className="text-left px-3 py-2 font-medium text-xs uppercase tracking-wide text-slate-500">Vigente</th>
                  <th className="text-left px-3 py-2 font-medium text-xs uppercase tracking-wide text-slate-500">Tipo empleado</th>
                  <th className="text-left px-3 py-2 font-medium text-xs uppercase tracking-wide text-slate-500">Cargo actual</th>
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
                    <td className="px-3 py-2 font-medium">{r.id_persona}</td>
                    <td className="px-3 py-2">
                      <span
                        className={`px-2 py-0.5 text-xs rounded-full ${
                          r.vigente ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-500"
                        }`}
                      >
                        {r.vigente ? "Vigente" : "No vigente"}
                      </span>
                    </td>
                    <td className="px-3 py-2">{r.tipo_empleado ?? "No vigente"}</td>
                    <td className="px-3 py-2">{r.cargo_actual ?? "No vigente"}</td>
                    <td className="px-3 py-2 text-slate-500 max-w-md">{r.evidencia}</td>
                  </tr>
                ))}
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
