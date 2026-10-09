import { useState } from "react";
import { de } from "../lib/texto";
import type { Ambito, DimensionPersona } from "../api/client";

const NOMBRE_AMBITO: Record<Ambito, string> = {
  todos: "todo el personal",
  administrativos: "el personal administrativo",
  docentes: "el personal docente",
};

// Intensidad (percentil 0-100 dentro del ámbito) en cada dimensión de evidencia (DEC-053).
// Barras independientes: no suman 100. Clic en una fila para ver de qué componentes sale.
export default function IntensidadDimensiones({ ambito, dimensiones }: { ambito: Ambito; dimensiones: DimensionPersona[] }) {
  const [abierta, setAbierta] = useState<string | null>(null);
  if (!dimensiones.length) return <p className="text-xs text-slate-500">Esta versión de resultados no tiene dimensiones.</p>;

  return (
    <div>
      <p className="text-xs text-slate-500 mb-3">
        Percentil frente a {NOMBRE_AMBITO[ambito]}: 85 significa que tiene tanta o más evidencia registrada que el 85&nbsp;% de
        las personas. Cada dimensión se mide por separado; 0 = sin evidencias registradas.
      </p>
      <ul className="space-y-1">
        {dimensiones.map((d) => {
          const desplegada = abierta === d.dimension;
          const sin = d.n_evidencias === 0;
          return (
            <li key={d.dimension}>
              <button
                type="button"
                onClick={() => setAbierta(desplegada ? null : d.dimension)}
                aria-expanded={desplegada}
                title={sin ? "Sin evidencias registradas" : d.componentes.map((c) => `${c.descripcion}: ${Math.round(c.valor * 100)}%`).join("\n")}
                className="w-full grid grid-cols-[7.5rem_1fr_2.5rem] items-center gap-2 py-1 rounded hover:bg-slate-50 text-left"
              >
                <span className="text-xs text-slate-700 truncate">{d.nombre}</span>
                <span className="h-2.5 bg-slate-100 rounded-sm overflow-hidden">
                  <span className="block h-full bg-espol-blue rounded-r-[4px]" style={{ width: `${d.intensidad}%` }} />
                </span>
                <span className={`text-xs tabular-nums text-right ${sin ? "text-slate-400" : "text-slate-800 font-medium"}`}>
                  {Math.floor(d.intensidad)}
                </span>
              </button>
              {desplegada && (
                <div className="ml-2 mb-2 mt-1 pl-3 border-l text-xs text-slate-600 space-y-0.5">
                  {d.patron && (
                    <div className="mb-2">
                      <p className="text-[11px] uppercase text-slate-500">Patrón de actividad (descubierto)</p>
                      <p className="text-slate-800">{d.patron.etiqueta}</p>
                      <p className="text-slate-500">
                        Lo comparte con {d.patron.tamano} de {d.patron.n_personas} personas con esta evidencia · afinidad{" "}
                        {Math.round(d.patron.afinidad * 100)}%
                      </p>
                      {d.patron.mixto && <p className="text-amber-700">También se parece mucho a: {d.patron.segundo}</p>}
                    </div>
                  )}
                  {d.temas.length > 0 && (
                    <div className="mb-2">
                      <p className="text-[11px] uppercase text-slate-500">Temas principales (descubiertos)</p>
                      {d.temas.map((t) => (
                        <p key={t.tema} className="flex justify-between gap-3">
                          <span>{t.etiqueta}</span>
                          <span className="tabular-nums">{Math.round(t.proporcion * 100)}% de sus evidencias</span>
                        </p>
                      ))}
                    </div>
                  )}
                  <p className="text-slate-500">
                    {d.n_evidencias} evidencia{d.n_evidencias === 1 ? "" : "s"}. Aporte de cada componente (100 % = el valor más alto {de(NOMBRE_AMBITO[ambito])}):
                  </p>
                  {d.componentes.map((c) => (
                    <p key={c.componente} className="flex justify-between gap-3">
                      <span>{c.descripcion}</span>
                      <span className="tabular-nums">{Math.round(c.valor * 100)}%</span>
                    </p>
                  ))}
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
