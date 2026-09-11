import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { getPersonasIds } from "../api/client";
import { LoadingBlock, ErrorBlock } from "../components/LoadingBlock";
import PersonaFicha from "../components/PersonaFicha";

export default function BuscarPage() {
  const { data: ids, isLoading, error } = useQuery({ queryKey: ["personas-ids"], queryFn: getPersonasIds });
  const [filtro, setFiltro] = useState("");
  const [idSel, setIdSel] = useState<number | null>(null);

  const filtrados = useMemo(() => {
    if (!ids) return [];
    if (!filtro.trim()) return ids.slice(0, 50);
    return ids.filter((id) => String(id).includes(filtro.trim())).slice(0, 50);
  }, [ids, filtro]);

  return (
    <div className="space-y-5">
      <div className="bg-white rounded-xl border border-slate-200 p-4">
        <h3 className="font-semibold text-sm mb-1 text-slate-700">Consulta directa por identificador</h3>
        <p className="text-sm text-slate-500 mb-3">
          Ya conoces el IDPERSONA (por ejemplo, desde el mapa de perfiles) y quieres ver su ficha
          completa. ¿Buscas a alguien por experiencia o conocimiento sin conocer su ID? Usa la pestaña
          "Búsqueda semántica" en su lugar.
        </p>

        {isLoading ? (
          <LoadingBlock label="Cargando lista de personas..." />
        ) : error || !ids ? (
          <ErrorBlock message="No se pudo cargar la lista de personas." />
        ) : (
          <div>
            <input
              type="text"
              value={filtro}
              onChange={(e) => setFiltro(e.target.value)}
              placeholder="Escribe un IDPERSONA..."
              className="w-full sm:w-72 rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-espol-blue"
            />
            <div className="mt-2 max-h-56 overflow-y-auto rounded-md border border-slate-200 divide-y divide-slate-100">
              {filtrados.map((id) => (
                <button
                  key={id}
                  onClick={() => setIdSel(id)}
                  className={`block w-full text-left px-3 py-1.5 text-sm hover:bg-slate-50 ${
                    idSel === id ? "bg-espol-blue/10 font-semibold" : ""
                  }`}
                >
                  {id}
                </button>
              ))}
              {filtrados.length === 0 && <p className="text-sm text-slate-400 px-3 py-2">Sin resultados.</p>}
            </div>
          </div>
        )}
      </div>

      {idSel !== null && (
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <PersonaFicha idPersona={idSel} mostrarEvidenciaTexto={false} />
        </div>
      )}
    </div>
  );
}
