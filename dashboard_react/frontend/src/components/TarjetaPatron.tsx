import type { ReactNode } from "react";
import type { Patron } from "../api/client";
import { colorPatron } from "../lib/colores";
import { ComponentesPatron } from "./DetallePersona";

// Tarjeta de un patrón de actividad de una dimensión (DEC-055): lo que lo distingue frente al
// promedio de la dimensión, las barras de sus componentes y su persona más representativa.
export default function TarjetaPatron({ patron, seleccionado, onClick, onPersona, nombreDimension, pie }: {
  patron: Patron;
  seleccionado: boolean;
  onClick: () => void;
  /** sin él, la persona representativa se muestra sin enlace */
  onPersona?: (id: number) => void;
  nombreDimension: string;
  /** contenido extra al pie (p. ej. cómo se reparte un patrón global en él) */
  pie?: ReactNode;
}) {
  return (
    <div className={`border rounded-md p-3 bg-white ${seleccionado ? "border-espol-blue ring-1 ring-espol-blue" : "hover:border-slate-300"}`}>
      <button onClick={onClick} className="w-full text-left" aria-pressed={seleccionado}>
        <div className="flex items-baseline gap-2">
          <span className="w-2.5 h-2.5 rounded-full shrink-0 self-center" style={{ background: colorPatron(patron.id) }} />
          <span className="text-sm font-semibold text-slate-800 flex-1">Patrón {patron.id + 1}</span>
          <span className="text-xs text-slate-500 tabular-nums">
            {patron.tamano_vigentes} vigentes · {patron.tamano} en total
          </span>
        </div>
        <div className="mt-2">
          <ComponentesPatron componentes={patron.componentes} nombreDimension={nombreDimension} />
        </div>
      </button>
      {patron.representante_id !== null && (
        <p className="text-[11px] text-slate-500 mt-2">
          Persona más representativa:{" "}
          {onPersona ? (
            <button className="text-espol-blue hover:underline" onClick={() => onPersona(patron.representante_id!)}>
              {patron.representante_nombre}
            </button>
          ) : (
            <span className="text-slate-700">{patron.representante_nombre}</span>
          )}
        </p>
      )}
      {pie}
    </div>
  );
}
