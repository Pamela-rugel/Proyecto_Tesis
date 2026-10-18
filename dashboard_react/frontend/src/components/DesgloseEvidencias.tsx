import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getEvidencias, type EvidenciaDetalle, type ValorAtributo } from "../api/client";
import { NOMBRE_TIPO } from "../lib/colores";

interface Props {
  personaId: number;
  /** dimensión elegida al llegar desde la pestaña Dimensiones (null = todas) */
  dimensionInicial: string | null;
}

const POR_PAGINA = 10;

const etiqueta = (campo: string) => {
  const t = campo.replace(/_/g, " ");
  return t.charAt(0).toUpperCase() + t.slice(1);
};

const SinDato = () => <span className="italic text-slate-400">sin dato</span>;

function Valor({ v }: { v: ValorAtributo }) {
  if (v === null) return <SinDato />;
  if (typeof v === "boolean") return <>{v ? "Sí" : "No"}</>;
  if (typeof v === "number") return <>{v.toLocaleString("es-EC")}</>;
  if (typeof v === "string") return <>{v}</>;
  if (Array.isArray(v)) {
    if (v.every((x) => x === null || typeof x !== "object")) {
      return (
        <>
          {v.map((x, i) => (
            <span key={i}>
              {i > 0 && ", "}
              <Valor v={x} />
            </span>
          ))}
        </>
      );
    }
    return (
      <ul className="space-y-0.5">
        {v.map((x, i) => (
          <li key={i} className="pl-2 border-l border-slate-200">
            <Valor v={x} />
          </li>
        ))}
      </ul>
    );
  }
  return (
    <>
      {Object.entries(v).map(([k, x], i) => (
        <span key={k}>
          {i > 0 && " · "}
          <span className="text-slate-500">{etiqueta(k)}:</span> <Valor v={x} />
        </span>
      ))}
    </>
  );
}

// Una línea por evidencia: título y fechas; clic para ver todos sus datos.
function Evidencia({ e }: { e: EvidenciaDetalle }) {
  return (
    <li>
      <details>
        <summary className="cursor-pointer py-0.5 flex gap-2 items-baseline marker:text-slate-300">
          <span className="text-slate-800 flex-1 min-w-0 truncate" title={e.texto ?? undefined}>{e.texto ?? <SinDato />}</span>
          {e.con_fecha && <span className="text-[10px] text-slate-400 shrink-0 tabular-nums">{e.fechas ?? "sin fecha"}</span>}
        </summary>
        <dl className="mb-1.5 ml-3 pl-2 border-l grid grid-cols-[minmax(0,7rem)_minmax(0,1fr)] gap-x-2 text-[11px]">
          {e.campos.map((c) => (
            <div key={c.campo} className="contents">
              <dt className="text-slate-500 truncate" title={etiqueta(c.campo)}>{etiqueta(c.campo)}</dt>
              <dd className="text-slate-700 break-words min-w-0"><Valor v={c.valor} /></dd>
            </div>
          ))}
        </dl>
      </details>
    </li>
  );
}

function Tipo({ tipo, n, evidencias, conTitulo }: { tipo: string; n: number; evidencias: EvidenciaDetalle[]; conTitulo: boolean }) {
  const [visibles, setVisibles] = useState(POR_PAGINA);
  return (
    <div>
      {conTitulo && (
        <p className="text-[11px] font-medium text-slate-500 mt-1">
          {NOMBRE_TIPO[tipo] ?? tipo} ({n})
        </p>
      )}
      <ul className="text-xs">
        {evidencias.slice(0, visibles).map((e, i) => (
          <Evidencia key={i} e={e} />
        ))}
      </ul>
      {n > visibles && (
        <button className="text-[11px] text-espol-blue hover:underline" onClick={() => setVisibles(visibles + POR_PAGINA * 2)}>
          Mostrar más ({n - visibles})
        </button>
      )}
    </div>
  );
}

// Pestaña "Evidencias": lo que sustenta el perfil, por dimensión y tipo, con los datos tal como
// vienen en cada evidencia (sin identificadores internos). Se carga al abrir la pestaña. Cada
// dimensión se despliega por separado; llegando desde Dimensiones, esa dimensión viene abierta.
export default function DesgloseEvidencias({ personaId, dimensionInicial }: Props) {
  const { data, isLoading, isError } = useQuery({ queryKey: ["evidencias", personaId], queryFn: () => getEvidencias(personaId) });

  if (isLoading) return <p className="text-xs text-slate-500">Cargando evidencias…</p>;
  if (isError || !data) return <p className="text-xs text-red-600">No se pudieron cargar las evidencias.</p>;
  if (data.length === 0) return <p className="text-xs text-slate-500">La persona no tiene evidencias registradas.</p>;

  return (
    <div>
      <p
        className="text-[11px] text-slate-500 mb-2"
        title="«Otras evidencias» no cuentan en ninguna dimensión (p. ej., actividades de carga sin horas de docencia)."
      >
        Datos tal como vienen registrados; «sin dato» = campo vacío en la fuente.
      </p>
      <div className="divide-y border-y">
        {data.map((g) => (
          <details key={g.dimension} open={g.dimension === dimensionInicial} className="py-1">
            <summary className="cursor-pointer flex items-baseline gap-2 text-xs font-medium text-slate-800">
              <span className="flex-1">{g.nombre}</span>
              <span className="text-[11px] font-normal text-slate-500 tabular-nums">{g.n}</span>
            </summary>
            <div className="pt-0.5 pb-1">
              {g.tipos.map((t) => (
                <Tipo key={t.tipo_id} tipo={t.tipo_id} n={t.n} evidencias={t.evidencias} conTitulo={g.tipos.length > 1} />
              ))}
            </div>
          </details>
        ))}
      </div>
    </div>
  );
}
