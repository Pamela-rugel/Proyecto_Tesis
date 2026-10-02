import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { buscarPersonas, type Ambito, type ResultadoBusqueda } from "../api/client";
import { colorCluster } from "../lib/colores";

interface Props {
  ambito: Ambito;
  onElegir: (r: ResultadoBusqueda) => void;
}

// Busca personas vigentes del ámbito por nombre, cargo o unidad.
export default function BuscadorPersonas({ ambito, onElegir }: Props) {
  const [texto, setTexto] = useState("");
  const [consulta, setConsulta] = useState("");
  const [abierto, setAbierto] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setConsulta(texto.trim()), 250);
    return () => clearTimeout(t);
  }, [texto]);

  const { data, isFetching } = useQuery({
    queryKey: ["buscar", ambito, consulta],
    queryFn: () => buscarPersonas(ambito, consulta),
    enabled: consulta.length >= 2,
  });

  return (
    <div className="relative w-full">
      <input
        value={texto}
        onChange={(e) => {
          setTexto(e.target.value);
          setAbierto(true);
        }}
        onFocus={() => setAbierto(true)}
        onBlur={() => setTimeout(() => setAbierto(false), 150)}
        placeholder="Buscar persona por nombre, cargo o unidad…"
        className="w-full border rounded-md px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-espol-blue/40"
      />
      {abierto && consulta.length >= 2 && (
        <div className="absolute z-40 mt-1 w-full bg-white border rounded-md shadow-lg max-h-80 overflow-y-auto">
          {isFetching && !data && <p className="text-xs text-slate-500 p-3">Buscando…</p>}
          {data?.length === 0 && <p className="text-xs text-slate-500 p-3">Sin resultados entre las personas vigentes.</p>}
          {data?.map((r) => (
            <button
              key={r.persona_id}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => {
                onElegir(r);
                setAbierto(false);
              }}
              className="w-full text-left px-3 py-2 hover:bg-slate-50 border-b last:border-b-0"
            >
              <p className="text-sm font-medium text-slate-800">{r.nombre}</p>
              <p className="text-xs text-slate-500 truncate">
                {r.cargo_actual ?? "Sin cargo actual"}
                {r.unidad_actual ? ` · ${r.unidad_actual}` : ""}
              </p>
              <p className="text-[11px] text-slate-500 flex items-center gap-1">
                <span className="w-2 h-2 rounded-full" style={{ background: colorCluster(r.cluster) }} />
                Patrón {r.cluster} · {r.etiqueta}
              </p>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
