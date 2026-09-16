import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { getEquipos } from "../api/client";
import { LoadingBlock, ErrorBlock } from "../components/LoadingBlock";
import DataTable from "../components/DataTable";
import FiltrosEstructurados from "../components/FiltrosEstructurados";
import { METRICAS_CLAVE_COLUMNS } from "../lib/columns";

const COLUMNAS_CANDIDATOS = METRICAS_CLAVE_COLUMNS.map((c) =>
  c.key === "NOMBRE_COMPLETO"
    ? {
        ...c,
        render: (row: Record<string, unknown>) => (
          <Link
            to={`/persona/${row.IDPERSONA}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-espol-blue hover:text-espol-navy font-medium transition-colors"
          >
            {String(row.NOMBRE_COMPLETO ?? "-")}
          </Link>
        ),
      }
    : c
);

export default function EquiposPage() {
  const [vigencia, setVigencia] = useState("Cualquiera");
  const [tipoSel, setTipoSel] = useState<string[]>([]);
  const [nivelSel, setNivelSel] = useState<string[]>([]);
  const [minPub, setMinPub] = useState(0);
  const [minExpAdmin, setMinExpAdmin] = useState(0);
  const [maxIrregularidad, setMaxIrregularidad] = useState(0);
  const [minDuracionMediana, setMinDuracionMediana] = useState(0);
  const [minCargosEspol, setMinCargosEspol] = useState(0);
  const [maxCargosEspol, setMaxCargosEspol] = useState(0);

  const equiposQuery = useQuery({
    queryKey: [
      "equipos", vigencia, tipoSel, nivelSel, minPub, minExpAdmin,
      maxIrregularidad, minDuracionMediana, minCargosEspol, maxCargosEspol,
    ],
    queryFn: () =>
      getEquipos({
        vigencia,
        tipo: tipoSel,
        nivel: nivelSel,
        minPublicaciones: minPub,
        minExpAdmin,
        maxIrregularidad,
        minDuracionMediana,
        minCargosEspol,
        maxCargosEspol,
      }),
  });

  function descargarCSV() {
    if (!equiposQuery.data) return;
    const cols = METRICAS_CLAVE_COLUMNS.filter((c) => equiposQuery.data!.candidatos[0]?.[c.key] !== undefined || c.key === "NOMBRE_COMPLETO");
    const header = cols.map((c) => c.key).join(",");
    const rows = equiposQuery.data.candidatos.map((row) =>
      cols.map((c) => JSON.stringify(row[c.key] ?? "")).join(",")
    );
    const csv = [header, ...rows].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "candidatos_equipo.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-5">
      <p className="text-sm text-slate-600">
        Filtra candidatos por perfil y por criterios profesionales/institucionales para apoyar la
        conformación de una comisión o equipo. ¿Buscas por conocimiento/experiencia además de
        estos filtros? Usa "Búsqueda combinada" en su lugar.
      </p>

      <FiltrosEstructurados
        state={{
          vigencia, setVigencia, tipoSel, setTipoSel,
          nivelSel, setNivelSel, minPub, setMinPub, minExpAdmin, setMinExpAdmin,
          maxIrregularidad, setMaxIrregularidad, minDuracionMediana, setMinDuracionMediana,
          minCargosEspol, setMinCargosEspol, maxCargosEspol, setMaxCargosEspol,
        }}
        opcionesTipo={equiposQuery.data?.opciones.tipo_empleado ?? []}
        opcionesNivel={equiposQuery.data?.opciones.nivel_academico ?? []}
      />

      <div className="bg-white rounded-xl border border-slate-200 p-4">
        {equiposQuery.isLoading ? (
          <LoadingBlock label="Filtrando candidatos..." />
        ) : equiposQuery.error || !equiposQuery.data ? (
          <ErrorBlock message="No se pudo cargar la lista de candidatos." />
        ) : (
          <>
            <div className="flex items-center justify-between mb-3">
              <p className="text-sm font-semibold text-slate-700">
                {equiposQuery.data.n_resultados} personas cumplen los criterios.
              </p>
              <button
                onClick={descargarCSV}
                className="px-3 py-1.5 text-sm rounded-md bg-espol-navy text-white hover:bg-espol-blue transition-colors"
              >
                Descargar candidatos (CSV)
              </button>
            </div>
            <DataTable columns={COLUMNAS_CANDIDATOS} rows={equiposQuery.data.candidatos} maxHeight={500} />
          </>
        )}
      </div>
    </div>
  );
}
