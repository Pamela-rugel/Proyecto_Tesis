import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { getEquipos, getResumen } from "../api/client";
import { LoadingBlock, ErrorBlock } from "../components/LoadingBlock";
import DataTable from "../components/DataTable";
import { METRICAS_CLAVE_COLUMNS } from "../lib/columns";

const VIGENCIA_OPTS = ["Cualquiera", "Solo vigentes", "Solo no vigentes"];

export default function EquiposPage() {
  const resumenQuery = useQuery({ queryKey: ["resumen"], queryFn: getResumen });
  const perfiles = resumenQuery.data?.perfiles ?? [];

  const [perfilesSel, setPerfilesSel] = useState<number[]>([]);
  const [vigencia, setVigencia] = useState("Cualquiera");
  const [tipoSel, setTipoSel] = useState<string[]>([]);
  const [nivelSel, setNivelSel] = useState<string[]>([]);
  const [minPub, setMinPub] = useState(0);
  const [minExpAdmin, setMinExpAdmin] = useState(0);
  const [perfilesInit, setPerfilesInit] = useState(false);

  if (!perfilesInit && perfiles.length > 0) {
    setPerfilesSel(perfiles.map((p) => p.CLUSTER));
    setPerfilesInit(true);
  }

  const equiposQuery = useQuery({
    queryKey: ["equipos", perfilesSel, vigencia, tipoSel, nivelSel, minPub, minExpAdmin],
    queryFn: () =>
      getEquipos({
        perfiles: perfilesSel,
        vigencia,
        tipo: tipoSel,
        nivel: nivelSel,
        minPublicaciones: minPub,
        minExpAdmin,
      }),
    enabled: perfilesInit,
  });

  function togglePerfil(c: number) {
    setPerfilesSel((prev) => (prev.includes(c) ? prev.filter((x) => x !== c) : [...prev, c]));
  }
  function toggleMulti(list: string[], setList: (v: string[]) => void, value: string) {
    setList(list.includes(value) ? list.filter((x) => x !== value) : [...list, value]);
  }

  function descargarCSV() {
    if (!equiposQuery.data) return;
    const cols = METRICAS_CLAVE_COLUMNS.filter((c) => equiposQuery.data!.candidatos[0]?.[c.key] !== undefined || c.key === "IDPERSONA");
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
        conformación de una comisión o equipo.
      </p>

      <div className="bg-white rounded-xl border border-slate-200 p-4 space-y-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1.5">Perfiles a incluir</p>
          <div className="flex flex-wrap gap-1.5">
            {perfiles.map((p) => (
              <button
                key={p.CLUSTER}
                onClick={() => togglePerfil(p.CLUSTER)}
                className={`px-2.5 py-1 text-xs rounded-md border transition-colors ${
                  perfilesSel.includes(p.CLUSTER) ? "text-white border-transparent" : "border-slate-300 text-slate-600 hover:bg-slate-50"
                }`}
                style={perfilesSel.includes(p.CLUSTER) ? { backgroundColor: p.COLOR } : undefined}
              >
                {p.CLUSTER} — {p.PERFIL_NOMBRE}
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1.5">Vigencia</p>
            <select
              value={vigencia}
              onChange={(e) => setVigencia(e.target.value)}
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
              {(resumenQuery.data ? equiposQuery.data?.opciones.tipo_empleado ?? [] : []).map((t) => (
                <button
                  key={t}
                  onClick={() => toggleMulti(tipoSel, setTipoSel, t)}
                  className={`px-2 py-1 text-xs rounded-md border transition-colors ${
                    tipoSel.includes(t) ? "bg-espol-blue text-white border-espol-blue" : "border-slate-300 text-slate-600 hover:bg-slate-50"
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
              {(equiposQuery.data?.opciones.nivel_academico ?? []).map((n) => (
                <button
                  key={n}
                  onClick={() => toggleMulti(nivelSel, setNivelSel, n)}
                  className={`px-2 py-1 text-xs rounded-md border transition-colors ${
                    nivelSel.includes(n) ? "bg-espol-blue text-white border-espol-blue" : "border-slate-300 text-slate-600 hover:bg-slate-50"
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
              value={minPub}
              onChange={(e) => setMinPub(Number(e.target.value))}
              className="w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-espol-blue"
            />
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1.5">Mínimo de años de experiencia administrativa</p>
            <input
              type="number"
              min={0}
              step={0.5}
              value={minExpAdmin}
              onChange={(e) => setMinExpAdmin(Number(e.target.value))}
              className="w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-espol-blue"
            />
          </div>
        </div>
      </div>

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
            <DataTable columns={METRICAS_CLAVE_COLUMNS} rows={equiposQuery.data.candidatos} maxHeight={500} />
          </>
        )}
      </div>
    </div>
  );
}
