import { useState } from "react";
import type { Ambito, DimensionPersona } from "../api/client";
import { colorPatron } from "../lib/colores";
import { ModalDimensionPersona } from "./PatronesDimension";

const NOMBRE_AMBITO: Record<Ambito, string> = {
  todos: "todo el personal",
  administrativos: "el personal administrativo",
  docentes: "el personal docente",
};

// La persona en cada dimensión de evidencia: su puntaje frente al ámbito (percentil, DEC-053) y su
// patrón de actividad (DEC-055) con lo que lo describe. Clic en una dimensión: su detalle en una
// ventana (sus datos frente a su patrón, temas, evidencias), con la opción de ver todos los
// patrones de la dimensión o de ir a ella.
export default function IntensidadDimensiones({ ambito, dimensiones, personaId, nombrePersona, onPersona }: {
  ambito: Ambito;
  dimensiones: DimensionPersona[];
  /** sin persona, las filas no abren el detalle */
  personaId?: number;
  nombrePersona?: string;
  onPersona?: (id: number) => void;
}) {
  const [abierta, setAbierta] = useState<string | null>(null);
  if (!dimensiones.length) return <p className="text-xs text-slate-500">Esta versión de resultados no tiene dimensiones.</p>;
  const conDetalle = personaId !== undefined;

  return (
    <div>
      <p className="text-xs text-slate-500 mb-3">
        Barra y número: puntaje frente a {NOMBRE_AMBITO[ambito]} (85 = tanta o más evidencia registrada que el 85&nbsp;%; 0 = sin
        evidencias). A la derecha, su patrón en cada dimensión.{conDetalle && " Clic en una dimensión para ver su detalle."}
      </p>
      <ul className="space-y-0.5">
        {dimensiones.map((d) => {
          const sin = d.n_evidencias === 0;
          const fila = (
            <>
              <span className="grid grid-cols-[7.5rem_1fr_2rem_2.5rem] items-center gap-2">
                <span className="text-xs text-slate-700 truncate">{d.nombre}</span>
                <span className="h-2.5 bg-slate-100 rounded-sm overflow-hidden">
                  <span className="block h-full bg-espol-blue rounded-r-[4px]" style={{ width: `${d.intensidad}%` }} />
                </span>
                <span className={`text-xs tabular-nums text-right ${sin ? "text-slate-400" : "text-slate-800 font-medium"}`}>
                  {Math.floor(d.intensidad)}
                </span>
                <span className="text-[11px] text-right">
                  {d.patron ? (
                    <span className="inline-flex items-center gap-1 border rounded px-1 py-px bg-white text-slate-800">
                      <span className="w-2 h-2 rounded-full" style={{ background: colorPatron(d.patron.patron) }} />P{d.patron.patron + 1}
                    </span>
                  ) : (
                    <span className="text-slate-300">—</span>
                  )}
                </span>
              </span>
              {d.patron && (
                <span className="block text-[11px] text-slate-500 ml-[8rem] leading-snug">
                  {d.patron.etiqueta}
                  {d.patron.mixto && <span className="text-amber-700"> · entre dos patrones</span>}
                </span>
              )}
            </>
          );
          return (
            <li key={d.dimension}>
              {conDetalle ? (
                <button
                  type="button"
                  onClick={() => setAbierta(d.dimension)}
                  className="w-full text-left rounded px-1 -mx-1 py-1 hover:bg-slate-50"
                  title={`Ver su detalle en ${d.nombre}`}
                >
                  {fila}
                </button>
              ) : (
                <div className="py-1">{fila}</div>
              )}
            </li>
          );
        })}
      </ul>
      {abierta && conDetalle && (
        <ModalDimensionPersona
          ambito={ambito}
          personaId={personaId!}
          nombrePersona={nombrePersona ?? ""}
          dimension={abierta}
          onCerrar={() => setAbierta(null)}
          onPersona={onPersona}
        />
      )}
    </div>
  );
}
